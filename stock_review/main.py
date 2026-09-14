#!/usr/bin/env python3
"""
股票复盘工具 - CLI 入口
用法:
    python main.py                    # 采集今日数据
    python main.py --date 2026-09-12  # 采集指定日期数据
    python main.py --no-db            # 不保存到数据库，仅输出 JSON
    python main.py --pretty           # 格式化输出 JSON
"""
import sys
import os
import json
import logging
import argparse
from datetime import datetime

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import config
from database import DatabaseManager
from data_fetcher import DataFetcher
from filters import StockFilter
from collectors import ReviewCollector


def setup_logging(level: str = None):
    """初始化日志"""
    log_level = getattr(logging, (level or config.LOG_LEVEL).upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format=config.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stderr),  # 日志输出到 stderr，JSON 输出到 stdout
        ],
    )


def run_review(trade_date: str, save_to_db: bool = True, pretty: bool = False):
    """
    执行完整的复盘流程
    1. 获取股票基础信息，建立过滤器
    2. 执行 9 大采集模块
    3. 入库保存
    4. 输出 JSON
    """
    logger = logging.getLogger("main")
    logger.info(f"开始执行复盘: 日期={trade_date}, 入库={save_to_db}")

    # ===== 初始化 =====
    fetcher = DataFetcher()
    stock_filter = StockFilter()

    # ===== 步骤1: 获取基础数据，构建过滤器 =====
    logger.info("步骤1: 获取A股基础数据...")
    try:
        spot_df = fetcher.get_all_stocks_spot()
    except Exception as e:
        logger.error(f"获取A股行情失败: {e}")
        spot_df = pd.DataFrame()

    try:
        list_dates = fetcher.get_stock_list_dates()
    except Exception as e:
        logger.error(f"获取上市日期失败: {e}")
        list_dates = {}

    if not spot_df.empty:
        stock_filter.build_from_spot_data(spot_df, list_dates)
    else:
        logger.warning("A股行情数据为空，将跳过ST/新股/次新股过滤")

    # ===== 步骤2: 执行全部采集 =====
    logger.info("步骤2: 执行9大采集模块...")
    collector = ReviewCollector(fetcher, stock_filter)
    result = collector.collect_all(trade_date)

    # ===== 步骤3: 入库保存 =====
    if save_to_db:
        logger.info("步骤3: 保存数据到数据库...")
        try:
            db = DatabaseManager()

            # 保存股票基础信息
            basic_infos = stock_filter.get_all_infos()
            if basic_infos:
                db.save_stock_basic_infos(basic_infos)

            trade_date_obj = datetime.strptime(trade_date, "%Y-%m-%d").date()

            # 保存每日复盘主记录
            raw_json = json.dumps(result, ensure_ascii=False, default=str)
            db.save_daily_review(trade_date_obj, raw_json)

            # 保存板块资金流向
            if result["sector_inflow_top10"]:
                db.save_sector_flows(trade_date_obj, result["sector_inflow_top10"], "inflow")
            if result["sector_outflow_top10"]:
                db.save_sector_flows(trade_date_obj, result["sector_outflow_top10"], "outflow")

            # 保存各分类个股结果
            category_map = {
                "stock_inflow_top30": config.CATEGORY_STOCK_INFLOW_TOP30,
                "stock_outflow_top30": config.CATEGORY_STOCK_OUTFLOW_TOP30,
                "abnormal_sectors": config.CATEGORY_ABNORMAL_SECTOR_LEADER,
                "volume_ma5_cross_ma10_stocks": config.CATEGORY_VOLUME_MA5_CROSS_MA10,
                "turnover_top20_stocks": config.CATEGORY_TURNOVER_TOP20,
                "limit_up_stocks_last_10_days": config.CATEGORY_LIMIT_UP_LAST_10_DAYS,
                "decline_shrink_volume_stocks": config.CATEGORY_DECLINE_SHRINK_VOLUME,
            }

            for json_key, db_category in category_map.items():
                records = result.get(json_key, [])
                if records:
                    db.save_stock_results(trade_date_obj, records, db_category)

            logger.info("数据库保存完成!")

        except Exception as e:
            logger.error(f"数据库保存失败: {e}")
            logger.error("数据仍将以 JSON 格式输出到终端")

    # ===== 步骤4: 输出 JSON =====
    logger.info("步骤4: 输出 JSON...")

    # 统计摘要
    summary = {
        "trade_date": trade_date,
        "summary": {
            "sector_inflow_top10": len(result.get("sector_inflow_top10", [])),
            "sector_outflow_top10": len(result.get("sector_outflow_top10", [])),
            "stock_inflow_top30": len(result.get("stock_inflow_top30", [])),
            "stock_outflow_top30": len(result.get("stock_outflow_top30", [])),
            "abnormal_sectors": len(result.get("abnormal_sectors", [])),
            "volume_ma5_cross_ma10_stocks": len(result.get("volume_ma5_cross_ma10_stocks", [])),
            "turnover_top20_stocks": len(result.get("turnover_top20_stocks", [])),
            "limit_up_stocks_last_10_days": len(result.get("limit_up_stocks_last_10_days", [])),
            "decline_shrink_volume_stocks": len(result.get("decline_shrink_volume_stocks", [])),
        },
    }
    logger.info(f"采集结果摘要: {json.dumps(summary['summary'], ensure_ascii=False)}")

    # JSON 输出到 stdout
    indent = 2 if pretty else None
    output = json.dumps(result, ensure_ascii=False, indent=indent, default=str)
    print(output)

    return result


def main():
    parser = argparse.ArgumentParser(description="股票复盘数据采集工具")
    parser.add_argument(
        "--date", "-d",
        type=str,
        default=datetime.now().strftime("%Y-%m-%d"),
        help="交易日期，格式 YYYY-MM-DD（默认今天）"
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="不保存到数据库，仅输出 JSON"
    )
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="格式化输出 JSON（缩进2空格）"
    )
    parser.add_argument(
        "--log-level", "-l",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别（默认 INFO）"
    )

    args = parser.parse_args()

    # 验证日期格式
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"错误: 日期格式不正确，请使用 YYYY-MM-DD 格式", file=sys.stderr)
        sys.exit(1)

    setup_logging(args.log_level)

    try:
        run_review(
            trade_date=args.date,
            save_to_db=not args.no_db,
            pretty=args.pretty,
        )
    except KeyboardInterrupt:
        print("\n用户中断", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        logging.getLogger("main").error(f"复盘执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
