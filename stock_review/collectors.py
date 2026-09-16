"""
股票复盘工具 - 9大数据采集模块
每个模块独立容错，单模块失败不影响其他模块
"""
import logging
from datetime import datetime, date
from typing import List, Dict, Optional

import pandas as pd
import numpy as np

import config
from data_fetcher import DataFetcher, safe_float
from filters import StockFilter
from database import DatabaseManager

logger = logging.getLogger(__name__)


class ReviewCollector:
    """
    复盘数据采集总控
    负责调度 9 个子模块，汇总结果
    优先从本地 DB 读取 K 线，DB 无数据时才调 API
    """

    def __init__(self, fetcher: DataFetcher, stock_filter: StockFilter,
                 db: DatabaseManager = None):
        self.fetcher = fetcher
        self.filter = stock_filter
        self.db = db  # 本地数据库（用于读取持久化的K线）
        self._spot_df: Optional[pd.DataFrame] = None
        self._sector_flow_df: Optional[pd.DataFrame] = None
        self._stock_flow_df: Optional[pd.DataFrame] = None
        self._sector_map: Dict[str, str] = {}
        self._kline_from_db = 0   # 统计：从DB读取的K线数
        self._kline_from_api = 0  # 统计：从API拉取的K线数

    def _ensure_base_data(self):
        """确保基础数据已加载"""
        if self._spot_df is None:
            self._spot_df = self.fetcher.get_all_stocks_spot()
        if self._sector_flow_df is None:
            self._sector_flow_df = self.fetcher.get_sector_fund_flow()
        if self._stock_flow_df is None:
            self._stock_flow_df = self.fetcher.get_stock_fund_flow()

    def _get_sector_for_stock(self, stock_code: str) -> str:
        """获取个股所属板块名称"""
        if not self._sector_map:
            self._sector_map = self.fetcher.get_stock_sector_map()
        return self._sector_map.get(stock_code, "")

    def _enrich_with_sector(self, records: List[dict]) -> List[dict]:
        """为记录补充板块信息"""
        for r in records:
            if not r.get("sector_name"):
                r["sector_name"] = self._get_sector_for_stock(r.get("stock_code", ""))
        return records

    def _get_kline_smart(self, stock_code: str, days: int = 30) -> pd.DataFrame:
        """
        智能获取K线：优先从本地DB读取，不足时从API拉取并存入DB
        """
        # 1. 尝试从本地 DB 读取
        if self.db:
            records = self.db.get_stock_kline(stock_code, days)
            if len(records) >= days - 2:  # 允许少2天（周末/节假日）
                self._kline_from_db += 1
                return pd.DataFrame(records)

        # 2. DB 不足，从 API 拉取
        df = self.fetcher.get_stock_history(stock_code, days)
        if df is not None and not df.empty:
            self._kline_from_api += 1
            # 同时存入 DB（下次不用再拉）
            if self.db:
                try:
                    self.db.save_stock_daily_quotes(stock_code, df.to_dict("records"))
                except Exception:
                    pass
        return df if df is not None else pd.DataFrame()

    def _batch_get_kline_smart(self, codes: List[str], days: int = 30,
                                progress_callback=None) -> Dict[str, pd.DataFrame]:
        """
        批量智能获取K线：DB有的直接读，没有的走API
        """
        result = {}
        db_hit = 0
        api_need = []

        # 第一轮：从 DB 读取
        if self.db:
            for code in codes:
                records = self.db.get_stock_kline(code, days)
                if len(records) >= days - 2:
                    result[code] = pd.DataFrame(records)
                    db_hit += 1
                else:
                    api_need.append(code)
        else:
            api_need = list(codes)

        if db_hit > 0:
            logger.info(f"  K线本地DB命中: {db_hit} 只，需API拉取: {len(api_need)} 只")

        # 第二轮：从 API 拉取（带熔断）
        if api_need:
            api_result = self.fetcher.batch_get_stock_history(
                api_need, days=days, progress_callback=progress_callback
            )
            # 拉到的存入 DB
            for code, df in api_result.items():
                result[code] = df
                if self.db and not df.empty:
                    try:
                        self.db.save_stock_daily_quotes(code, df.to_dict("records"))
                    except Exception:
                        pass

        self._kline_from_db += db_hit
        self._kline_from_api += len(api_need) - (len(api_need) - len([c for c in api_need if c in result]))
        return result

    # =================================================================
    #  模块 1 & 2: 资金流入/流出前十板块
    # =================================================================

    def collect_sector_inflow_top10(self, trade_date: str) -> List[dict]:
        """4.1 资金流入前十板块"""
        try:
            self._ensure_base_data()
            df = self._sector_flow_df.copy()
            if df.empty:
                logger.warning("板块资金流数据为空")
                return []

            # 确保 net_amount 列存在
            if "net_amount" not in df.columns:
                for col in df.columns:
                    if "净流入" in str(col) or "净额" in str(col):
                        df = df.rename(columns={col: "net_amount"})
                        break

            if "net_amount" not in df.columns:
                logger.warning("板块资金流数据缺少 net_amount 列")
                return []

            df["net_amount"] = pd.to_numeric(df["net_amount"], errors="coerce").fillna(0)
            # 按净流入降序，取前 N
            df = df.sort_values("net_amount", ascending=False).head(config.SECTOR_TOP_N)

            records = []
            for rank, (_, row) in enumerate(df.iterrows(), 1):
                records.append({
                    "sector_name": str(row.get("sector_name", "")),
                    "sector_code": str(row.get("sector_code", "")),
                    "net_amount": safe_float(row.get("net_amount")),
                    "change_percent": safe_float(row.get("change_percent")),
                    "turnover_amount": safe_float(row.get("turnover_amount")),
                    "rank_no": rank,
                    "trade_date": trade_date,
                })
            logger.info(f"[模块1] 资金流入前十板块: {len(records)} 条")
            return records
        except Exception as e:
            logger.error(f"[模块1] 采集失败: {e}")
            return []

    def collect_sector_outflow_top10(self, trade_date: str) -> List[dict]:
        """4.2 资金流出前十板块"""
        try:
            self._ensure_base_data()
            df = self._sector_flow_df.copy()
            if df.empty:
                return []

            if "net_amount" not in df.columns:
                for col in df.columns:
                    if "净流入" in str(col) or "净额" in str(col):
                        df = df.rename(columns={col: "net_amount"})
                        break

            if "net_amount" not in df.columns:
                return []

            df["net_amount"] = pd.to_numeric(df["net_amount"], errors="coerce").fillna(0)
            # 按净流入升序（即净流出最多），取前 N
            df = df.sort_values("net_amount", ascending=True).head(config.SECTOR_TOP_N)

            records = []
            for rank, (_, row) in enumerate(df.iterrows(), 1):
                records.append({
                    "sector_name": str(row.get("sector_name", "")),
                    "sector_code": str(row.get("sector_code", "")),
                    "net_amount": safe_float(row.get("net_amount")),
                    "change_percent": safe_float(row.get("change_percent")),
                    "turnover_amount": safe_float(row.get("turnover_amount")),
                    "rank_no": rank,
                    "trade_date": trade_date,
                })
            logger.info(f"[模块2] 资金流出前十板块: {len(records)} 条")
            return records
        except Exception as e:
            logger.error(f"[模块2] 采集失败: {e}")
            return []

    # =================================================================
    #  模块 3 & 4: 资金流入/流出前30个股
    # =================================================================

    def collect_stock_inflow_top30(self, trade_date: str) -> List[dict]:
        """4.3 资金流入前30股"""
        try:
            self._ensure_base_data()
            df = self._stock_flow_df.copy()
            if df.empty:
                return []

            if "net_amount" not in df.columns:
                for col in df.columns:
                    if "净流入" in str(col) or "净额" in str(col):
                        df = df.rename(columns={col: "net_amount"})
                        break
            if "net_amount" not in df.columns:
                return []

            # 过滤 ST/新股/次新股
            df = self.filter.filter_dataframe(df, code_col="stock_code")
            df["net_amount"] = pd.to_numeric(df["net_amount"], errors="coerce").fillna(0)
            df = df.sort_values("net_amount", ascending=False).head(config.STOCK_INFLOW_TOP_N)

            records = []
            for rank, (_, row) in enumerate(df.iterrows(), 1):
                records.append({
                    "stock_code": str(row.get("stock_code", "")),
                    "stock_name": str(row.get("stock_name", "")),
                    "sector_name": str(row.get("sector_name", self._get_sector_for_stock(str(row.get("stock_code", ""))))),
                    "net_amount": safe_float(row.get("net_amount")),
                    "change_percent": safe_float(row.get("change_percent")),
                    "turnover_amount": safe_float(row.get("turnover_amount")),
                    "turnover_rate": safe_float(row.get("turnover_rate")),
                    "rank_no": rank,
                    "trade_date": trade_date,
                })
            records = self._enrich_with_sector(records)
            logger.info(f"[模块3] 资金流入前30股: {len(records)} 条")
            return records
        except Exception as e:
            logger.error(f"[模块3] 采集失败: {e}")
            return []

    def collect_stock_outflow_top30(self, trade_date: str) -> List[dict]:
        """4.4 资金流出前30股"""
        try:
            self._ensure_base_data()
            df = self._stock_flow_df.copy()
            if df.empty:
                return []

            if "net_amount" not in df.columns:
                for col in df.columns:
                    if "净流入" in str(col) or "净额" in str(col):
                        df = df.rename(columns={col: "net_amount"})
                        break
            if "net_amount" not in df.columns:
                return []

            df = self.filter.filter_dataframe(df, code_col="stock_code")
            df["net_amount"] = pd.to_numeric(df["net_amount"], errors="coerce").fillna(0)
            df = df.sort_values("net_amount", ascending=True).head(config.STOCK_OUTFLOW_TOP_N)

            records = []
            for rank, (_, row) in enumerate(df.iterrows(), 1):
                records.append({
                    "stock_code": str(row.get("stock_code", "")),
                    "stock_name": str(row.get("stock_name", "")),
                    "sector_name": str(row.get("sector_name", "")),
                    "net_amount": safe_float(row.get("net_amount")),
                    "change_percent": safe_float(row.get("change_percent")),
                    "turnover_amount": safe_float(row.get("turnover_amount")),
                    "turnover_rate": safe_float(row.get("turnover_rate")),
                    "rank_no": rank,
                    "trade_date": trade_date,
                })
            records = self._enrich_with_sector(records)
            logger.info(f"[模块4] 资金流出前30股: {len(records)} 条")
            return records
        except Exception as e:
            logger.error(f"[模块4] 采集失败: {e}")
            return []

    # =================================================================
    #  模块 5: 今日资金异动板块及带领个股
    # =================================================================

    def collect_abnormal_sectors(self, trade_date: str) -> List[dict]:
        """
        4.5 识别异动板块及龙头个股
        异动判断：资金净流入靠前 + 涨幅高 + 成交额放大
        """
        try:
            self._ensure_base_data()
            df = self._sector_flow_df.copy()
            if df.empty:
                return []

            # 标准化列名
            for col in df.columns:
                if "净流入" in str(col) or "净额" in str(col):
                    if "net_amount" not in df.columns:
                        df = df.rename(columns={col: "net_amount"})
                if "涨跌幅" in str(col):
                    if "change_percent" not in df.columns:
                        df = df.rename(columns={col: "change_percent"})
                if "成交额" in str(col):
                    if "turnover_amount" not in df.columns:
                        df = df.rename(columns={col: "turnover_amount"})

            for c in ["net_amount", "change_percent", "turnover_amount"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

            # 异动板块条件（满足任一即可）
            if "net_amount" not in df.columns:
                return []

            df = df.sort_values("net_amount", ascending=False).reset_index(drop=True)
            df["rank"] = df.index + 1

            abnormal_mask = pd.Series(False, index=df.index)
            # 条件1: 资金净流入排名前 N
            abnormal_mask |= (df["rank"] <= config.ABNORMAL_SECTOR_INFLOW_RANK)
            # 条件2: 涨幅高于阈值
            if "change_percent" in df.columns:
                abnormal_mask |= (df["change_percent"] >= config.ABNORMAL_SECTOR_CHANGE_THRESHOLD)

            abnormal_df = df[abnormal_mask].copy()
            # 取资金净流入为正的板块
            abnormal_df = abnormal_df[abnormal_df["net_amount"] > 0]

            records = []
            for _, sector_row in abnormal_df.iterrows():
                sector_name = str(sector_row.get("sector_name", ""))
                sector_code = str(sector_row.get("sector_code", ""))

                # 获取板块龙头个股
                leaders = self._find_sector_leaders(sector_name)

                if leaders:
                    for leader in leaders:
                        records.append({
                            "sector_name": sector_name,
                            "sector_code": sector_code,
                            "sector_net_amount": safe_float(sector_row.get("net_amount")),
                            "sector_change_percent": safe_float(sector_row.get("change_percent")),
                            "stock_code": leader.get("stock_code", ""),
                            "stock_name": leader.get("stock_name", ""),
                            "net_amount": leader.get("net_amount", 0),
                            "change_percent": leader.get("change_percent", 0),
                            "turnover_amount": leader.get("turnover_amount", 0),
                            "turnover_rate": leader.get("turnover_rate", 0),
                            "trade_date": trade_date,
                        })
                else:
                    # 没有龙头数据也保留板块记录，用 sector_code 做唯一标识避免DB冲突
                    records.append({
                        "sector_name": sector_name,
                        "sector_code": sector_code,
                        "sector_net_amount": safe_float(sector_row.get("net_amount")),
                        "sector_change_percent": safe_float(sector_row.get("change_percent")),
                        "stock_code": f"SECTOR_{sector_code or sector_name}",
                        "stock_name": f"[板块]{sector_name}",
                        "net_amount": safe_float(sector_row.get("net_amount")),
                        "change_percent": safe_float(sector_row.get("change_percent")),
                        "turnover_amount": 0,
                        "turnover_rate": 0,
                        "trade_date": trade_date,
                    })

            logger.info(f"[模块5] 异动板块及龙头: {len(records)} 条")
            return records
        except Exception as e:
            logger.error(f"[模块5] 采集失败: {e}")
            return []

    def _find_sector_leaders(self, sector_name: str) -> List[dict]:
        """从个股资金流中找出板块龙头"""
        try:
            # 尝试获取板块成分股
            cons_df = self.fetcher.get_sector_stocks(sector_name)

            if cons_df is not None and not cons_df.empty:
                # 有成分股数据：在资金流中匹配
                if "stock_code" in cons_df.columns:
                    codes = set(cons_df["stock_code"].astype(str).tolist())
                    flow_df = self._stock_flow_df.copy()
                    if not flow_df.empty and "stock_code" in flow_df.columns:
                        flow_df = flow_df[flow_df["stock_code"].astype(str).isin(codes)]
                        flow_df = self.filter.filter_dataframe(flow_df)
                        if "net_amount" not in flow_df.columns:
                            for col in flow_df.columns:
                                if "净流入" in str(col):
                                    flow_df = flow_df.rename(columns={col: "net_amount"})
                                    break
                        if "net_amount" in flow_df.columns:
                            flow_df["net_amount"] = pd.to_numeric(flow_df["net_amount"], errors="coerce").fillna(0)
                            flow_df = flow_df.sort_values("net_amount", ascending=False)
                            top = flow_df.head(config.ABNORMAL_LEADER_TOP_N)
                            return [
                                {
                                    "stock_code": str(row.get("stock_code", "")),
                                    "stock_name": str(row.get("stock_name", "")),
                                    "net_amount": safe_float(row.get("net_amount")),
                                    "change_percent": safe_float(row.get("change_percent")),
                                    "turnover_amount": safe_float(row.get("turnover_amount")),
                                    "turnover_rate": safe_float(row.get("turnover_rate")),
                                }
                                for _, row in top.iterrows()
                            ]
            return []
        except Exception as e:
            logger.debug(f"获取板块 [{sector_name}] 龙头失败: {e}")
            return []

    # =================================================================
    #  模块 6: 放量且5日线上穿10日线，站稳5日线
    # =================================================================

    def collect_ma_cross_stocks(self, trade_date: str) -> List[dict]:
        """
        4.6 筛选满足技术形态的个股
        条件: 放量 + MA5上穿MA10 + 收盘价站上MA5
        """
        try:
            self._ensure_base_data()
            df = self._spot_df.copy()
            if df.empty:
                return []

            # 过滤ST/新股/次新股
            df = self.filter.filter_dataframe(df, code_col="stock_code")

            # 预筛选：减少需要获取K线的股票数量
            if "close" in df.columns:
                df["close"] = pd.to_numeric(df["close"], errors="coerce").fillna(0)
                df = df[df["close"] > 0]  # 排除停牌
            if "change_percent" in df.columns:
                df["change_percent"] = pd.to_numeric(df["change_percent"], errors="coerce").fillna(0)
                # MA5上穿MA10场景：涨幅通常为正且不太大
                df = df[(df["change_percent"] > 0) & (df["change_percent"] < 8)]
            if "volume_ratio" in df.columns:
                df["volume_ratio"] = pd.to_numeric(df["volume_ratio"], errors="coerce").fillna(0)
                df = df[df["volume_ratio"] >= config.VOLUME_RATIO_THRESHOLD]
            if "turnover_rate" in df.columns:
                df["turnover_rate"] = pd.to_numeric(df["turnover_rate"], errors="coerce").fillna(0)
                df = df[df["turnover_rate"] > 0.5]  # 有一定换手率

            candidates = df["stock_code"].astype(str).tolist()
            logger.info(f"[模块6] MA交叉预筛选: {len(candidates)} 只候选")

            if not candidates:
                return []

            # 限制数量，避免请求过多
            candidates = candidates[:300]

            # 批量获取K线
            def progress(done, total):
                logger.info(f"[模块6] 获取K线进度: {done}/{total}")

            history_map = self._batch_get_kline_smart(
                candidates, days=25, progress_callback=progress
            )

            records = []
            for code, hist_df in history_map.items():
                result = self._check_ma_cross(code, hist_df)
                if result:
                    result["trade_date"] = trade_date
                    result["sector_name"] = self._get_sector_for_stock(code)
                    records.append(result)

            records = self.filter.filter_records(records)
            logger.info(f"[模块6] 放量MA5上穿MA10: {len(records)} 只")
            return records
        except Exception as e:
            logger.error(f"[模块6] 采集失败: {e}")
            return []

    @staticmethod
    def _check_ma_cross(code: str, hist_df: pd.DataFrame) -> Optional[dict]:
        """检查单只股票是否满足MA5上穿MA10+放量条件"""
        try:
            if hist_df.empty or len(hist_df) < 12:
                return None

            df = hist_df.sort_values("date").reset_index(drop=True)
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

            # 计算均线
            df["ma5"] = df["close"].rolling(5).mean()
            df["ma10"] = df["close"].rolling(10).mean()
            df["vol_ma5"] = df["volume"].rolling(5).mean()

            # 取最后两天
            if len(df) < 12:
                return None

            today = df.iloc[-1]
            yesterday = df.iloc[-2]

            ma5_today = today["ma5"]
            ma10_today = today["ma10"]
            ma5_yesterday = yesterday["ma5"]
            ma10_yesterday = yesterday["ma10"]
            close_today = today["close"]
            volume_today = today["volume"]
            vol_ma5 = today["vol_ma5"]

            if pd.isna(ma5_today) or pd.isna(ma10_today) or pd.isna(ma5_yesterday) or pd.isna(ma10_yesterday):
                return None

            # 条件1: 今日放量（成交量 > 5日均量）
            if vol_ma5 > 0 and volume_today <= vol_ma5:
                return None

            # 条件2: MA5 今日上穿 MA10（昨日 MA5 <= MA10，今日 MA5 > MA10）
            if not (ma5_yesterday <= ma10_yesterday and ma5_today > ma10_today):
                return None

            # 条件3: 收盘价站上 MA5
            if close_today < ma5_today:
                return None

            # 通过所有条件
            stock_name = ""
            # 从 spot 数据获取名称（这里简化处理）
            return {
                "stock_code": code,
                "stock_name": stock_name,
                "volume": float(volume_today),
                "vol_ma5": float(vol_ma5),
                "ma5": round(float(ma5_today), 2),
                "ma10": round(float(ma10_today), 2),
                "close": float(close_today),
                "change_percent": safe_float(today.get("change_percent")),
                "turnover_amount": safe_float(today.get("turnover_amount")),
                "extra": {
                    "open": safe_float(today.get("open")),
                    "high": safe_float(today.get("high")),
                    "low": safe_float(today.get("low")),
                    "turnover_rate": safe_float(today.get("turnover_rate")),
                    "volume_ratio": round(float(volume_today / vol_ma5), 2) if vol_ma5 > 0 else 0,
                },
            }
        except Exception:
            return None

    # =================================================================
    #  模块 7: 成交额前20股
    # =================================================================

    def collect_turnover_top20(self, trade_date: str) -> List[dict]:
        """4.7 资金成交量前20股"""
        try:
            self._ensure_base_data()
            df = self._spot_df.copy()
            if df.empty:
                return []

            # 过滤
            df = self.filter.filter_dataframe(df, code_col="stock_code")

            if "turnover_amount" not in df.columns:
                for col in df.columns:
                    if "成交额" in str(col):
                        df = df.rename(columns={col: "turnover_amount"})
                        break
            if "turnover_amount" not in df.columns:
                return []

            df["turnover_amount"] = pd.to_numeric(df["turnover_amount"], errors="coerce").fillna(0)
            df = df.sort_values("turnover_amount", ascending=False).head(config.TURNOVER_TOP_N)

            records = []
            for rank, (_, row) in enumerate(df.iterrows(), 1):
                records.append({
                    "stock_code": str(row.get("stock_code", "")),
                    "stock_name": str(row.get("stock_name", "")),
                    "sector_name": "",
                    "turnover_amount": safe_float(row.get("turnover_amount")),
                    "volume": safe_float(row.get("volume")),
                    "change_percent": safe_float(row.get("change_percent")),
                    "turnover_rate": safe_float(row.get("turnover_rate")),
                    "rank_no": rank,
                    "trade_date": trade_date,
                })
            records = self._enrich_with_sector(records)
            logger.info(f"[模块7] 成交额前20: {len(records)} 条")
            return records
        except Exception as e:
            logger.error(f"[模块7] 采集失败: {e}")
            return []

    # =================================================================
    #  模块 8: 近10日涨停个股
    # =================================================================

    def collect_limit_up_stocks(self, trade_date: str) -> List[dict]:
        """4.8 近10日内有涨停的个股名单"""
        try:
            # 获取最近交易日列表
            trade_dates = self.fetcher.get_recent_trade_dates(
                config.LIMIT_UP_LOOKBACK_DAYS + 5
            )
            # 取最近 N 个交易日
            trade_dates = trade_dates[:config.LIMIT_UP_LOOKBACK_DAYS]

            if not trade_dates:
                logger.warning("[模块8] 无法获取交易日历")
                return []

            # 逐日获取涨停池
            all_zt = []
            for td in trade_dates:
                try:
                    zt_df = self.fetcher.get_limit_up_pool(td)
                    if zt_df is not None and not zt_df.empty:
                        if "stock_code" in zt_df.columns:
                            zt_df["zt_date"] = td
                            all_zt.append(zt_df)
                except Exception as e:
                    logger.debug(f"获取 {td} 涨停池失败: {e}")
                    continue

            if not all_zt:
                logger.warning("[模块8] 未获取到涨停数据")
                return []

            combined = pd.concat(all_zt, ignore_index=True)
            combined = self.filter.filter_dataframe(combined, code_col="stock_code")

            if combined.empty:
                return []

            # 按股票聚合：涨停次数、最近涨停日期
            grouped = combined.groupby("stock_code").agg(
                stock_name=("stock_name", "first"),
                zt_count=("zt_date", "count"),
                last_zt_date=("zt_date", "max"),
                zt_dates=("zt_date", list),
            ).reset_index()

            grouped = grouped.sort_values("zt_count", ascending=False)

            # 计算最近一次涨停后的涨跌幅
            spot_dict = {}
            if not self._spot_df.empty:
                for _, row in self._spot_df.iterrows():
                    spot_dict[str(row.get("stock_code", ""))] = row

            records = []
            for _, row in grouped.iterrows():
                code = str(row["stock_code"])
                spot = spot_dict.get(code, {})
                records.append({
                    "stock_code": code,
                    "stock_name": str(row.get("stock_name", "")),
                    "sector_name": self._get_sector_for_stock(code),
                    "change_percent": safe_float(spot.get("change_percent") if isinstance(spot, dict) else (spot["change_percent"] if "change_percent" in spot.index else 0)),
                    "rank_no": 0,
                    "trade_date": trade_date,
                    "extra": {
                        "zt_count": int(row["zt_count"]),
                        "last_zt_date": str(row["last_zt_date"]),
                        "zt_dates": [str(d) for d in row.get("zt_dates", [])],
                    },
                })
            logger.info(f"[模块8] 近10日涨停: {len(records)} 只")
            return records
        except Exception as e:
            logger.error(f"[模块8] 采集失败: {e}")
            return []

    # =================================================================
    #  模块 9: 近几日下跌且下跌量逐渐变小的个股
    # =================================================================

    def collect_decline_shrink_volume(self, trade_date: str) -> List[dict]:
        """
        4.9 近期持续下跌但缩量的个股
        优先关注：今日下跌且放量的（可能见底信号）
        """
        try:
            self._ensure_base_data()
            df = self._spot_df.copy()
            if df.empty:
                return []

            # 过滤
            df = self.filter.filter_dataframe(df, code_col="stock_code")

            # 预筛选：今日下跌
            if "change_percent" in df.columns:
                df["change_percent"] = pd.to_numeric(df["change_percent"], errors="coerce").fillna(0)
                df = df[df["change_percent"] < 0]
            if "close" in df.columns:
                df["close"] = pd.to_numeric(df["close"], errors="coerce").fillna(0)
                df = df[df["close"] > 0]

            candidates = df["stock_code"].astype(str).tolist()
            logger.info(f"[模块9] 下跌缩量预筛选: {len(candidates)} 只候选")

            if not candidates:
                return []

            # 限制数量
            candidates = candidates[:500]

            def progress(done, total):
                logger.info(f"[模块9] 获取K线进度: {done}/{total}")

            history_map = self._batch_get_kline_smart(
                candidates, days=15, progress_callback=progress
            )

            records = []
            for code, hist_df in history_map.items():
                result = self._check_decline_shrink(code, hist_df)
                if result:
                    result["trade_date"] = trade_date
                    result["sector_name"] = self._get_sector_for_stock(code)
                    records.append(result)

            records = self.filter.filter_records(records)

            # 排序：优先今日下跌放量的
            records.sort(key=lambda x: (
                -1 if x.get("extra", {}).get("is_decline_volume_up") else 0,
                x.get("change_percent", 0),
            ))

            logger.info(f"[模块9] 下跌缩量/放量: {len(records)} 只")
            return records
        except Exception as e:
            logger.error(f"[模块9] 采集失败: {e}")
            return []

    @staticmethod
    def _check_decline_shrink(code: str, hist_df: pd.DataFrame) -> Optional[dict]:
        """
        检查单只股票是否满足下跌缩量条件
        基础: 最近3-5日整体下跌 + 成交量逐日缩小
        优先: 今日下跌 + 今日放量
        """
        try:
            if hist_df.empty or len(hist_df) < 6:
                return None

            df = hist_df.sort_values("date").reset_index(drop=True)
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
            df["change_percent"] = pd.to_numeric(df.get("change_percent", 0), errors="coerce").fillna(0)

            # 取最近 6 天数据
            recent = df.tail(6).reset_index(drop=True)
            if len(recent) < 6:
                return None

            today = recent.iloc[-1]
            yesterday = recent.iloc[-2]
            last_5 = recent.tail(5)
            last_3 = recent.tail(3)

            # 基础条件1: 近 3 日整体下跌
            close_3_days_ago = last_3.iloc[0]["close"]
            close_today = today["close"]
            if pd.isna(close_3_days_ago) or pd.isna(close_today) or close_3_days_ago <= 0:
                return None
            pct_3d = (close_today - close_3_days_ago) / close_3_days_ago * 100
            if pct_3d >= 0:
                return None

            # 基础条件2: 今日仍为下跌
            if today["change_percent"] >= 0:
                return None

            # 基础条件3: 下跌过程中成交量整体缩量趋势
            volumes = last_5["volume"].tolist()
            # 检查整体缩量趋势（允许偶尔波动，用线性回归斜率判断）
            if len(volumes) >= 3:
                x = np.arange(len(volumes) - 1)  # 不含今日
                y = np.array(volumes[:-1])
                if len(x) > 1 and np.std(y) > 0:
                    slope = np.polyfit(x, y, 1)[0]
                    is_shrinking = slope < 0
                else:
                    is_shrinking = False
            else:
                is_shrinking = False

            # 优先条件: 今日下跌放量
            vol_today = today["volume"]
            vol_yesterday = yesterday["volume"]
            vol_ma5 = last_5["volume"].mean()
            is_volume_up = (vol_today > vol_yesterday) and (vol_today > vol_ma5)

            # 必须满足缩量或今日放量中的至少一个
            if not is_shrinking and not is_volume_up:
                return None

            close_5_days_ago = last_5.iloc[0]["close"]
            pct_5d = (close_today - close_5_days_ago) / close_5_days_ago * 100 if close_5_days_ago > 0 else 0

            return {
                "stock_code": code,
                "stock_name": "",
                "change_percent": float(today["change_percent"]),
                "volume": float(vol_today),
                "turnover_amount": safe_float(today.get("turnover_amount")),
                "extra": {
                    "pct_3d": round(pct_3d, 2),
                    "pct_5d": round(pct_5d, 2),
                    "vol_today": float(vol_today),
                    "vol_yesterday": float(vol_yesterday),
                    "vol_ma5": round(float(vol_ma5), 0),
                    "is_decline_volume_up": is_volume_up,
                    "is_shrinking": is_shrinking,
                },
            }
        except Exception:
            return None

    # =================================================================
    #  汇总执行
    # =================================================================

    def collect_all(self, trade_date: str = None) -> dict:
        """
        执行全部9个模块的数据采集
        返回完整的 JSON 结构
        """
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"========== 开始复盘数据采集: {trade_date} ==========")

        # 预加载基础数据
        self._ensure_base_data()

        # 补充股票名称映射（供K线模块使用）
        name_map = {}
        if self._spot_df is not None and not self._spot_df.empty:
            for _, row in self._spot_df.iterrows():
                name_map[str(row.get("stock_code", ""))] = str(row.get("stock_name", ""))

        result = {
            "trade_date": trade_date,
            "sector_inflow_top10": [],
            "sector_outflow_top10": [],
            "stock_inflow_top30": [],
            "stock_outflow_top30": [],
            "abnormal_sectors": [],
            "volume_ma5_cross_ma10_stocks": [],
            "turnover_top20_stocks": [],
            "limit_up_stocks_last_10_days": [],
            "decline_shrink_volume_stocks": [],
        }

        # 模块1: 资金流入前十板块
        logger.info(">>> [1/9] 采集资金流入前十板块...")
        result["sector_inflow_top10"] = self.collect_sector_inflow_top10(trade_date)

        # 模块2: 资金流出前十板块
        logger.info(">>> [2/9] 采集资金流出前十板块...")
        result["sector_outflow_top10"] = self.collect_sector_outflow_top10(trade_date)

        # 模块3: 资金流入前30股
        logger.info(">>> [3/9] 采集资金流入前30股...")
        result["stock_inflow_top30"] = self.collect_stock_inflow_top30(trade_date)

        # 模块4: 资金流出前30股
        logger.info(">>> [4/9] 采集资金流出前30股...")
        result["stock_outflow_top30"] = self.collect_stock_outflow_top30(trade_date)

        # 模块5: 异动板块及龙头
        logger.info(">>> [5/9] 采集异动板块及龙头个股...")
        result["abnormal_sectors"] = self.collect_abnormal_sectors(trade_date)

        # 模块6: MA5上穿MA10放量
        logger.info(">>> [6/9] 采集放量MA5上穿MA10个股...")
        ma_cross = self.collect_ma_cross_stocks(trade_date)
        # 补充股票名称
        for r in ma_cross:
            if not r.get("stock_name"):
                r["stock_name"] = name_map.get(r.get("stock_code", ""), "")
        result["volume_ma5_cross_ma10_stocks"] = ma_cross

        # 模块7: 成交额前20
        logger.info(">>> [7/9] 采集成交额前20股...")
        result["turnover_top20_stocks"] = self.collect_turnover_top20(trade_date)

        # 模块8: 近10日涨停
        logger.info(">>> [8/9] 采集近10日涨停个股...")
        result["limit_up_stocks_last_10_days"] = self.collect_limit_up_stocks(trade_date)

        # 模块9: 下跌缩量
        logger.info(">>> [9/9] 采集下跌缩量个股...")
        decline = self.collect_decline_shrink_volume(trade_date)
        for r in decline:
            if not r.get("stock_name"):
                r["stock_name"] = name_map.get(r.get("stock_code", ""), "")
        result["decline_shrink_volume_stocks"] = decline

        # 统计
        total_records = sum(len(v) for v in result.values() if isinstance(v, list))
        logger.info(
            f"========== 复盘采集完成: 共 {total_records} 条记录 "
            f"(K线: DB命中{self._kline_from_db} API拉取{self._kline_from_api}) =========="
        )

        return result
