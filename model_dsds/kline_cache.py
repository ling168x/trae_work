#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
K线数据本地缓存模块

功能：
  - 首次运行时从腾讯财经API下载所有A股K线数据并缓存到本地JSON文件
  - 后续运行直接从本地缓存读取，大幅提升速度
  - 缓存自动按日期刷新（同一交易日不重复下载）
  - 支持增量更新（仅下载缺失或过期的股票）

缓存目录：{script_dir}/kline_cache/
文件格式：{code}.json  →  [{date, open, close, high, low, volume, amount}, ...]
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

# ============================================================
# 配置
# ============================================================
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kline_cache")
MIN_DAYS = 120  # 最少需要K线天数
MAX_DAYS = 200  # 请求K线天数
REQUEST_TIMEOUT = 15
MAX_RETRIES = 3
DOWNLOAD_WORKERS = 20  # 下载并发数

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def get_market_prefix(code: str) -> str:
    """根据代码判断市场前缀：sh/sz/bj。"""
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith(("0", "3")):
        return "sz"
    elif code.startswith(("4", "8")):
        return "bj"
    return "sz"


def get_cache_path(code: str) -> str:
    """获取某只股票缓存文件路径。"""
    return os.path.join(CACHE_DIR, f"{code}.json")


def is_cache_fresh(code: str) -> bool:
    """
    判断缓存是否新鲜（同一交易日的数据）。
    如果缓存文件不存在或不是今天更新的，返回False。
    """
    path = get_cache_path(code)
    if not os.path.exists(path):
        return False
    # 检查文件修改日期是否在今天
    mtime = os.path.getmtime(path)
    file_date = datetime.fromtimestamp(mtime).strftime("%Y%m%d")
    today = datetime.now().strftime("%Y%m%d")
    return file_date == today


def fetch_kline_from_api(code: str) -> Optional[List[Dict]]:
    """
    从腾讯财经API获取单只股票K线数据。
    返回: [{date, open, close, high, low, volume, amount}, ...]
    """
    prefix = get_market_prefix(code)
    full_code = f"{prefix}{code}"
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={full_code},day,,,{MAX_DAYS},qfq"
    )
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                return None
            stock_data = data.get("data", {}).get(full_code)
            if not stock_data:
                return None
            klines = stock_data.get("qfqday") or stock_data.get("day")
            if not klines or len(klines) < MIN_DAYS:
                return None

            # 腾讯K线格式: [date, open, close, high, low, volume]
            result = []
            for k in klines:
                if len(k) < 6:
                    continue
                result.append({
                    "date": str(k[0]),
                    "open": float(k[1]) if k[1] else 0,
                    "close": float(k[2]) if k[2] else 0,
                    "high": float(k[3]) if k[3] else 0,
                    "low": float(k[4]) if k[4] else 0,
                    "volume": float(k[5]) if k[5] else 0,
                })
            return result

        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.5)
    return None


def save_cache(code: str, klines: List[Dict]):
    """保存K线数据到本地缓存。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = get_cache_path(code)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(klines, f, ensure_ascii=False)


def load_cache(code: str) -> Optional[List[Dict]]:
    """从本地缓存读取K线数据。"""
    path = get_cache_path(code)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def get_klines(code: str, min_days: int = MIN_DAYS) -> Optional[List[Dict]]:
    """
    获取股票K线数据（优先从缓存读取）。
    如果缓存新鲜则直接返回，否则从API获取并更新缓存。
    """
    # 优先从缓存读取
    if is_cache_fresh(code):
        klines = load_cache(code)
        if klines and len(klines) >= min_days:
            return klines

    # 缓存不存在或过期，从API获取
    klines = fetch_kline_from_api(code)
    if klines and len(klines) >= min_days:
        save_cache(code, klines)
        return klines

    # API获取失败，尝试读取旧缓存
    old_cache = load_cache(code)
    if old_cache and len(old_cache) >= min_days:
        return old_cache

    return None


def download_all_klines(codes: List[str], workers: int = DOWNLOAD_WORKERS) -> Dict[str, int]:
    """
    批量下载所有股票的K线数据到本地缓存。
    返回: {"success": N, "failed": N, "total": N}
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    total = len(codes)
    success = 0
    failed = 0
    skipped = 0

    print(f"\n  [缓存] 开始下载 {total} 只股票K线数据...")
    start_time = time.time()

    def download_one(code: str, idx: int):
        nonlocal success, failed, skipped
        if is_cache_fresh(code):
            skipped += 1
            return code, True, "skipped"

        klines = fetch_kline_from_api(code)
        if klines and len(klines) >= MIN_DAYS:
            save_cache(code, klines)
            success += 1
            return code, True, "downloaded"
        else:
            failed += 1
            return code, False, "failed"

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(download_one, code, i): code
            for i, code in enumerate(codes)
        }
        for i, future in enumerate(as_completed(futures)):
            code, ok, status = future.result()
            if (i + 1) % 200 == 0 or i == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                print(f"  [缓存] 进度: {i + 1}/{total}  "
                      f"成功:{success} 失败:{failed} 已缓存:{skipped}  "
                      f"速度:{rate:.1f}只/秒")

    elapsed = time.time() - start_time
    print(f"  [缓存] 下载完成! 耗时:{elapsed:.1f}秒  "
          f"成功:{success} 失败:{failed} 已缓存:{skipped}")
    return {"success": success, "failed": failed, "skipped": skipped, "total": total}


def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息。"""
    if not os.path.exists(CACHE_DIR):
        return {"total": 0, "size_mb": 0, "fresh": 0}

    files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")]
    total_size = sum(
        os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files
    )
    fresh = 0
    today = datetime.now().strftime("%Y%m%d")
    for f in files:
        path = os.path.join(CACHE_DIR, f)
        mtime = os.path.getmtime(path)
        file_date = datetime.fromtimestamp(mtime).strftime("%Y%m%d")
        if file_date == today:
            fresh += 1

    return {
        "total": len(files),
        "size_mb": round(total_size / 1024 / 1024, 2),
        "fresh": fresh,
    }


def get_all_stock_codes() -> List[str]:
    """
    从新浪财经API获取全A股股票代码列表（用于批量下载缓存）。
    """
    all_codes = []
    page = 0
    while True:
        url = (
            "http://money.finance.sina.com.cn/d/api/openapi_proxy.php?"
            f"__s=[[%22hq%22,%22hs_a%22,%22%22,0,{page},5000]]"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if not data or len(data) == 0:
                break
            items = data[0].get("items", [])
            if not items:
                break
            for item in items:
                if len(item) < 22:
                    continue
                name = item[2] if item[2] else ""
                if "ST" in name.upper():
                    continue
                code = item[1] if item[1] else ""
                if code:
                    all_codes.append(code)
            if len(items) < 60:
                break
        except Exception:
            break
        page += 1
        time.sleep(0.1)
    return all_codes


def ensure_cache(codes: List[str] = None, workers: int = DOWNLOAD_WORKERS, force: bool = False):
    """
    确保所有股票K线数据已缓存到本地。
    如果 codes 为 None，则自动获取全A股代码列表。

    参数:
        codes: 股票代码列表（None则自动获取全A股）
        workers: 并发下载线程数
        force: 是否强制重新下载（忽略已有缓存）
    """
    if codes is None:
        print("  [缓存] 获取全A股代码列表...")
        codes = get_all_stock_codes()
        print(f"  [缓存] 共 {len(codes)} 只股票需要缓存")

    if not codes:
        print("  [缓存] 未获取到股票代码")
        return

    # 如果强制刷新，清除旧缓存
    if force and os.path.exists(CACHE_DIR):
        import shutil
        shutil.rmtree(CACHE_DIR)
        print("  [缓存] 已清除旧缓存，将重新下载全部数据")

    result = download_all_klines(codes, workers=workers)
    return result


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="K线数据缓存工具")
    parser.add_argument("--force", action="store_true", help="强制刷新所有缓存")
    parser.add_argument("--workers", type=int, default=DOWNLOAD_WORKERS, help="并发线程数")
    parser.add_argument("--stats", action="store_true", help="仅显示缓存统计")
    args = parser.parse_args()

    if args.stats:
        stats = get_cache_stats()
        print(f"缓存统计: {stats['total']} 只股票, {stats['size_mb']} MB, 今日新鲜: {stats['fresh']}")
    else:
        print("=" * 60)
        print("  K线数据缓存工具")
        print("=" * 60)
        ensure_cache(force=args.force, workers=args.workers)
        stats = get_cache_stats()
        print(f"\n  最终缓存: {stats['total']} 只, {stats['size_mb']} MB")