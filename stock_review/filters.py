"""
股票复盘工具 - 股票过滤器
统一过滤 ST、新股、次新股
"""
import re
import logging
from datetime import datetime, date, timedelta
from typing import Set, Dict, Optional, List

import pandas as pd

import config

logger = logging.getLogger(__name__)

# ST 股票名称关键字
ST_KEYWORDS = ["ST", "*ST", "SST", "S*ST", "st", "*st"]
ST_PATTERN = re.compile(r'(?:^|\s)(\*?S{0,2}\*?ST)', re.IGNORECASE)


def is_st_stock(stock_name: str) -> bool:
    """判断是否为 ST 股票"""
    if not stock_name:
        return False
    name = stock_name.strip().upper()
    # 精确匹配模式
    for kw in ["*ST", "SST", "S*ST", "ST"]:
        if kw in name:
            return True
    return False


def is_new_stock(list_date: Optional[date], today: date = None) -> bool:
    """判断是否为新股（上市 <= NEW_STOCK_DAYS 天）"""
    if list_date is None:
        return False  # 无上市日期视为非新股（宁可放过）
    today = today or datetime.now().date()
    days = (today - list_date).days
    return days <= config.NEW_STOCK_DAYS


def is_sub_new_stock(list_date: Optional[date], today: date = None) -> bool:
    """判断是否为次新股（上市 <= SUB_NEW_STOCK_DAYS 天）"""
    if list_date is None:
        return False
    today = today or datetime.now().date()
    days = (today - list_date).days
    return days <= config.SUB_NEW_STOCK_DAYS


def should_exclude(stock_name: str, list_date: Optional[date] = None,
                   today: date = None) -> bool:
    """综合判断是否应排除该股票"""
    if is_st_stock(stock_name):
        return True
    if list_date is not None:
        if is_new_stock(list_date, today):
            return True
        if is_sub_new_stock(list_date, today):
            return True
    return False


class StockFilter:
    """
    股票过滤器
    维护一个排除集合，用于快速判断股票是否应被剔除
    """

    def __init__(self):
        self._excluded_codes: Set[str] = set()
        self._stock_info: Dict[str, dict] = {}  # code -> {name, list_date, is_st, ...}
        self._today = datetime.now().date()

    def build_from_spot_data(self, spot_df: pd.DataFrame,
                              list_dates: Dict[str, Optional[date]] = None):
        """
        从实时行情数据构建过滤集合
        spot_df: 全量 A 股实时数据（含 stock_code, stock_name 列）
        list_dates: {股票代码: 上市日期} 映射
        """
        list_dates = list_dates or {}
        excluded = set()
        infos = {}

        for _, row in spot_df.iterrows():
            code = str(row.get("stock_code", ""))
            name = str(row.get("stock_name", ""))
            if not code:
                continue

            ld = list_dates.get(code) or row.get("list_date")
            # 确保 list_date 是 date 类型
            if isinstance(ld, str):
                try:
                    ld = datetime.strptime(ld[:10], "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    ld = None
            elif isinstance(ld, pd.Timestamp):
                ld = ld.date()

            _is_st = is_st_stock(name)
            _is_new = is_new_stock(ld, self._today)
            _is_sub_new = is_sub_new_stock(ld, self._today)

            info = {
                "stock_code": code,
                "stock_name": name,
                "list_date": ld,
                "is_st": _is_st,
                "is_new_stock": _is_new,
                "is_sub_new_stock": _is_sub_new,
            }
            infos[code] = info

            if _is_st or _is_new or _is_sub_new:
                excluded.add(code)

        self._excluded_codes = excluded
        self._stock_info = infos
        logger.info(
            f"过滤器构建完成: 总 {len(infos)} 只, "
            f"排除 {len(excluded)} 只 "
            f"(ST {sum(1 for v in infos.values() if v['is_st'])}, "
            f"新股 {sum(1 for v in infos.values() if v['is_new_stock'])}, "
            f"次新股 {sum(1 for v in infos.values() if v['is_sub_new_stock'])})"
        )

    def is_excluded(self, stock_code: str) -> bool:
        """判断股票代码是否被排除"""
        return stock_code in self._excluded_codes

    def filter_dataframe(self, df: pd.DataFrame, code_col: str = "stock_code") -> pd.DataFrame:
        """过滤 DataFrame，移除应排除的股票"""
        if df.empty or code_col not in df.columns:
            return df
        mask = ~df[code_col].astype(str).isin(self._excluded_codes)
        filtered = df[mask].copy()
        removed = len(df) - len(filtered)
        if removed > 0:
            logger.debug(f"过滤了 {removed} 只股票 (ST/新股/次新股)")
        return filtered

    def filter_records(self, records: List[dict], code_key: str = "stock_code") -> List[dict]:
        """过滤字典列表"""
        result = [r for r in records if str(r.get(code_key, "")) not in self._excluded_codes]
        removed = len(records) - len(result)
        if removed > 0:
            logger.debug(f"过滤了 {removed} 条记录 (ST/新股/次新股)")
        return result

    def get_all_infos(self) -> List[dict]:
        """获取所有股票基础信息（用于入库）"""
        return list(self._stock_info.values())

    @property
    def excluded_codes(self) -> Set[str]:
        return self._excluded_codes

    @property
    def stock_info(self) -> Dict[str, dict]:
        return self._stock_info
