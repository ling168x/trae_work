#!/usr/bin/env python3
"""
股票复盘工具 - 数据同步脚本
全量同步：首次运行，拉取所有股票近 1 年的日 K 线数据入库
增量更新：后续运行，只更新最近 2 天的数据

用法:
    python sync.py                  # 智能模式：自动判断全量/增量
    python sync.py --full           # 强制全量同步（约1年数据）
    python sync.py --update         # 强制增量更新（最近2天）
    python sync.py --status         # 查看同步状态
    python sync.py --days 365       # 全量同步天数（默认365）
    python sync.py --resume         # 断点续传（从上次失败处继续）
"""
import sys
import os
import time
import logging
import argparse
from datetime import datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from database import DatabaseManager
from data_fetcher import DataFetcher
from filters import StockFilter

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO"):
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%H%M%S")
    log_file = os.path.join(log_dir, f"sync_{datetime.now().strftime('%Y-%m-%d')}_{timestamp}.log")
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=config.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stderr),
            logging.FileHandler(log_file, encoding="utf-8", mode="w"),
        ],
    )
    logger.info(f"日志文件: {log_file}")


def show_status(db: DatabaseManager):
    """显示同步状态"""
    kline_count = db.get_kline_stock_count()
    latest = db.get_kline_latest_date()
    last_full = db.get_last_sync("full")
    last_incr = db.get_last_sync("incremental")

    print(f"\n{'=' * 50}")
    print(f"  数据同步状态")
    print(f"{'=' * 50}")
    print(f"  K线数据库: {kline_count} 只股票有数据")
    print(f"  最新数据日期: {latest or '无数据'}")
    print()
    if last_full:
        print(f"  上次全量同步:")
        print(f"    状态: {last_full['status']}")
        print(f"    时间: {last_full['start_time']}")
        print(f"    进度: {last_full['synced_stocks']}/{last_full['total_stocks']}")
        if last_full['failed_stocks']:
            print(f"    失败: {last_full['failed_stocks']} 只")
    else:
        print(f"  尚未执行过全量同步")
    print()
    if last_incr:
        print(f"  上次增量更新:")
        print(f"    状态: {last_incr['status']}")
        print(f"    时间: {last_incr['start_time']}")
        print(f"    更新: {last_incr['synced_stocks']} 只")
    print()


def run_full_sync(db: DatabaseManager, fetcher: DataFetcher, days: int = 365,
                   resume_from: str = None):
    """
    全量同步：拉取所有股票的历史 K 线数据
    days: 拉取最近多少天的数据
    resume_from: 断点续传，从该代码之后继续
    """
    logger.info(f"===== 开始全量同步（最近 {days} 天）=====")

    # 1. 获取全量股票列表
    logger.info("步骤1: 获取全量A股列表...")
    spot_df = fetcher.get_all_stocks_spot()
    if spot_df.empty:
        logger.error("无法获取股票列表，同步终止")
        return

    # 保存基础信息
    list_dates = fetcher.get_stock_list_dates()
    stock_filter = StockFilter()
    stock_filter.build_from_spot_data(spot_df, list_dates)
    basic_infos = stock_filter.get_all_infos()
    if basic_infos:
        db.save_stock_basic_infos(basic_infos)

    all_codes = sorted(spot_df["stock_code"].astype(str).tolist())
    total = len(all_codes)
    logger.info(f"共 {total} 只股票需要同步")

    # 断点续传：跳过已完成的
    if resume_from:
        try:
            idx = all_codes.index(resume_from)
            all_codes = all_codes[idx + 1:]
            logger.info(f"断点续传: 从 {resume_from} 之后继续，剩余 {len(all_codes)} 只")
        except ValueError:
            logger.warning(f"断点代码 {resume_from} 不在列表中，从头开始")

    # 2. 创建同步日志
    log_id = db.create_sync_log("full", total)
    synced = 0
    failed = 0
    start_time = time.time()

    # 3. 逐只拉取 K 线
    logger.info("步骤2: 开始逐只拉取K线数据...")
    for i, code in enumerate(all_codes):
        try:
            hist_df = fetcher.get_stock_history(code, days=days)
            if hist_df is not None and not hist_df.empty:
                records = hist_df.to_dict("records")
                db.save_stock_daily_quotes_bulk(code, records)
                synced += 1
            else:
                failed += 1
        except Exception as e:
            logger.debug(f"同步 {code} 失败: {e}")
            failed += 1

        # 进度日志
        done = i + 1
        if done % 50 == 0 or done == len(all_codes):
            elapsed = time.time() - start_time
            speed = done / elapsed if elapsed > 0 else 0
            eta = (len(all_codes) - done) / speed if speed > 0 else 0
            logger.info(
                f"  进度: {done}/{len(all_codes)} "
                f"(成功{synced} 失败{failed}) "
                f"速度{speed:.1f}只/秒 预计剩余{eta:.0f}秒"
            )
            # 更新同步日志
            db.update_sync_log(log_id,
                synced_stocks=synced, failed_stocks=failed,
                last_synced_code=code
            )

        # K 线熔断后跳出
        if fetcher._kline_circuit_broken:
            logger.warning("K线请求已熔断，停止同步")
            break

    # 4. 完成
    db.update_sync_log(log_id,
        status="completed", synced_stocks=synced, failed_stocks=failed,
        end_time=datetime.now(), last_synced_code=all_codes[-1] if all_codes else ""
    )
    elapsed = time.time() - start_time
    logger.info(
        f"===== 全量同步完成: 成功{synced} 失败{failed} "
        f"耗时{elapsed:.0f}秒 ====="
    )


def run_incremental_update(db: DatabaseManager, fetcher: DataFetcher, days: int = 2):
    """
    增量更新：只更新最近 N 天的数据
    适用于每日收盘后更新
    """
    logger.info(f"===== 开始增量更新（最近 {days} 天）=====")

    # 获取已有股票代码
    codes = db.get_all_stock_codes()
    if not codes:
        # 数据库没有基础信息，先获取
        logger.info("数据库无基础信息，先获取股票列表...")
        spot_df = fetcher.get_all_stocks_spot()
        if not spot_df.empty:
            list_dates = fetcher.get_stock_list_dates()
            stock_filter = StockFilter()
            stock_filter.build_from_spot_data(spot_df, list_dates)
            db.save_stock_basic_infos(stock_filter.get_all_infos())
            codes = db.get_all_stock_codes()

    if not codes:
        logger.error("无法获取股票列表，增量更新终止")
        return

    total = len(codes)
    logger.info(f"共 {total} 只股票需要更新")

    log_id = db.create_sync_log("incremental", total)
    synced = 0
    failed = 0
    start_time = time.time()

    for i, code in enumerate(sorted(codes)):
        try:
            hist_df = fetcher.get_stock_history(code, days=days + 5)
            if hist_df is not None and not hist_df.empty:
                records = hist_df.to_dict("records")
                db.save_stock_daily_quotes(code, records)
                synced += 1
            else:
                failed += 1
        except Exception:
            failed += 1

        done = i + 1
        if done % 100 == 0 or done == total:
            elapsed = time.time() - start_time
            speed = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / speed if speed > 0 else 0
            logger.info(
                f"  增量进度: {done}/{total} "
                f"(成功{synced} 失败{failed}) "
                f"预计剩余{eta:.0f}秒"
            )
            db.update_sync_log(log_id,
                synced_stocks=synced, failed_stocks=failed,
                last_synced_code=code
            )

        if fetcher._kline_circuit_broken:
            logger.warning("K线请求已熔断，停止更新")
            break

    db.update_sync_log(log_id,
        status="completed", synced_stocks=synced, failed_stocks=failed,
        end_time=datetime.now()
    )
    elapsed = time.time() - start_time
    logger.info(f"===== 增量更新完成: 成功{synced} 失败{failed} 耗时{elapsed:.0f}秒 =====")


def run_smart_sync(db: DatabaseManager, fetcher: DataFetcher):
    """
    智能模式：自动判断全量/增量
    - K线库无数据或股票数 < 100 → 全量同步
    - K线库有数据 → 增量更新最近2天
    """
    kline_count = db.get_kline_stock_count()
    latest = db.get_kline_latest_date()

    if kline_count < 100:
        logger.info(f"K线库仅 {kline_count} 只股票，执行全量同步")
        run_full_sync(db, fetcher, days=365)
    else:
        logger.info(f"K线库已有 {kline_count} 只股票，最新日期 {latest}，执行增量更新")
        run_incremental_update(db, fetcher, days=2)


def main():
    parser = argparse.ArgumentParser(description="股票数据同步工具")
    parser.add_argument("--full", action="store_true", help="强制全量同步")
    parser.add_argument("--update", action="store_true", help="强制增量更新（最近2天）")
    parser.add_argument("--status", action="store_true", help="查看同步状态")
    parser.add_argument("--resume", action="store_true", help="断点续传（从上次中断处继续）")
    parser.add_argument("--days", type=int, default=365, help="全量同步天数（默认365）")
    parser.add_argument("--log-level", "-l", type=str, default="INFO")

    args = parser.parse_args()
    setup_logging(args.log_level)

    db = DatabaseManager()
    fetcher = DataFetcher()

    if args.status:
        show_status(db)
        return

    if args.full:
        resume_from = None
        if args.resume:
            last = db.get_last_sync("full")
            if last and last.get("last_synced_code"):
                resume_from = last["last_synced_code"]
                logger.info(f"断点续传: 将从 {resume_from} 之后继续")
        run_full_sync(db, fetcher, days=args.days, resume_from=resume_from)
    elif args.update:
        run_incremental_update(db, fetcher, days=2)
    else:
        run_smart_sync(db, fetcher)


if __name__ == "__main__":
    main()
