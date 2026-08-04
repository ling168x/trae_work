#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
K线数据本地缓存模块
- 缓存目录: model_dsds/kline_cache/
- 每只股票一个JSON文件: {code}.json
- 只增量获取缓存最后日期到今天之间的新数据
"""
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kline_cache")

# 请求配置
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
}
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
MIN_TRADING_DAYS = 120  # 最少缓存交易日


def _cache_path(code: str) -> str:
    """获取单只股票的缓存文件路径"""
    return os.path.join(CACHE_DIR, f"{code}.json")


def _load_cache(code: str) -> Optional[List[Dict]]:
    """
    从本地缓存文件加载K线数据
    返回格式: [{"date": "2026-07-01", "open": 10.0, "close": 10.5, "high": 10.8, "low": 9.9, "volume": 100000, "amount": 1000000}, ...]
    """
    path = _cache_path(code)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or len(data) == 0:
            return None
        return data
    except Exception:
        return None


def _save_cache(code: str, klines: List[Dict]) -> None:
    """保存K线数据到本地缓存文件"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(code)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(klines, f, ensure_ascii=False)
    except Exception:
        pass


def _fetch_klines_from_api(code: str, lmt: int = 200) -> Optional[List[str]]:
    """
    从东方财富API获取原始K线字符串列表
    格式: ["日期,开盘,收盘,最高,最低,成交量,成交额", ...]
    """
    # 东方财富secid前缀：上海=1, 深圳/北京=0
    if code.startswith("6"):
        secid = f"1.{code}"
    else:
        secid = f"0.{code}"
    url = (
        "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57"
        f"&klt=101&fqt=1&end=20500101&lmt={lmt}"
    )
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            klines_raw = data.get("data", {}).get("klines", [])
            if klines_raw:
                return klines_raw
            return None
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None
    return None


def _parse_kline_str(kline_str: str) -> Dict:
    """将API返回的K线字符串解析为字典"""
    parts = kline_str.split(",")
    return {
        "date": parts[0],
        "open": float(parts[1]),
        "close": float(parts[2]),
        "high": float(parts[3]),
        "low": float(parts[4]),
        "volume": float(parts[5]) if len(parts) > 5 else 0,
        "amount": float(parts[6]) if len(parts) > 6 else 0,
    }


def _merge_klines(cached: List[Dict], new_raw: List[str]) -> List[Dict]:
    """
    合并缓存数据和新增数据，去重（以日期为key），按日期排序
    """
    # 构建已有日期集合
    existing_dates = {k["date"] for k in cached}
    
    # 解析新数据并过滤已存在的日期
    merged = list(cached)
    for raw in new_raw:
        parsed = _parse_kline_str(raw)
        if parsed["date"] not in existing_dates:
            merged.append(parsed)
            existing_dates.add(parsed["date"])
    
    # 按日期排序
    merged.sort(key=lambda x: x["date"])
    return merged


def get_klines(code: str, min_days: int = MIN_TRADING_DAYS) -> Optional[List[Dict]]:
    """
    获取股票K线数据（带本地缓存）
    1. 先读本地缓存
    2. 如果缓存足够且包含今天的数据，直接返回
    3. 否则只增量获取缺失部分，合并后保存并返回
    
    Args:
        code: 股票代码（如 600000）
        min_days: 最少需要的交易日数
        
    Returns:
        K线数据列表 [{"date", "open", "close", "high", "low", "volume", "amount"}, ...]
        失败返回None
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 1. 加载本地缓存
    cached = _load_cache(code)
    
    # 2. 判断是否需要增量更新
    need_fetch = False
    fetch_lmt = min_days + 10  # 默认获取数量
    
    if cached is None:
        # 无缓存，全量获取
        need_fetch = True
        fetch_lmt = min_days + 10
    else:
        last_date = cached[-1]["date"]
        if last_date >= today_str:
            # 缓存已是最新，检查数量是否足够
            if len(cached) >= min_days:
                return cached
            else:
                # 数据不够，需要获取更多
                need_fetch = True
                fetch_lmt = min_days + 10
        else:
            # 缓存不是最新，增量获取
            need_fetch = True
            # 只获取缺失的天数（加一些缓冲）
            days_gap = (datetime.now() - datetime.strptime(last_date, "%Y-%m-%d")).days
            fetch_lmt = max(days_gap + 5, 20)  # 至少获取20天
    
    if not need_fetch:
        return cached
    
    # 3. 从API获取数据
    new_raw = _fetch_klines_from_api(code, lmt=fetch_lmt)
    if new_raw is None:
        # API失败，如果有缓存就用缓存
        if cached and len(cached) >= min_days:
            return cached
        return None
    
    # 4. 合并数据
    if cached:
        merged = _merge_klines(cached, new_raw)
    else:
        merged = [_parse_kline_str(raw) for raw in new_raw]
        merged.sort(key=lambda x: x["date"])
    
    # 5. 保存到缓存
    _save_cache(code, merged)
    
    # 6. 返回足够数量的数据（截取最后 min_days+10 条）
    if len(merged) < min_days:
        return None
    return merged[-(min_days + 10):]


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    if not os.path.exists(CACHE_DIR):
        return {"total": 0, "dir": CACHE_DIR}
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")]
    total_size = sum(
        os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files
    )
    return {
        "total": len(files),
        "dir": CACHE_DIR,
        "size_mb": round(total_size / 1024 / 1024, 2),
    }


def clear_cache():
    """清空缓存目录"""
    if not os.path.exists(CACHE_DIR):
        return
    for f in os.listdir(CACHE_DIR):
        if f.endswith(".json"):
            os.remove(os.path.join(CACHE_DIR, f))
