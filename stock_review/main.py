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


def setup_logging(level: str = None, trade_date: str = None):
    """初始化日志：同时输出到终端(stderr)和日志文件"""
    log_level = getattr(logging, (level or config.LOG_LEVEL).upper(), logging.INFO)

    # 创建 logs 目录
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # 日志文件名: logs/review_2026-09-14_163000.log
    timestamp = datetime.now().strftime("%H%M%S")
    date_part = trade_date or datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"review_{date_part}_{timestamp}.log")

    handlers = [
        logging.StreamHandler(sys.stderr),                          # 终端
        logging.FileHandler(log_file, encoding="utf-8", mode="w"),  # 文件
    ]

    logging.basicConfig(
        level=log_level,
        format=config.LOG_FORMAT,
        handlers=handlers,
    )
    logging.getLogger("main").info(f"日志文件: {log_file}")


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

    # ===== 步骤2: 执行全部采集（传入DB，K线优先从本地读取）=====
    logger.info("步骤2: 执行9大采集模块...")
    db = DatabaseManager() if save_to_db else None
    collector = ReviewCollector(fetcher, stock_filter, db=db)
    result = collector.collect_all(trade_date)

    # ===== 步骤3: 入库保存 =====
    if save_to_db:
        logger.info("步骤3: 保存数据到数据库...")
        try:
            if db is None:
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

    # ===== 步骤5: 生成 TXT 结果文件 =====
    try:
        generate_txt_report(result, trade_date)
    except Exception as e:
        logger.warning(f"生成TXT报告失败: {e}")

    return result


def generate_txt_report(result: dict, trade_date: str):
    """
    生成简洁的 TXT 复盘报告，只记录条件和符合条件的个股名称
    保存到 result/ 目录
    """
    project_dir = os.path.dirname(os.path.abspath(__file__))
    result_dir = os.path.join(project_dir, "result")
    os.makedirs(result_dir, exist_ok=True)

    filename = f"复盘_{trade_date}.txt"
    filepath = os.path.join(result_dir, filename)

    lines = []
    lines.append(f"{'=' * 60}")
    lines.append(f"  股票复盘结果  {trade_date}")
    lines.append(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"{'=' * 60}")

    # --- 模块1: 资金流入前十板块 ---
    lines.append("")
    lines.append(f"【1】资金流入前十板块")
    lines.append(f"  条件: 当日主力资金净流入排名前10的行业板块")
    data = result.get("sector_inflow_top10", [])
    if data:
        for r in data:
            amt = r.get("net_amount", 0)
            amt_str = f"{amt/1e8:.2f}亿" if abs(amt) >= 1e8 else f"{amt/1e4:.0f}万"
            lines.append(f"  {r.get('rank_no', '')}. {r.get('sector_name', '')}  净流入{amt_str}  涨跌{r.get('change_percent', 0):+.2f}%")
    else:
        lines.append("  (无数据)")

    # --- 模块2: 资金流出前十板块 ---
    lines.append("")
    lines.append(f"【2】资金流出前十板块")
    lines.append(f"  条件: 当日主力资金净流出排名前10的行业板块")
    data = result.get("sector_outflow_top10", [])
    if data:
        for r in data:
            amt = r.get("net_amount", 0)
            amt_str = f"{amt/1e8:.2f}亿" if abs(amt) >= 1e8 else f"{amt/1e4:.0f}万"
            lines.append(f"  {r.get('rank_no', '')}. {r.get('sector_name', '')}  净流出{amt_str}  涨跌{r.get('change_percent', 0):+.2f}%")
    else:
        lines.append("  (无数据)")

    # --- 模块3: 资金流入前30股 ---
    lines.append("")
    lines.append(f"【3】资金流入前30股")
    lines.append(f"  条件: 当日主力资金净流入排名前30 (已剔除ST/新股/次新股)")
    data = result.get("stock_inflow_top30", [])
    if data:
        names = [f"{r.get('stock_name', '')}({r.get('stock_code', '')})" for r in data]
        # 每行5个
        for i in range(0, len(names), 5):
            lines.append(f"  {', '.join(names[i:i+5])}")
    else:
        lines.append("  (无数据)")

    # --- 模块4: 资金流出前30股 ---
    lines.append("")
    lines.append(f"【4】资金流出前30股")
    lines.append(f"  条件: 当日主力资金净流出排名前30 (已剔除ST/新股/次新股)")
    data = result.get("stock_outflow_top30", [])
    if data:
        names = [f"{r.get('stock_name', '')}({r.get('stock_code', '')})" for r in data]
        for i in range(0, len(names), 5):
            lines.append(f"  {', '.join(names[i:i+5])}")
    else:
        lines.append("  (无数据)")

    # --- 模块5: 异动板块及龙头 ---
    lines.append("")
    lines.append(f"【5】今日异动板块及带领个股")
    lines.append(f"  条件: 资金净流入靠前 + 涨幅高于平均 + 板块内多股放量上涨")
    data = result.get("abnormal_sectors", [])
    if data:
        # 按板块分组
        sectors = {}
        for r in data:
            sn = r.get("sector_name", "")
            if sn not in sectors:
                sectors[sn] = []
            name = r.get("stock_name", "")
            if name and not name.startswith("[板块]"):
                sectors[sn].append(name)
        for sn, stocks in sectors.items():
            stock_str = ", ".join(stocks) if stocks else "无龙头数据"
            lines.append(f"  {sn}: {stock_str}")
    else:
        lines.append("  (无数据)")

    # --- 模块6: MA5上穿MA10 ---
    lines.append("")
    lines.append(f"【6】放量且5日线上穿10日线个股")
    lines.append(f"  条件: 今日放量(成交量>5日均量) + MA5上穿MA10 + 收盘价站上MA5")
    data = result.get("volume_ma5_cross_ma10_stocks", [])
    if data:
        names = [f"{r.get('stock_name', '')}({r.get('stock_code', '')})" for r in data]
        for i in range(0, len(names), 5):
            lines.append(f"  {', '.join(names[i:i+5])}")
    else:
        lines.append("  (无符合条件个股)")

    # --- 模块7: 成交额前20 ---
    lines.append("")
    lines.append(f"【7】成交额前20股")
    lines.append(f"  条件: 当日成交额排名前20 (已剔除ST/新股/次新股)")
    data = result.get("turnover_top20_stocks", [])
    if data:
        names = [f"{r.get('stock_name', '')}({r.get('stock_code', '')})" for r in data]
        for i in range(0, len(names), 5):
            lines.append(f"  {', '.join(names[i:i+5])}")
    else:
        lines.append("  (无数据)")

    # --- 模块8: 近10日涨停 ---
    lines.append("")
    lines.append(f"【8】近10个交易日有涨停的个股")
    lines.append(f"  条件: 最近10个交易日内出现过涨停 (已剔除ST/新股/次新股)")
    data = result.get("limit_up_stocks_last_10_days", [])
    if data:
        # 按涨停次数排序展示
        sorted_data = sorted(data, key=lambda x: x.get("extra", {}).get("zt_count", 0), reverse=True)
        for r in sorted_data[:50]:  # 最多展示50只
            extra = r.get("extra", {})
            zt_count = extra.get("zt_count", 0)
            last_zt = extra.get("last_zt_date", "")
            lines.append(f"  {r.get('stock_name', '')}({r.get('stock_code', '')})  涨停{zt_count}次  最近涨停{last_zt}")
        if len(data) > 50:
            lines.append(f"  ... 共 {len(data)} 只，仅展示前50只")
    else:
        lines.append("  (无数据)")

    # --- 模块9: 下跌缩量 ---
    lines.append("")
    lines.append(f"【9】近期下跌缩量 / 今日下跌放量个股")
    lines.append(f"  条件: 近3-5日持续下跌+成交量缩小，优先今日下跌且放量(可能见底)")
    data = result.get("decline_shrink_volume_stocks", [])
    if data:
        # 分两组：今日放量 vs 缩量
        vol_up = [r for r in data if r.get("extra", {}).get("is_decline_volume_up")]
        shrink = [r for r in data if not r.get("extra", {}).get("is_decline_volume_up")]
        if vol_up:
            lines.append(f"  [今日下跌放量] ({len(vol_up)}只):")
            names = [f"{r.get('stock_name', '')}({r.get('stock_code', '')})" for r in vol_up]
            for i in range(0, len(names), 5):
                lines.append(f"    {', '.join(names[i:i+5])}")
        if shrink:
            lines.append(f"  [持续下跌缩量] ({len(shrink)}只):")
            names = [f"{r.get('stock_name', '')}({r.get('stock_code', '')})" for r in shrink]
            for i in range(0, min(len(names), 25), 5):
                lines.append(f"    {', '.join(names[i:i+5])}")
            if len(shrink) > 25:
                lines.append(f"    ... 共 {len(shrink)} 只")
    else:
        lines.append("  (无符合条件个股)")

    # --- 统计 ---
    lines.append("")
    lines.append(f"{'=' * 60}")
    lines.append(f"  统计汇总")
    lines.append(f"{'=' * 60}")
    total = 0
    for key, label in [
        ("sector_inflow_top10", "资金流入板块"),
        ("sector_outflow_top10", "资金流出板块"),
        ("stock_inflow_top30", "资金流入前30股"),
        ("stock_outflow_top30", "资金流出前30股"),
        ("abnormal_sectors", "异动板块龙头"),
        ("volume_ma5_cross_ma10_stocks", "MA5上穿MA10"),
        ("turnover_top20_stocks", "成交额前20"),
        ("limit_up_stocks_last_10_days", "近10日涨停"),
        ("decline_shrink_volume_stocks", "下跌缩量/放量"),
    ]:
        count = len(result.get(key, []))
        total += count
        lines.append(f"  {label:16s} {count} 条")
    lines.append(f"  {'─' * 30}")
    lines.append(f"  {'总计':16s} {total} 条")
    lines.append("")

    # 写入文件
    content = "\n".join(lines)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    logging.getLogger("main").info(f"TXT报告已保存: {filepath}")


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

    setup_logging(args.log_level, trade_date=args.date)

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
