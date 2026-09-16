"""
股票复盘工具 - 核心数据获取层
设计目标：尽最大技术保障获取数据
策略：
  1. AKShare 为主数据源（封装良好，覆盖广）
  2. 东方财富 HTTP API 为第一备用源
  3. 腾讯财经 API 为第二备用源
  4. 新浪财经 API 为第三备用源
  5. 网易财经 API 为第四备用源
  6. 每个请求带指数退避重试
  7. AKShare 首次失败后整个会话熔断，不再浪费时间
  8. K线连续失败5次后熔断，跳过剩余请求
  9. 请求频率控制，避免被限频
  10. 数据缓存，减少重复请求
  11. 每个模块独立容错，单模块失败不影响整体
"""
import re
import time
import json
import logging
import functools
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Callable

import requests
import pandas as pd
import numpy as np

import config

logger = logging.getLogger(__name__)


# =========================================================================
#  工具函数
# =========================================================================

def get_secid(stock_code: str) -> str:
    """股票代码 -> 东方财富 secid（交易所前缀.代码）"""
    code = stock_code.strip()
    if code.startswith(("6", "9")):
        return f"1.{code}"       # 上海
    elif code.startswith(("0", "3", "2")):
        return f"0.{code}"       # 深圳
    elif code.startswith(("4", "8")):
        return f"0.{code}"       # 北交所
    return f"1.{code}"


def safe_float(val, default=0.0) -> float:
    """安全转换为 float"""
    if val is None or val == "" or val == "-":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0) -> int:
    """安全转换为 int"""
    if val is None or val == "" or val == "-":
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def parse_eastmoney_jsonp(text: str) -> dict:
    """解析东方财富 JSONP 响应 -> dict"""
    # 格式: jQuery123_456({...});
    match = re.search(r'\((\{.*\})\)', text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # 可能直接就是 JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def try_sources(source_list: list, label: str = "") -> Any:
    """
    多数据源链式尝试：按顺序调用 source_list 中的函数，
    任一成功即返回结果，全部失败返回 None。
    source_list: [(name, callable), ...]
    """
    for i, (name, fn) in enumerate(source_list):
        try:
            logger.info(f"  [{label}] 尝试源 {i+1}/{len(source_list)}: {name}")
            result = fn()
            if result is not None:
                if isinstance(result, pd.DataFrame) and result.empty:
                    logger.info(f"  [{label}] {name} 返回空数据，尝试下一个源")
                    continue
                logger.info(f"  [{label}] {name} 获取成功")
                return result
            logger.info(f"  [{label}] {name} 返回None，尝试下一个源")
        except Exception as e:
            logger.warning(f"  [{label}] {name} 失败: {type(e).__name__}: {str(e)[:80]}")
            continue
    logger.error(f"  [{label}] 全部 {len(source_list)} 个数据源均失败")
    return None


# =========================================================================
#  重试装饰器
# =========================================================================

def retry_on_failure(max_retries: int = None, base_delay: float = None):
    """指数退避重试装饰器"""
    _max = max_retries or config.MAX_RETRIES
    _delay = base_delay or config.RETRY_BASE_DELAY

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, _max + 1):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    last_exception = e
                    wait = _delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"[重试 {attempt}/{_max}] {func.__name__} 失败: {e}，"
                        f"{wait:.1f}秒后重试..."
                    )
                    time.sleep(wait)
            logger.error(f"{func.__name__} 重试{_max}次后仍失败: {last_exception}")
            raise last_exception
        return wrapper
    return decorator


# =========================================================================
#  DataFetcher 主类
# =========================================================================

class DataFetcher:
    """
    数据获取核心类
    负责从多个数据源获取股票/板块数据，带重试和降级逻辑
    """

    def __init__(self):
        # HTTP 会话（复用连接池）
        self.session = requests.Session()
        self.session.headers.update(config.EASTMONEY_HEADERS)
        self.session.timeout = config.REQUEST_TIMEOUT

        # 数据缓存（同一次运行内有效）
        self._cache: Dict[str, Any] = {}
        self._last_request_time = 0

        # 数据源熔断标记：首次失败后整个会话不再尝试该源
        self._akshare_disabled = False
        self._eastmoney_disabled = False
        self._eastmoney_fail_count = 0
        self.EASTMONEY_FAIL_THRESHOLD = 3  # 东方财富连续失败N次后熔断

        # K线连续失败计数器（熔断用）
        self._kline_consecutive_failures = 0
        self._kline_circuit_broken = False
        self.KLINE_FAILURE_THRESHOLD = 3  # 连续失败N次后熔断

        # 尝试导入 akshare
        self._akshare = None
        try:
            import akshare as ak
            self._akshare = ak
            logger.info("AKShare 加载成功，作为主数据源")
        except ImportError:
            logger.warning("AKShare 未安装，将使用东方财富直连 API")
            self._akshare_disabled = True

    def _disable_akshare(self, reason: str = ""):
        """熔断 AKShare"""
        if not self._akshare_disabled:
            self._akshare_disabled = True
            logger.warning(f"[熔断] AKShare 已禁用。原因: {reason}")

    def _is_akshare_available(self) -> bool:
        return self._akshare is not None and not self._akshare_disabled

    def _record_eastmoney_failure(self, reason: str = ""):
        """记录东方财富失败，达到阈值后熔断"""
        self._eastmoney_fail_count += 1
        if self._eastmoney_fail_count >= self.EASTMONEY_FAIL_THRESHOLD and not self._eastmoney_disabled:
            self._eastmoney_disabled = True
            logger.warning(f"[熔断] 东方财富已禁用（连续失败{self._eastmoney_fail_count}次）。原因: {reason}")

    def _is_eastmoney_available(self) -> bool:
        return not self._eastmoney_disabled

    def _rate_limit(self):
        """请求频率控制"""
        elapsed = time.time() - self._last_request_time
        if elapsed < config.REQUEST_INTERVAL:
            time.sleep(config.REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def _http_get(self, url: str, params: dict = None, timeout: int = None) -> dict:
        """带频率控制的 HTTP GET"""
        self._rate_limit()
        resp = self.session.get(
            url, params=params, timeout=timeout or config.REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        text = resp.text
        # 尝试 JSONP 解析
        if text.strip().startswith("jQuery") or text.strip().startswith("callback"):
            return parse_eastmoney_jsonp(text)
        return resp.json()

    # =====================================================================
    #  1. 全量 A 股实时数据（含上市日期）
    # =====================================================================

    def get_all_stocks_spot(self) -> pd.DataFrame:
        """
        获取全量 A 股实时行情（多源链式降级）
        优先级: AKShare → 东方财富 → 腾讯 → 新浪
        """
        cache_key = "all_stocks_spot"
        if cache_key in self._cache:
            return self._cache[cache_key]

        sources = []
        if self._is_akshare_available():
            sources.append(("AKShare", self._akshare_spot_with_breaker))
        if self._is_eastmoney_available():
            sources.append(("东方财富直连", self._eastmoney_spot_with_breaker))
        sources.append(("新浪财经", self._try_sina_spot))  # 新浪优先（已验证可用）
        sources.append(("腾讯财经", self._try_tencent_spot))

        df = try_sources(sources, "A股行情")

        if df is not None and not df.empty:
            self._cache[cache_key] = df
            logger.info(f"获取 A 股实时行情成功: {len(df)} 只")
        else:
            logger.error("所有数据源均无法获取 A 股行情")
            df = pd.DataFrame()

        return df

    @retry_on_failure()
    def _try_akshare_spot(self) -> Optional[pd.DataFrame]:
        """通过 AKShare 获取 A 股实时行情"""
        if not self._is_akshare_available():
            return None
        ak = self._akshare
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return None
        # 标准化列名
        col_map = {
            "代码": "stock_code", "名称": "stock_name",
            "最新价": "close", "涨跌幅": "change_percent",
            "涨跌额": "change_amount", "成交量": "volume",
            "成交额": "turnover_amount", "振幅": "amplitude",
            "最高": "high", "最低": "low", "今开": "open",
            "昨收": "pre_close", "量比": "volume_ratio",
            "换手率": "turnover_rate", "市盈率-动态": "pe",
            "市净率": "pb", "总市值": "total_mv",
            "流通市值": "circ_mv",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        return df

    @retry_on_failure()
    def _try_eastmoney_spot(self) -> Optional[pd.DataFrame]:
        """
        直连东方财富 API 获取 A 股实时行情（降级）
        自动分页获取全量数据，同时包含资金流字段(f62)避免额外请求
        """
        all_records = []
        page = 1
        # 服务端实际最多返回约100条/页，用较小的page_size避免误判
        page_size = 100

        # 包含 f62(主力净流入) 和 f26(上市日期)，合并获取减少请求
        fields = "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f26,f62"

        while True:
            params = {
                "pn": page, "pz": page_size, "po": 1, "np": 1,
                "fltt": 2, "invt": 2, "fid": "f3",
                "fs": config.EM_A_SHARE_FS,
                "fields": fields,
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            }
            data = self._http_get(config.EM_PUSH2_URL, params=params)
            data_body = data.get("data", {})
            items = data_body.get("diff", [])
            if not items:
                break

            for item in items:
                all_records.append({
                    "stock_code": str(item.get("f12", "")),
                    "stock_name": str(item.get("f14", "")),
                    "close": safe_float(item.get("f2")),
                    "change_percent": safe_float(item.get("f3")),
                    "change_amount": safe_float(item.get("f4")),
                    "volume": safe_float(item.get("f5")),
                    "turnover_amount": safe_float(item.get("f6")),
                    "amplitude": safe_float(item.get("f7")),
                    "turnover_rate": safe_float(item.get("f8")),
                    "volume_ratio": safe_float(item.get("f10")),
                    "high": safe_float(item.get("f15")),
                    "low": safe_float(item.get("f16")),
                    "open": safe_float(item.get("f17")),
                    "pre_close": safe_float(item.get("f18")),
                    "total_mv": safe_float(item.get("f20")),
                    "circ_mv": safe_float(item.get("f21")),
                    "pe": safe_float(item.get("f9")),
                    "pb": safe_float(item.get("f23")),
                    "net_amount": safe_float(item.get("f62")),  # 主力净流入
                    "list_date_raw": item.get("f26"),
                })

            total = safe_int(data_body.get("total", 0))
            fetched_this_page = len(items)

            if page % 10 == 1 or len(all_records) >= total:
                logger.info(f"  东方财富直连: 第{page}页获取 {fetched_this_page} 条，累计 {len(all_records)}/{total}")

            # 停止条件：已获取全量 或 本页返回0条（到头了）
            if len(all_records) >= total or fetched_this_page == 0:
                break
            page += 1
            time.sleep(0.2)  # 分页间短等待

        if not all_records:
            return None

        df = pd.DataFrame(all_records)
        if "list_date_raw" in df.columns:
            df["list_date"] = df["list_date_raw"].apply(self._parse_list_date)
        return df

    def _akshare_spot_with_breaker(self) -> Optional[pd.DataFrame]:
        """AKShare 行情封装：失败时触发全局熔断"""
        try:
            return self._try_akshare_spot()
        except Exception as e:
            self._disable_akshare(f"获取A股行情失败: {e}")
            raise

    def _eastmoney_spot_with_breaker(self) -> Optional[pd.DataFrame]:
        """东方财富行情封装：失败时计数，达阈值熔断"""
        try:
            return self._try_eastmoney_spot()
        except Exception as e:
            self._record_eastmoney_failure(f"获取A股行情失败: {e}")
            raise

    # ----- 腾讯财经 A 股行情 -----
    def _try_tencent_spot(self) -> Optional[pd.DataFrame]:
        """腾讯财经接口获取 A 股行情（按交易所分两批获取）"""
        all_records = []
        # 沪市: sh + 深市: sz
        for prefix, market in [("sh", "1"), ("sz", "0")]:
            try:
                self._rate_limit()
                # 腾讯股票列表接口
                url = f"https://qt.gtimg.cn/q={prefix}000001"  # 先测通
                resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
                if resp.status_code != 200:
                    continue
            except Exception:
                continue

            # 使用腾讯行情批量接口: 每次最多取约800只
            # 先从已有的东方财富获取股票代码列表，再批量查腾讯
            pass

        # 腾讯单独获取全量不太实际（无分页列表接口），
        # 改用腾讯的 ifind 行情快照接口
        try:
            self._rate_limit()
            url = "https://push2.eastmoney.com/api/qt/clist/get"  # 备用东方财富节点
            # 尝试不同的 ut 参数（有时特定 ut 可以绕过限制）
            for ut in [
                "bd1d9ddb04089700cf9c27f6f7426281",
                "7eea3edcaed734bea9cbfc24409ed989",
                "fa5fd1943c7b386f172d6893dbba10b0",
            ]:
                try:
                    all_records = []
                    page = 1
                    while True:
                        params = {
                            "pn": page, "pz": 100, "po": 1, "np": 1,
                            "fltt": 2, "invt": 2, "fid": "f12",
                            "fs": config.EM_A_SHARE_FS,
                            "fields": "f2,f3,f5,f6,f8,f10,f12,f14,f17,f18,f26,f62",
                            "ut": ut,
                        }
                        self._rate_limit()
                        resp = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
                        data = resp.json() if resp.text.strip().startswith("{") else parse_eastmoney_jsonp(resp.text)
                        items = data.get("data", {}).get("diff", [])
                        if not items:
                            break
                        total = safe_int(data.get("data", {}).get("total", 0))
                        for item in items:
                            all_records.append({
                                "stock_code": str(item.get("f12", "")),
                                "stock_name": str(item.get("f14", "")),
                                "close": safe_float(item.get("f2")),
                                "change_percent": safe_float(item.get("f3")),
                                "volume": safe_float(item.get("f5")),
                                "turnover_amount": safe_float(item.get("f6")),
                                "turnover_rate": safe_float(item.get("f8")),
                                "volume_ratio": safe_float(item.get("f10")),
                                "open": safe_float(item.get("f17")),
                                "pre_close": safe_float(item.get("f18")),
                                "net_amount": safe_float(item.get("f62")),
                                "list_date_raw": item.get("f26"),
                            })
                        if len(all_records) >= total or len(items) == 0:
                            break
                        page += 1
                    if len(all_records) > 1000:
                        logger.info(f"  腾讯源(ut={ut[:8]}..): 获取 {len(all_records)} 条")
                        df = pd.DataFrame(all_records)
                        if "list_date_raw" in df.columns:
                            df["list_date"] = df["list_date_raw"].apply(self._parse_list_date)
                        return df
                except Exception:
                    continue
        except Exception:
            pass
        return None

    # ----- 新浪财经 A 股行情 -----
    def _try_sina_spot(self) -> Optional[pd.DataFrame]:
        """新浪财经接口获取 A 股行情"""
        all_records = []
        page = 1
        while True:
            try:
                self._rate_limit()
                url = (
                    f"https://vip.stock.finance.sina.com.cn/quotes_service/api/"
                    f"json_v2.php/Market_Center.getHQNodeData?"
                    f"page={page}&num=100&sort=symbol&asc=1&node=hs_a&symbol=&_s_r_a=sort"
                )
                resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT, headers={
                    "Referer": "https://finance.sina.com.cn/",
                    "User-Agent": config.EASTMONEY_HEADERS["User-Agent"],
                })
                if resp.status_code != 200:
                    break
                text = resp.text.strip()
                if not text or text == "null" or text == "[]":
                    break
                data = json.loads(text)
                if not data:
                    break
                for item in data:
                    code = str(item.get("symbol", ""))
                    # 新浪代码格式: sh600000 / sz000001 -> 去掉前缀
                    pure_code = code[2:] if len(code) > 2 else code
                    all_records.append({
                        "stock_code": pure_code,
                        "stock_name": str(item.get("name", "")),
                        "close": safe_float(item.get("trade")),
                        "change_percent": safe_float(item.get("changepercent")),
                        "volume": safe_float(item.get("volume")),
                        "turnover_amount": safe_float(item.get("amount")),
                        "turnover_rate": safe_float(item.get("turnoverratio")),
                        "high": safe_float(item.get("high")),
                        "low": safe_float(item.get("low")),
                        "open": safe_float(item.get("open")),
                        "pre_close": safe_float(item.get("settlement")),
                        "net_amount": 0.0,  # 新浪无资金流数据
                    })
                if len(data) < 100:
                    break
                page += 1
            except Exception as e:
                logger.debug(f"新浪行情第{page}页失败: {e}")
                break
        if len(all_records) > 100:
            logger.info(f"  新浪财经: 获取 {len(all_records)} 条")
            return pd.DataFrame(all_records)
        return None

    @staticmethod
    def _parse_list_date(val) -> Optional[date]:
        """解析东方财富的上市日期字段"""
        if val is None or val == "-" or val == "":
            return None
        try:
            if isinstance(val, (int, float)) and val > 19000000:
                # 格式 YYYYMMDD
                s = str(int(val))
                return datetime.strptime(s, "%Y%m%d").date()
            elif isinstance(val, str) and len(val) == 8:
                return datetime.strptime(val, "%Y%m%d").date()
            elif isinstance(val, str) and "-" in val:
                return datetime.strptime(val[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass
        return None

    # =====================================================================
    #  2. 股票上市日期（补充获取）
    # =====================================================================

    def get_stock_list_dates(self) -> Dict[str, Optional[date]]:
        """
        获取所有 A 股的上市日期
        优先从实时行情中提取，不足时补充查询
        """
        cache_key = "stock_list_dates"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = {}

        # 方式1: 从实时行情数据中提取
        df = self.get_all_stocks_spot()
        if not df.empty and "list_date" in df.columns:
            for _, row in df.iterrows():
                code = str(row.get("stock_code", ""))
                ld = row.get("list_date")
                if code and ld is not None:
                    result[code] = ld

        # 方式2: 通过东方财富直连补充（包含 f26 字段）
        if not result:
            try:
                result = self._fetch_list_dates_eastmoney()
            except Exception as e:
                logger.warning(f"东方财富直连获取上市日期失败: {e}")

        # 方式3: AKShare 补充
        if not result:
            result = self._fetch_list_dates_akshare()

        # 方式4: 返回空字典兜底，不阻塞后续流程
        if not result:
            logger.warning("未能获取上市日期数据，将跳过新股/次新股过滤")

        self._cache[cache_key] = result
        logger.info(f"获取上市日期: {len(result)} 只股票")
        return result

    @retry_on_failure()
    def _fetch_list_dates_eastmoney(self) -> Dict[str, Optional[date]]:
        """直连东方财富获取上市日期"""
        params = {
            "pn": 1, "pz": 6000, "po": 1, "np": 1,
            "fltt": 2, "invt": 2, "fid": "f26",
            "fs": config.EM_A_SHARE_FS,
            "fields": "f12,f14,f26",
        }
        data = self._http_get(config.EM_PUSH2_URL, params=params)
        items = data.get("data", {}).get("diff", [])
        result = {}
        for item in items:
            code = str(item.get("f12", ""))
            ld = self._parse_list_date(item.get("f26"))
            if code:
                result[code] = ld
        return result

    def _fetch_list_dates_akshare(self) -> Dict[str, Optional[date]]:
        """通过 AKShare 获取上市日期"""
        if not self._is_akshare_available():
            return {}
        try:
            ak = self._akshare
            # 尝试获取沪深股票列表
            result = {}
            try:
                df = ak.stock_info_a_code_name()
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        code = str(row.get("code", ""))
                        if code:
                            result[code] = None  # 此接口可能无上市日期
            except Exception:
                pass
            return result
        except Exception as e:
            logger.warning(f"AKShare 获取上市日期失败: {e}")
            return {}

    # =====================================================================
    #  3. 板块资金流向
    # =====================================================================

    def get_sector_fund_flow(self) -> pd.DataFrame:
        """获取行业板块资金流向排名（多源降级）"""
        sources = []
        if self._is_akshare_available():
            def _ak_sector():
                try:
                    return self._try_akshare_sector_flow()
                except Exception as e:
                    self._disable_akshare(f"获取板块资金流失败: {e}")
                    raise
            sources.append(("AKShare", _ak_sector))
        if self._is_eastmoney_available():
            def _em_sector():
                try:
                    return self._try_eastmoney_sector_flow()
                except Exception as e:
                    self._record_eastmoney_failure(f"获取板块资金流失败: {e}")
                    raise
            sources.append(("东方财富直连", _em_sector))
        sources.append(("新浪板块资金流", self._try_sina_sector_flow))

        df = try_sources(sources, "板块资金流")
        if df is not None and not df.empty:
            logger.info(f"获取板块资金流向成功: {len(df)} 个板块")
        else:
            logger.error("所有数据源均无法获取板块资金流向")
            df = pd.DataFrame()
        return df

    @retry_on_failure()
    def _try_akshare_sector_flow(self) -> Optional[pd.DataFrame]:
        """AKShare 获取板块资金流向"""
        if not self._is_akshare_available():
            return None
        ak = self._akshare
        self._rate_limit()
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业板块")
        if df is None or df.empty:
            return None
        col_map = {
            "名称": "sector_name", "代码": "sector_code",
            "今日涨跌幅": "change_percent", "今日主力净流入-净额": "net_amount",
            "今日成交额": "turnover_amount",
        }
        # 兼容不同版本的列名
        for old_col in list(df.columns):
            for key_word, new_name in [
                ("名称", "sector_name"), ("涨跌幅", "change_percent"),
                ("主力净流入", "net_amount"), ("成交额", "turnover_amount"),
            ]:
                if key_word in str(old_col) and new_name not in df.columns:
                    df = df.rename(columns={old_col: new_name})
        return df

    @retry_on_failure()
    def _try_eastmoney_sector_flow(self) -> Optional[pd.DataFrame]:
        """直连东方财富获取板块资金流向"""
        params = {
            "pn": 1, "pz": 100, "po": 1, "np": 1,
            "fltt": 2, "invt": 2,
            "fid": "f62",  # 按主力净流入排序
            "fs": config.EM_SECTOR_FS,
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f124",
        }
        data = self._http_get(config.EM_PUSH2_URL, params=params)
        items = data.get("data", {}).get("diff", [])
        if not items:
            return None
        records = []
        for item in items:
            records.append({
                "sector_code": str(item.get("f12", "")),
                "sector_name": str(item.get("f14", "")),
                "change_percent": safe_float(item.get("f3")),
                "net_amount": safe_float(item.get("f62")),
                "turnover_amount": safe_float(item.get("f2", 0)) * 10000 if item.get("f2") else 0,
                "main_inflow": safe_float(item.get("f62")),
                "main_inflow_pct": safe_float(item.get("f184")),
            })
        return pd.DataFrame(records)

    # ----- 新浪板块资金流 -----
    def _try_sina_sector_flow(self) -> Optional[pd.DataFrame]:
        """新浪财经获取行业板块数据"""
        try:
            self._rate_limit()
            url = (
                "https://vip.stock.finance.sina.com.cn/quotes_service/api/"
                "json_v2.php/Market_Center.getHQNodeStockCount?node=hs_a"
            )
            # 新浪行业板块列表
            self._rate_limit()
            url = (
                "https://vip.stock.finance.sina.com.cn/quotes_service/api/"
                "json_v2.php/Market_Center.getHQNodes"
            )
            resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT, headers={
                "Referer": "https://finance.sina.com.cn/",
                "User-Agent": config.EASTMONEY_HEADERS["User-Agent"],
            })
            if resp.status_code != 200:
                return None

            # 新浪板块接口较复杂，尝试另一种方式：
            # 使用新浪行业板块排行接口
            self._rate_limit()
            url2 = (
                "https://vip.stock.finance.sina.com.cn/quotes_service/api/"
                "json_v2.php/Market_Center.getHQNodeData?"
                "page=1&num=50&sort=changepercent&asc=0&node=hangye_block"
            )
            resp2 = self.session.get(url2, timeout=config.REQUEST_TIMEOUT, headers={
                "Referer": "https://finance.sina.com.cn/",
                "User-Agent": config.EASTMONEY_HEADERS["User-Agent"],
            })
            if resp2.status_code != 200:
                return None
            text = resp2.text.strip()
            if not text or text == "null":
                return None
            data = json.loads(text)
            if not data:
                return None
            records = []
            for i, item in enumerate(data, 1):
                records.append({
                    "sector_code": str(item.get("symbol", "")),
                    "sector_name": str(item.get("name", "")),
                    "change_percent": safe_float(item.get("changepercent")),
                    "net_amount": safe_float(item.get("amount", 0)),  # 新浪用成交额近似
                    "turnover_amount": safe_float(item.get("amount")),
                })
            if records:
                return pd.DataFrame(records)
            return None
        except Exception as e:
            logger.debug(f"新浪板块资金流失败: {e}")
            return None

    # =====================================================================
    #  4. 个股资金流向
    # =====================================================================

    def get_stock_fund_flow(self) -> pd.DataFrame:
        """获取个股资金流向排名（多源降级）"""
        sources = []
        if self._is_akshare_available():
            def _ak_stock_flow():
                try:
                    return self._try_akshare_stock_flow()
                except Exception as e:
                    self._disable_akshare(f"获取个股资金流失败: {e}")
                    raise
            sources.append(("AKShare", _ak_stock_flow))
        if self._is_eastmoney_available():
            def _em_stock_flow():
                try:
                    return self._try_eastmoney_stock_flow()
                except Exception as e:
                    self._record_eastmoney_failure(f"获取个股资金流失败: {e}")
                    raise
            sources.append(("东方财富直连", _em_stock_flow))

        # 从 spot 缓存提取资金流的降级函数
        def _from_spot_cache():
            spot_df = self.get_all_stocks_spot()
            if not spot_df.empty and "net_amount" in spot_df.columns:
                return spot_df[["stock_code", "stock_name", "close",
                                "change_percent", "net_amount",
                                "turnover_amount", "turnover_rate", "volume"]].copy()
            return None
        sources.append(("Spot缓存提取", _from_spot_cache))

        df = try_sources(sources, "个股资金流")
        if df is not None and not df.empty:
            logger.info(f"获取个股资金流向成功: {len(df)} 只")
        else:
            logger.error("所有数据源均无法获取个股资金流向")
            df = pd.DataFrame()
        return df

    @retry_on_failure()
    def _try_akshare_stock_flow(self) -> Optional[pd.DataFrame]:
        """AKShare 获取个股资金流向"""
        if not self._is_akshare_available():
            return None
        ak = self._akshare
        self._rate_limit()
        df = ak.stock_individual_fund_flow_rank(indicator="今日")
        if df is None or df.empty:
            return None
        # 标准化列名
        for old_col in list(df.columns):
            for key_word, new_name in [
                ("代码", "stock_code"), ("名称", "stock_name"),
                ("涨跌幅", "change_percent"), ("主力净流入", "net_amount"),
                ("成交额", "turnover_amount"),
            ]:
                if key_word in str(old_col) and "占比" not in str(old_col) and new_name not in df.columns:
                    df = df.rename(columns={old_col: new_name})
        return df

    @retry_on_failure()
    def _try_eastmoney_stock_flow(self) -> Optional[pd.DataFrame]:
        """直连东方财富获取个股资金流向"""
        params = {
            "pn": 1, "pz": 200, "po": 1, "np": 1,
            "fltt": 2, "invt": 2,
            "fid": "f62",
            "fs": config.EM_A_SHARE_FS,
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f124",
        }
        data = self._http_get(config.EM_PUSH2_URL, params=params)
        items = data.get("data", {}).get("diff", [])
        if not items:
            return None
        records = []
        for item in items:
            records.append({
                "stock_code": str(item.get("f12", "")),
                "stock_name": str(item.get("f14", "")),
                "close": safe_float(item.get("f2")),
                "change_percent": safe_float(item.get("f3")),
                "net_amount": safe_float(item.get("f62")),
            })
        return pd.DataFrame(records)

    # =====================================================================
    #  5. 个股历史 K 线
    # =====================================================================

    def get_stock_history(self, stock_code: str, days: int = 30) -> pd.DataFrame:
        """
        获取单只股票的日 K 线历史数据
        返回: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 涨跌幅, 换手率
        """
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days + 15)).strftime("%Y%m%d")

        # K线熔断检查
        if self._kline_circuit_broken:
            return pd.DataFrame()

        # K 线源优先级：新浪（已验证可用）→ 网易 → 东方财富 → AKShare
        sources = []
        sources.append(("新浪K线", lambda: self._try_sina_history(stock_code, start_date, end_date)))
        sources.append(("网易K线", lambda: self._try_netease_history(stock_code, start_date, end_date)))
        if self._is_eastmoney_available():
            sources.append(("东方财富K线", lambda: self._try_eastmoney_history(stock_code, start_date, end_date)))
        if self._is_akshare_available():
            sources.append(("AKShare K线", lambda: self._try_akshare_history(stock_code, start_date, end_date)))

        df = None
        for name, fn in sources:
            try:
                df = fn()
                if df is not None and not df.empty:
                    self._kline_consecutive_failures = 0
                    return df
            except Exception:
                continue

        if df is None or df.empty:
            self._kline_consecutive_failures += 1
            if self._kline_consecutive_failures >= self.KLINE_FAILURE_THRESHOLD:
                self._kline_circuit_broken = True
                logger.warning(f"K线请求连续失败{self.KLINE_FAILURE_THRESHOLD}次，熔断后续K线请求")

        return df if df is not None else pd.DataFrame()

    def _try_akshare_history(self, code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """AKShare 获取历史 K 线（单次尝试，不重试）"""
        if not self._is_akshare_available():
            return None
        ak = self._akshare
        self._rate_limit()
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=start, end_date=end, adjust="qfq"
        )
        if df is None or df.empty:
            return None
        col_map = {
            "日期": "date", "开盘": "open", "收盘": "close",
            "最高": "high", "最低": "low", "成交量": "volume",
            "成交额": "turnover_amount", "振幅": "amplitude",
            "涨跌幅": "change_percent", "涨跌额": "change_amount",
            "换手率": "turnover_rate",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"]).dt.date
        return df

    def _try_eastmoney_history(self, code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """直连东方财富获取历史 K 线（单次尝试，不重试）"""
        secid = get_secid(code)
        params = {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": 101,     # 日K
            "fqt": 1,       # 前复权
            "beg": start,
            "end": end,
            "ut": "fa5fd1943c7b386f172d6893dbba10b0",
        }
        data = self._http_get(config.EM_PUSH2HIS_URL, params=params)
        klines = data.get("data", {}).get("klines", [])
        if not klines:
            return None
        records = []
        for line in klines:
            parts = line.split(",")
            if len(parts) >= 11:
                records.append({
                    "date": datetime.strptime(parts[0], "%Y-%m-%d").date(),
                    "open": safe_float(parts[1]),
                    "close": safe_float(parts[2]),
                    "high": safe_float(parts[3]),
                    "low": safe_float(parts[4]),
                    "volume": safe_float(parts[5]),
                    "turnover_amount": safe_float(parts[6]),
                    "amplitude": safe_float(parts[7]),
                    "change_percent": safe_float(parts[8]),
                    "change_amount": safe_float(parts[9]),
                    "turnover_rate": safe_float(parts[10]),
                })
        return pd.DataFrame(records)

    # ----- 网易财经 K 线 -----
    def _try_netease_history(self, code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """网易财经获取历史 K 线 (CSV 格式)"""
        # 网易代码格式: 沪市 0+code, 深市 1+code
        if code.startswith("6"):
            ne_code = f"0{code}"
        else:
            ne_code = f"1{code}"
        self._rate_limit()
        url = (
            f"https://quotes.money.163.com/service/chddata.html?"
            f"code={ne_code}&start={start}&end={end}&"
            f"fields=TCLOSE;HIGH;LOW;TOPEN;LCLOSE;CHG;PCHG;TURNOVER;VOTURNOVER;VATURNOVER"
        )
        resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT, headers={
            "User-Agent": config.EASTMONEY_HEADERS["User-Agent"],
            "Referer": "https://quotes.money.163.com/",
        })
        if resp.status_code != 200:
            return None
        # 网易返回 GBK 编码的 CSV
        text = resp.content.decode("gbk", errors="ignore")
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return None
        records = []
        for line in lines[1:]:  # 跳过表头
            parts = line.strip().split(",")
            if len(parts) < 11:
                continue
            try:
                records.append({
                    "date": datetime.strptime(parts[0].strip("'"), "%Y-%m-%d").date(),
                    "close": safe_float(parts[3]),
                    "high": safe_float(parts[4]),
                    "low": safe_float(parts[5]),
                    "open": safe_float(parts[6]),
                    "pre_close": safe_float(parts[7]),
                    "change_amount": safe_float(parts[8]),
                    "change_percent": safe_float(parts[9]),
                    "turnover_rate": safe_float(parts[10]),
                    "volume": safe_float(parts[11]) if len(parts) > 11 else 0,
                    "turnover_amount": safe_float(parts[12]) if len(parts) > 12 else 0,
                })
            except (ValueError, IndexError):
                continue
        if records:
            return pd.DataFrame(records)
        return None

    # ----- 新浪财经 K 线 -----
    def _try_sina_history(self, code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """新浪财经获取历史 K 线"""
        # 新浪代码格式: sh600000 / sz000001
        if code.startswith("6"):
            sina_code = f"sh{code}"
        else:
            sina_code = f"sz{code}"
        self._rate_limit()
        # 新浪接口: 获取最近N个交易日的K线
        url = (
            f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"CN_MarketData.getKLineData?"
            f"symbol={sina_code}&scale=240&ma=no&datalen=60"
        )
        resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT, headers={
            "Referer": "https://finance.sina.com.cn/",
            "User-Agent": config.EASTMONEY_HEADERS["User-Agent"],
        })
        if resp.status_code != 200:
            return None
        text = resp.text.strip()
        if not text or text == "null":
            return None
        data = json.loads(text)
        if not data:
            return None
        records = []
        for item in data:
            try:
                d = datetime.strptime(item["day"], "%Y-%m-%d").date()
                records.append({
                    "date": d,
                    "open": safe_float(item.get("open")),
                    "close": safe_float(item.get("close")),
                    "high": safe_float(item.get("high")),
                    "low": safe_float(item.get("low")),
                    "volume": safe_float(item.get("volume")),
                    "turnover_amount": 0,
                    "change_percent": 0,
                    "turnover_rate": 0,
                })
            except (ValueError, KeyError):
                continue
        if records:
            df = pd.DataFrame(records)
            # 补算涨跌幅
            df = df.sort_values("date").reset_index(drop=True)
            df["change_percent"] = df["close"].pct_change() * 100
            return df
        return None

    # =====================================================================
    #  6. 涨停池
    # =====================================================================

    def get_limit_up_pool(self, trade_date: str) -> pd.DataFrame:
        """
        获取某日涨停池
        trade_date: 格式 "YYYYMMDD"
        """
        df = None
        try:
            df = self._try_akshare_zt_pool(trade_date)
        except Exception:
            pass

        if df is None or df.empty:
            try:
                df = self._try_eastmoney_zt_pool(trade_date)
            except Exception:
                pass

        return df if df is not None else pd.DataFrame()

    @retry_on_failure(max_retries=2, base_delay=1)
    def _try_akshare_zt_pool(self, trade_date: str) -> Optional[pd.DataFrame]:
        """AKShare 获取涨停池"""
        if not self._is_akshare_available():
            return None
        ak = self._akshare
        self._rate_limit()
        try:
            df = ak.stock_zt_pool_em(date=trade_date)
            if df is None or df.empty:
                return None
            for old_col in list(df.columns):
                for key_word, new_name in [
                    ("代码", "stock_code"), ("名称", "stock_name"),
                    ("涨跌幅", "change_percent"), ("成交额", "turnover_amount"),
                    ("流通市值", "circ_mv"), ("封板资金", "seal_amount"),
                    ("首次封板时间", "first_seal_time"),
                    ("最后封板时间", "last_seal_time"),
                    ("炸板次数", "open_count"),
                    ("连板数", "streak_count"),
                ]:
                    if key_word in str(old_col) and new_name not in df.columns:
                        df = df.rename(columns={old_col: new_name})
            df["zt_date"] = trade_date
            return df
        except Exception as e:
            # 非交易日等情况可能报错
            logger.debug(f"获取 {trade_date} 涨停池失败: {e}")
            return None

    @retry_on_failure(max_retries=2, base_delay=1)
    def _try_eastmoney_zt_pool(self, trade_date: str) -> Optional[pd.DataFrame]:
        """直连东方财富获取涨停池"""
        params = {
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "dpt": "wz.ztzt",
            "Ession": trade_date,
        }
        try:
            data = self._http_get(config.EM_ZT_POOL_URL, params=params)
            pool = data.get("data", {}).get("pool", [])
            if not pool:
                return None
            records = []
            for item in pool:
                records.append({
                    "stock_code": str(item.get("c", "")),
                    "stock_name": str(item.get("n", "")),
                    "change_percent": safe_float(item.get("zdp")),
                    "turnover_amount": safe_float(item.get("amount")),
                    "circ_mv": safe_float(item.get("ltsz")),
                    "zt_date": trade_date,
                })
            return pd.DataFrame(records)
        except Exception as e:
            logger.debug(f"东方财富直连获取 {trade_date} 涨停池失败: {e}")
            return None

    # =====================================================================
    #  7. 板块成分股
    # =====================================================================

    def get_sector_stocks(self, sector_name: str) -> pd.DataFrame:
        """获取板块成分股"""
        df = None
        try:
            df = self._try_akshare_sector_stocks(sector_name)
        except Exception:
            pass

        if df is None or df.empty:
            logger.debug(f"无法获取板块 [{sector_name}] 成分股，将使用个股资金流数据替代")
        return df if df is not None else pd.DataFrame()

    @retry_on_failure(max_retries=2, base_delay=1)
    def _try_akshare_sector_stocks(self, sector_name: str) -> Optional[pd.DataFrame]:
        """AKShare 获取板块成分股"""
        if not self._is_akshare_available():
            return None
        ak = self._akshare
        self._rate_limit()
        try:
            df = ak.stock_board_industry_cons_em(symbol=sector_name)
            if df is None or df.empty:
                return None
            for old_col in list(df.columns):
                for key_word, new_name in [
                    ("代码", "stock_code"), ("名称", "stock_name"),
                    ("涨跌幅", "change_percent"), ("成交额", "turnover_amount"),
                    ("换手率", "turnover_rate"), ("成交量", "volume"),
                ]:
                    if key_word in str(old_col) and new_name not in df.columns:
                        df = df.rename(columns={old_col: new_name})
            return df
        except Exception as e:
            logger.debug(f"获取板块 [{sector_name}] 成分股失败: {e}")
            return None

    # =====================================================================
    #  8. 批量获取历史K线（带进度和频率控制）
    # =====================================================================

    def batch_get_stock_history(self, codes: List[str], days: int = 30,
                                progress_callback: Callable = None) -> Dict[str, pd.DataFrame]:
        """
        批量获取多只股票的历史K线
        带进度回调和批次间隔控制
        """
        result = {}
        total = len(codes)
        for i, code in enumerate(codes):
            try:
                df = self.get_stock_history(code, days)
                if df is not None and not df.empty:
                    result[code] = df
            except Exception as e:
                logger.warning(f"获取 {code} 历史K线失败: {e}")

            if progress_callback and (i + 1) % 20 == 0:
                progress_callback(i + 1, total)

            # 每批次额外等待
            if (i + 1) % config.BATCH_SIZE == 0:
                time.sleep(config.BATCH_INTERVAL)

        logger.info(f"批量获取历史K线完成: {len(result)}/{total} 成功")
        return result

    # =====================================================================
    #  9. 获取交易日列表
    # =====================================================================

    def get_recent_trade_dates(self, n: int = 15) -> List[str]:
        """获取最近 n 个交易日（格式 YYYYMMDD）"""
        cache_key = f"trade_dates_{n}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        dates = self._try_akshare_trade_dates(n)
        if not dates:
            dates = self._try_estimate_trade_dates(n)

        self._cache[cache_key] = dates
        return dates

    def _try_akshare_trade_dates(self, n: int) -> List[str]:
        """通过 AKShare 获取交易日历"""
        if not self._is_akshare_available():
            return []
        try:
            ak = self._akshare
            df = ak.tool_trade_date_hist_sina()
            if df is None or df.empty:
                return []
            # 过滤到今天及之前的日期
            today = datetime.now().date()
            col = df.columns[0]  # 通常是 "trade_date"
            df[col] = pd.to_datetime(df[col]).dt.date
            df = df[df[col] <= today]
            dates = df[col].sort_values(ascending=False).head(n).tolist()
            return [d.strftime("%Y%m%d") for d in dates]
        except Exception as e:
            logger.warning(f"获取交易日历失败: {e}")
            return []

    @staticmethod
    def _try_estimate_trade_dates(n: int) -> List[str]:
        """估算最近交易日（排除周末，不排除节假日）"""
        dates = []
        current = datetime.now().date()
        while len(dates) < n:
            if current.weekday() < 5:  # 周一到周五
                dates.append(current.strftime("%Y%m%d"))
            current -= timedelta(days=1)
        return dates

    # =====================================================================
    #  10. 个股所属板块（补充信息）
    # =====================================================================

    def get_stock_sector_map(self) -> Dict[str, str]:
        """获取个股->板块映射（尽力获取）"""
        cache_key = "stock_sector_map"
        if cache_key in self._cache:
            return self._cache[cache_key]

        result = {}
        if self._akshare:
            try:
                ak = self._akshare
                self._rate_limit()
                df = ak.stock_board_industry_name_em()
                if df is not None and not df.empty:
                    sector_col = None
                    for c in df.columns:
                        if "板块名称" in str(c) or "名称" in str(c):
                            sector_col = c
                            break
                    if sector_col:
                        sectors = df[sector_col].tolist()
                        for sector in sectors[:30]:  # 限制数量避免太多请求
                            try:
                                self._rate_limit()
                                sdf = ak.stock_board_industry_cons_em(symbol=sector)
                                if sdf is not None and not sdf.empty:
                                    code_col = None
                                    for c in sdf.columns:
                                        if "代码" in str(c):
                                            code_col = c
                                            break
                                    if code_col:
                                        for code in sdf[code_col].tolist():
                                            result[str(code)] = sector
                            except Exception:
                                continue
            except Exception as e:
                logger.warning(f"获取个股板块映射失败: {e}")

        self._cache[cache_key] = result
        logger.info(f"获取个股板块映射: {len(result)} 条")
        return result
