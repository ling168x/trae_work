#!/usr/bin/env python3
"""
股票复盘工具 - 数据库查询与终端展示
用法:
    python query.py --date 2026-09-14              # 查看指定日期全部复盘数据
    python query.py --date 2026-09-14 --module 1   # 只看模块1(资金流入前十板块)
    python query.py --dates                        # 列出所有已有复盘日期
    python query.py --stock 000001                 # 查某只股票历史入选记录
"""
import sys
import os
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from database import DatabaseManager, ReviewDaily, SectorMoneyFlow, StockReviewResult


# ===== 终端表格格式化 =====

def print_title(title: str):
    """打印模块标题"""
    width = 70
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def print_table(headers: list, rows: list, col_widths: list = None):
    """打印格式化表格"""
    if not rows:
        print("  (暂无数据)")
        return

    # 自动计算列宽
    if col_widths is None:
        col_widths = []
        for i, h in enumerate(headers):
            max_w = len(h)
            for row in rows:
                cell = str(row[i]) if i < len(row) else ""
                # 中文字符占2宽度
                w = sum(2 if ord(c) > 127 else 1 for c in cell)
                max_w = max(max_w, w)
            col_widths.append(min(max_w + 2, 30))

    def pad_cell(text, width):
        """中文感知的填充"""
        text = str(text)
        display_w = sum(2 if ord(c) > 127 else 1 for c in text)
        padding = width - display_w
        if padding < 0:
            padding = 0
        return text + " " * padding

    # 打印表头
    header_line = "  "
    for i, h in enumerate(headers):
        header_line += pad_cell(h, col_widths[i])
    print(header_line)
    print("  " + "-" * sum(col_widths))

    # 打印数据行
    for row in rows:
        line = "  "
        for i, h in enumerate(headers):
            cell = row[i] if i < len(row) else ""
            line += pad_cell(str(cell), col_widths[i])
        print(line)


def format_amount(val):
    """格式化金额: 1.23亿 / 1234.5万"""
    if val is None:
        return "-"
    val = float(val)
    if abs(val) >= 1e8:
        return f"{val / 1e8:.2f}亿"
    elif abs(val) >= 1e4:
        return f"{val / 1e4:.1f}万"
    else:
        return f"{val:.0f}"


def format_pct(val):
    """格式化百分比"""
    if val is None:
        return "-"
    return f"{float(val):+.2f}%"


# ===== 查询函数 =====

def show_available_dates(db: DatabaseManager):
    """显示所有已有复盘日期"""
    session = db.get_session()
    try:
        records = session.query(ReviewDaily.trade_date) \
            .order_by(ReviewDaily.trade_date.desc()).limit(50).all()
        if not records:
            print("\n数据库中暂无复盘数据。")
            print("请先运行采集: python main.py")
            return
        print_title("已有复盘日期")
        for i, r in enumerate(records, 1):
            print(f"  {i:3d}. {r[0].isoformat()}")
        print(f"\n  共 {len(records)} 条记录")
    finally:
        session.close()


def show_daily_review(db: DatabaseManager, trade_date_str: str, module: int = None):
    """展示指定日期的复盘数据"""
    try:
        trade_date = datetime.strptime(trade_date_str, "%Y-%m-%d").date()
    except ValueError:
        print(f"日期格式错误: {trade_date_str}，请使用 YYYY-MM-DD")
        return

    print(f"\n{'=' * 70}")
    print(f"  复盘日期: {trade_date_str}")
    print(f"{'=' * 70}")

    modules = {
        1: ("资金流入前十板块", show_sector_inflow),
        2: ("资金流出前十板块", show_sector_outflow),
        3: ("资金流入前30股", show_stock_by_category, config.CATEGORY_STOCK_INFLOW_TOP30),
        4: ("资金流出前30股", show_stock_by_category, config.CATEGORY_STOCK_OUTFLOW_TOP30),
        5: ("异动板块及龙头个股", show_stock_by_category, config.CATEGORY_ABNORMAL_SECTOR_LEADER),
        6: ("放量MA5上穿MA10", show_stock_by_category, config.CATEGORY_VOLUME_MA5_CROSS_MA10),
        7: ("成交额前20股", show_stock_by_category, config.CATEGORY_TURNOVER_TOP20),
        8: ("近10日涨停股", show_stock_by_category, config.CATEGORY_LIMIT_UP_LAST_10_DAYS),
        9: ("下跌缩量/今日下跌放量", show_stock_by_category, config.CATEGORY_DECLINE_SHRINK_VOLUME),
    }

    if module:
        if module in modules:
            entry = modules[module]
            if len(entry) == 2:
                entry[1](db, trade_date)
            else:
                entry[1](db, trade_date, entry[2], entry[0])
        else:
            print(f"无效模块编号: {module}，有效范围 1-9")
    else:
        # 显示全部模块
        for num, entry in modules.items():
            if len(entry) == 2:
                entry[1](db, trade_date)
            else:
                entry[1](db, trade_date, entry[2], entry[0])

    # 显示统计摘要
    show_summary(db, trade_date)


def show_sector_inflow(db: DatabaseManager, trade_date):
    """显示资金流入前十板块"""
    result = db.query_sector_flows(trade_date=trade_date, flow_type="inflow", page_size=10)
    data = result.get("data", [])
    print_title("模块1: 资金流入前十板块")
    headers = ["排名", "板块名称", "净流入", "涨跌幅", "成交额"]
    rows = []
    for r in data:
        rows.append([
            r.get("rank_no", ""),
            r.get("sector_name", ""),
            format_amount(r.get("net_amount")),
            format_pct(r.get("change_percent")),
            format_amount(r.get("turnover_amount")),
        ])
    print_table(headers, rows)


def show_sector_outflow(db: DatabaseManager, trade_date):
    """显示资金流出前十板块"""
    result = db.query_sector_flows(trade_date=trade_date, flow_type="outflow", page_size=10)
    data = result.get("data", [])
    print_title("模块2: 资金流出前十板块")
    headers = ["排名", "板块名称", "净流出", "涨跌幅", "成交额"]
    rows = []
    for r in data:
        rows.append([
            r.get("rank_no", ""),
            r.get("sector_name", ""),
            format_amount(r.get("net_amount")),
            format_pct(r.get("change_percent")),
            format_amount(r.get("turnover_amount")),
        ])
    print_table(headers, rows)


def show_stock_by_category(db: DatabaseManager, trade_date, category: str, title: str = ""):
    """通用: 按分类显示个股数据"""
    # 分类对应的模块编号
    cat_num = {
        config.CATEGORY_STOCK_INFLOW_TOP30: 3,
        config.CATEGORY_STOCK_OUTFLOW_TOP30: 4,
        config.CATEGORY_ABNORMAL_SECTOR_LEADER: 5,
        config.CATEGORY_VOLUME_MA5_CROSS_MA10: 6,
        config.CATEGORY_TURNOVER_TOP20: 7,
        config.CATEGORY_LIMIT_UP_LAST_10_DAYS: 8,
        config.CATEGORY_DECLINE_SHRINK_VOLUME: 9,
    }
    num = cat_num.get(category, "")
    print_title(f"模块{num}: {title or category}")

    result = db.query_stock_results(trade_date=trade_date, category=category, page_size=50)
    data = result.get("data", [])
    total = result.get("total", 0)

    if category == config.CATEGORY_ABNORMAL_SECTOR_LEADER:
        # 异动板块特殊展示
        headers = ["板块", "个股代码", "个股名称", "净流入", "涨跌幅", "成交额"]
        rows = []
        for r in data:
            extra = r.get("extra_json", {})
            rows.append([
                r.get("sector_name", ""),
                r.get("stock_code", ""),
                r.get("stock_name", ""),
                format_amount(r.get("net_amount")),
                format_pct(r.get("change_percent")),
                format_amount(r.get("turnover_amount")),
            ])

    elif category == config.CATEGORY_LIMIT_UP_LAST_10_DAYS:
        # 涨停股特殊展示
        headers = ["代码", "名称", "板块", "涨停次数", "最近涨停", "今日涨跌"]
        rows = []
        for r in data:
            extra = r.get("extra_json", {})
            rows.append([
                r.get("stock_code", ""),
                r.get("stock_name", ""),
                r.get("sector_name", ""),
                extra.get("zt_count", ""),
                extra.get("last_zt_date", ""),
                format_pct(r.get("change_percent")),
            ])

    elif category == config.CATEGORY_VOLUME_MA5_CROSS_MA10:
        # MA交叉特殊展示
        headers = ["代码", "名称", "板块", "收盘价", "MA5", "MA10", "涨跌幅"]
        rows = []
        for r in data:
            extra = r.get("extra_json", {})
            rows.append([
                r.get("stock_code", ""),
                r.get("stock_name", ""),
                r.get("sector_name", ""),
                r.get("extra_json", {}).get("close", safe_val(r, "turnover_amount")),
                extra.get("ma5", ""),
                extra.get("ma10", ""),
                format_pct(r.get("change_percent")),
            ])

    elif category == config.CATEGORY_DECLINE_SHRINK_VOLUME:
        # 下跌缩量特殊展示
        headers = ["代码", "名称", "板块", "今日涨跌", "3日涨跌", "今日放量", "成交额"]
        rows = []
        for r in data:
            extra = r.get("extra_json", {})
            is_vol_up = "是" if extra.get("is_decline_volume_up") else "否"
            rows.append([
                r.get("stock_code", ""),
                r.get("stock_name", ""),
                r.get("sector_name", ""),
                format_pct(r.get("change_percent")),
                format_pct(extra.get("pct_3d")),
                is_vol_up,
                format_amount(r.get("turnover_amount")),
            ])

    else:
        # 通用展示
        headers = ["排名", "代码", "名称", "板块", "净流入/出", "涨跌幅", "成交额", "换手率"]
        rows = []
        for r in data:
            rows.append([
                r.get("rank_no", ""),
                r.get("stock_code", ""),
                r.get("stock_name", ""),
                r.get("sector_name", "")[:6],
                format_amount(r.get("net_amount")),
                format_pct(r.get("change_percent")),
                format_amount(r.get("turnover_amount")),
                f"{r.get('turnover_rate', 0):.1f}%" if r.get("turnover_rate") else "-",
            ])

    print_table(headers, rows)
    if total > len(data):
        print(f"  ... 共 {total} 条，已显示前 {len(data)} 条")


def safe_val(r, key, default=""):
    """安全取值"""
    v = r.get(key)
    return v if v is not None else default


def show_summary(db: DatabaseManager, trade_date):
    """显示统计摘要"""
    print_title("数据统计摘要")

    session = db.get_session()
    try:
        # 板块数据
        inflow_count = session.query(SectorMoneyFlow).filter_by(
            trade_date=trade_date, flow_type="inflow"
        ).count()
        outflow_count = session.query(SectorMoneyFlow).filter_by(
            trade_date=trade_date, flow_type="outflow"
        ).count()

        # 各分类个股数量
        categories = [
            (config.CATEGORY_STOCK_INFLOW_TOP30, "资金流入前30股"),
            (config.CATEGORY_STOCK_OUTFLOW_TOP30, "资金流出前30股"),
            (config.CATEGORY_ABNORMAL_SECTOR_LEADER, "异动板块龙头"),
            (config.CATEGORY_VOLUME_MA5_CROSS_MA10, "MA5上穿MA10"),
            (config.CATEGORY_TURNOVER_TOP20, "成交额前20"),
            (config.CATEGORY_LIMIT_UP_LAST_10_DAYS, "近10日涨停"),
            (config.CATEGORY_DECLINE_SHRINK_VOLUME, "下跌缩量/放量"),
        ]

        print(f"  资金流入板块:   {inflow_count} 条")
        print(f"  资金流出板块:   {outflow_count} 条")

        total_stocks = 0
        for cat, label in categories:
            count = session.query(StockReviewResult).filter_by(
                trade_date=trade_date, category=cat
            ).count()
            total_stocks += count
            print(f"  {label:14s}  {count} 条")

        print(f"  {'─' * 30}")
        print(f"  个股总计:       {total_stocks} 条")
    finally:
        session.close()


def show_stock_history(db: DatabaseManager, stock_code: str):
    """查询某只股票的历史入选记录"""
    result = db.query_stock_history(stock_code, page_size=50)
    data = result.get("data", [])
    total = result.get("total", 0)

    if not data:
        print(f"\n股票 {stock_code} 暂无历史入选记录。")
        return

    stock_name = data[0].get("stock_name", stock_code)
    print_title(f"股票历史入选记录: {stock_name} ({stock_code})")

    # 分类中文映射
    cat_labels = {
        config.CATEGORY_STOCK_INFLOW_TOP30: "资金流入前30",
        config.CATEGORY_STOCK_OUTFLOW_TOP30: "资金流出前30",
        config.CATEGORY_ABNORMAL_SECTOR_LEADER: "异动板块龙头",
        config.CATEGORY_VOLUME_MA5_CROSS_MA10: "MA5穿MA10",
        config.CATEGORY_TURNOVER_TOP20: "成交额前20",
        config.CATEGORY_LIMIT_UP_LAST_10_DAYS: "近10日涨停",
        config.CATEGORY_DECLINE_SHRINK_VOLUME: "下跌缩量",
    }

    headers = ["日期", "分类", "排名", "净流入/出", "涨跌幅", "成交额"]
    rows = []
    for r in data:
        rows.append([
            r.get("trade_date", ""),
            cat_labels.get(r.get("category", ""), r.get("category", "")),
            r.get("rank_no", ""),
            format_amount(r.get("net_amount")),
            format_pct(r.get("change_percent")),
            format_amount(r.get("turnover_amount")),
        ])
    print_table(headers, rows)
    if total > len(data):
        print(f"  ... 共 {total} 条，已显示前 {len(data)} 条")


# ===== 入口 =====

def main():
    parser = argparse.ArgumentParser(description="股票复盘数据查询")
    parser.add_argument("--date", "-d", type=str, help="查询日期 (YYYY-MM-DD)")
    parser.add_argument("--module", "-m", type=int, help="只看指定模块 (1-9)")
    parser.add_argument("--dates", action="store_true", help="列出所有已有复盘日期")
    parser.add_argument("--stock", "-s", type=str, help="查询某只股票历史入选记录")

    args = parser.parse_args()

    db = DatabaseManager()

    if args.dates:
        show_available_dates(db)
    elif args.stock:
        show_stock_history(db, args.stock)
    elif args.date:
        show_daily_review(db, args.date, module=args.module)
    else:
        # 无参数时显示帮助 + 已有日期
        parser.print_help()
        print()
        show_available_dates(db)


if __name__ == "__main__":
    main()
