#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
四维共振选股器 v3.0
基于四维量化评分体系，从全A股中筛选出符合高胜率买入条件的标的。

数据源：
  - 股票列表 + 实时行情：新浪财经 API
  - K线历史数据：腾讯财经 API
  - 资金流向：基于换手率/成交额等指标综合评估
"""

import argparse
import json
import math
import os
import re
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

warnings.filterwarnings("ignore")

# ============================================================
# 全局配置
# ============================================================
MARKET_CAP_MIN = 30  # 最小市值（亿）
LIMIT_UP_DAYS = 10  # 涨停检测天数
LIMIT_UP_THRESHOLD = 9.5  # 涨停阈值（%）
MAX_RETRIES = 3  # 最大重试次数
REQUEST_TIMEOUT = 15  # 请求超时（秒）
REQUEST_INTERVAL = 0.3  # 请求间隔（秒）
DEFAULT_MIN_SCORE = 10  # 默认最低入选分数
DEFAULT_TOP_N = 50  # 默认输出数量
MAX_WORKERS = 20  # 并发线程数
MIN_TRADING_DAYS = 120  # 用于计算均线的最少交易日

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


# ============================================================
# 工具函数
# ============================================================
def safe_float(val, default=0.0):
    """安全转换为float，失败返回默认值。"""
    if val in (None, "", "-", "--"):
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def fmt_amount(val: float) -> str:
    """格式化金额显示。"""
    val = abs(val)
    if val >= 1e8:
        return f"{val / 1e8:.2f}亿"
    elif val >= 1e4:
        return f"{val / 1e4:.2f}万"
    return f"{val:.0f}"


def get_market_prefix(code: str) -> str:
    """根据代码判断市场前缀：sh/sz/bj。"""
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith(("0", "3")):
        return "sz"
    elif code.startswith(("4", "8")):
        return "bj"
    return "sz"


# ============================================================
# 数据获取层
# ============================================================
def fetch_all_spot() -> List[Dict[str, Any]]:
    """
    从新浪财经API分页获取全A股实时行情（含股票列表），做预筛选。
    返回股票数据字典列表，字段与统一接口对齐。
    """
    print("[1/4] 获取全A股实时行情（分页）...")
    all_stocks = []
    page = 0
    total_reported = 0

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
            if page == 0:
                total_reported = data[0].get("count", 0)
                print(f"  API报告总数: {total_reported}")
        except Exception as e:
            print(f"  [ERROR] 获取第{page + 1}页行情数据失败: {e}")
            break

        for item in items:
            if len(item) < 22:
                continue
            name = item[2] if item[2] else ""
            # 预筛选：剔除ST
            if "ST" in name.upper():
                continue
            code = item[1] if item[1] else ""
            if not code:
                continue
            # 预筛选：剔除市值<30亿（新浪mktcap单位：万元）
            mktcap = safe_float(item[19])
            if mktcap < MARKET_CAP_MIN * 10000:
                continue

            all_stocks.append({
                "code": code,
                "name": name,
                "price": safe_float(item[3]),
                "pct_chg": safe_float(item[5]),
                "open": safe_float(item[9]),
                "high": safe_float(item[10]),
                "low": safe_float(item[11]),
                "volume": safe_float(item[12]),
                "amount": safe_float(item[13]),  # 元
                "pe": safe_float(item[15]),
                "pb": safe_float(item[18]),
                "mktcap": mktcap,  # 万元
                "nmc": safe_float(item[20]),  # 万元
                "turnover": safe_float(item[21]),  # 换手率(%)
                "symbol": item[0],
            })

        if len(items) < 60:  # 新浪API每页固定60条
            break
        page += 1
        time.sleep(0.1)

    print(f"  预筛选后剩余: {len(all_stocks)} 只股票")
    return all_stocks


def fetch_kline_tencent(code: str) -> Optional[Dict[str, Any]]:
    """
    从腾讯财经API获取单只股票的K线历史数据，计算MA5/MA10/MA20/MA60、RSI，
    并检测近10日是否有涨停。
    返回: 均线/K线数据字典，失败返回None。
    """
    prefix = get_market_prefix(code)
    full_code = f"{prefix}{code}"
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={full_code},day,,,{MIN_TRADING_DAYS + 10},qfq"
    )
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
        if not klines or len(klines) < MIN_TRADING_DAYS:
            return None

        # 腾讯K线格式: [date, open, close, high, low, volume]
        closes = [safe_float(k[2]) for k in klines]
        highs = [safe_float(k[3]) for k in klines]
        lows = [safe_float(k[4]) for k in klines]
        opens = [safe_float(k[1]) for k in klines]
        dates = [k[0] for k in klines]

        # 计算均线
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20
        ma60 = sum(closes[-60:]) / 60

        # 计算RSI(14)
        deltas = closes[-15:]
        gains = [max(deltas[i] - deltas[i - 1], 0) for i in range(1, len(deltas))]
        losses = [max(deltas[i - 1] - deltas[i], 0) for i in range(1, len(deltas))]
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rsi = 100.0 if avg_loss == 0 else round(100.0 - (100.0 / (1.0 + avg_gain / avg_loss)), 2)

        # 检测近10日涨停（用每日涨跌幅近似）
        has_limit_up = False
        limit_up_date = None
        recent = klines[-LIMIT_UP_DAYS - 1:]
        for i in range(1, len(recent)):
            prev_close = safe_float(recent[i - 1][2])
            cur_close = safe_float(recent[i][2])
            if prev_close > 0:
                chg = (cur_close - prev_close) / prev_close * 100
                if chg >= LIMIT_UP_THRESHOLD:
                    has_limit_up = True
                    limit_up_date = recent[i][0]
                    break

        return {
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "ma60": ma60,
            "rsi": rsi,
            "close": closes[-1],
            "high": highs[-1],
            "low": lows[-1],
            "open": opens[-1],
            "volume": safe_float(klines[-1][5]),
            "has_limit_up": has_limit_up,
            "limit_up_date": limit_up_date,
        }

    except Exception:
        return None


# ============================================================
# 评分层
# ============================================================
def score_ma_position(ma_data: Optional[Dict]) -> int:
    """维度1：均线位置评分（满分8分）"""
    if ma_data is None:
        return 0
    price = ma_data["close"]
    ma5, ma10, ma20, ma60 = ma_data["ma5"], ma_data["ma10"], ma_data["ma20"], ma_data["ma60"]
    if price > ma5 > ma10 > ma20 > ma60:
        return 8
    elif price > ma5 > ma10 > ma20:
        return 6
    elif price > ma5 > ma10:
        return 4
    elif price > ma20:
        return 2
    return 0


def score_volume_price(item: Dict) -> int:
    """维度2：量价信号评分（满分8分）"""
    pct_chg = item.get("pct_chg", 0)
    turnover = item.get("turnover", 0)  # 换手率
    # 用换手率替代量比：换手率>5%视为放量，>3%温和放量，<1%缩量
    if pct_chg > 0 and turnover > 5:
        return 8
    elif pct_chg > 0 and turnover > 3:
        return 6
    elif pct_chg < 0 and turnover < 1:
        return 4
    elif pct_chg > 0 and turnover > 1:
        return 2
    return 0


def score_kline(ma_data: Optional[Dict]) -> int:
    """维度3：K线确认评分（满分8分）"""
    if ma_data is None:
        return 0
    close = ma_data["close"]
    open_ = ma_data["open"]
    high = ma_data["high"]
    low = ma_data["low"]
    body = close - open_
    body_pct = abs(body) / open_ * 100 if open_ > 0 else 0
    upper_shadow = high - max(close, open_)
    lower_shadow = min(close, open_) - low

    # 阳线吞没 + 长上影
    if body > 0 and body_pct > 5 and upper_shadow > body * 0.5:
        return 8
    # 锤子线 / 早晨之星
    if lower_shadow > upper_shadow * 2 and body > 0 and lower_shadow > abs(body) * 2:
        return 6
    # 大阳线 + 实体>5%
    if body > 0 and body_pct > 5:
        return 4
    # 小阳线 + 有下影线
    if body > 0 and lower_shadow > 0:
        return 2
    return 0


def score_fund_flow(item: Dict) -> int:
    """
    维度4：资金方向评分（满分8分）
    由于东方财富API不可用，使用换手率+成交额作为资金活跃度代理指标。
    """
    amount = item.get("amount", 0)  # 元
    turnover = item.get("turnover", 0)
    pct_chg = item.get("pct_chg", 0)

    # 成交额阈值：10亿/5亿
    if pct_chg > 3 and turnover > 10 and amount > 1e9:
        return 8
    elif pct_chg > 1 and turnover > 5 and amount > 5e8:
        return 6
    elif pct_chg > 0 and turnover > 3:
        return 4
    elif pct_chg > 0 and turnover > 1:
        return 2
    return 0


# ============================================================
# 过滤层
# ============================================================
def apply_filter(item: Dict) -> bool:
    """应用硬性过滤条件，返回True表示通过。"""
    name = item.get("name", "")
    if "ST" in name.upper():
        return False
    mktcap = item.get("mktcap", 0)  # 万元
    if mktcap < MARKET_CAP_MIN * 10000:
        return False
    return True


# ============================================================
# 输出层
# ============================================================
def generate_html(results: List[Dict], output_path: str):
    """生成HTML报告。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(results)

    rows_html = ""
    for i, r in enumerate(results, 1):
        dims = r["scores"]
        rows_html += f"""
        <tr>
            <td>{i}</td>
            <td>{r['name']}</td>
            <td>{r['code']}</td>
            <td class="score-total">{r['total']}</td>
            <td>{dims['ma']}</td>
            <td>{dims['volume']}</td>
            <td>{dims['kline']}</td>
            <td>{dims['fund']}</td>
            <td>{r['pct_chg']}</td>
            <td>{r['amount']}</td>
            <td>{r['turnover']}</td>
            <td>{r['mktcap']}</td>
            <td>{r['limit_up']}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>四维共振选股器 v3.0 - 扫描报告</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: "Microsoft YaHei", "PingFang SC", sans-serif; background: #f5f7fa; color: #333; }}
    .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460); color: #fff; padding: 30px 40px; text-align: center; }}
    .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
    .header .subtitle {{ font-size: 14px; opacity: 0.8; }}
    .container {{ max-width: 1400px; margin: 0 auto; padding: 20px 40px; }}
    .summary {{ display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }}
    .summary-card {{ background: #fff; border-radius: 10px; padding: 20px 30px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); flex: 1; min-width: 180px; text-align: center; }}
    .summary-card .num {{ font-size: 36px; font-weight: 700; color: #0f3460; }}
    .summary-card .label {{ font-size: 13px; color: #888; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
    th {{ background: #0f3460; color: #fff; padding: 12px 10px; font-size: 13px; text-align: center; white-space: nowrap; }}
    td {{ padding: 10px; font-size: 13px; text-align: center; border-bottom: 1px solid #eee; }}
    tr:hover {{ background: #f0f4ff; }}
    .score-total {{ font-weight: 700; font-size: 16px; color: #e74c3c; }}
    .footer {{ text-align: center; padding: 30px; color: #999; font-size: 12px; }}
    .risk-warning {{ background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 16px 20px; margin-bottom: 20px; color: #856404; font-size: 13px; line-height: 1.8; }}
</style>
</head>
<body>
<div class="header">
    <h1>四维共振选股器 v3.0</h1>
    <div class="subtitle">生成时间: {now} | 入选股票: {total} 只</div>
</div>
<div class="container">
    <div class="summary">
        <div class="summary-card"><div class="num">{total}</div><div class="label">入选股票</div></div>
        <div class="summary-card"><div class="num">{sum(1 for r in results if r['total'] >= 24)}</div><div class="label">高分标的(≥24)</div></div>
        <div class="summary-card"><div class="num">{sum(1 for r in results if r['total'] >= 16)}</div><div class="label">中高分标的(≥16)</div></div>
    </div>
    <div class="risk-warning">
        <strong>风险提示：</strong>本工具仅为辅助决策工具，不构成任何投资建议。四维评分基于历史数据，不能保证未来收益。
        近10日有涨停的股票可能处于高位，追高风险较大。投资有风险，入市需谨慎。
    </div>
    <table>
        <thead>
            <tr>
                <th>排名</th><th>名称</th><th>代码</th><th>总分</th>
                <th>均线</th><th>量价</th><th>K线</th><th>资金</th>
                <th>涨跌幅</th><th>成交额</th><th>换手率</th><th>市值</th><th>近10日涨停</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
    </table>
</div>
<div class="footer">
    <p>四维共振选股器 v3.0 | 数据源: 新浪财经 + 腾讯财经 | 开发日期: 2026-08-03</p>
    <p>本报告由程序自动生成，仅供参考，不构成投资建议。</p>
</div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  HTML报告已生成: {output_path}")


def print_console(results: List[Dict]):
    """控制台输出结果。"""
    print("\n" + "=" * 72)
    print(f"  筛选完成！共 {len(results)} 只股票入选")
    print("=" * 72)
    for i, r in enumerate(results, 1):
        dims = r["scores"]
        print(f"\n  {i:>2}. {r['name']}({r['code']})  总分:{r['total']:>2}  "
              f"均线:{dims['ma']} 量价:{dims['volume']} K线:{dims['kline']} 资金:{dims['fund']}")
        print(f"      涨幅:{r['pct_chg']}%  成交额:{r['amount']}  换手率:{r['turnover']}  市值:{r['mktcap']}")
        if r["limit_up"] and r["limit_up"] != "无":
            print(f"      近10日涨停: {r['limit_up']}")


# ============================================================
# 主流程
# ============================================================
def process_stock(stock: Dict, args) -> Optional[Dict]:
    """处理单只股票：获取K线、评分。"""
    code = stock["code"]
    name = stock["name"]

    # 获取K线数据
    ma_data = fetch_kline_tencent(code)

    # 涨停过滤
    if ma_data and not args.no_filter and not ma_data.get("has_limit_up"):
        return None

    # 四维评分
    s1 = score_ma_position(ma_data)
    s2 = score_volume_price(stock)
    s3 = score_kline(ma_data)
    s4 = score_fund_flow(stock)
    total_score = s1 + s2 + s3 + s4

    if total_score < args.min_score:
        return None

    amount = stock.get("amount", 0)
    mktcap = stock.get("mktcap", 0)
    turnover = stock.get("turnover", 0)
    limit_up_str = "无"
    if ma_data and ma_data.get("limit_up_date"):
        limit_up_str = str(ma_data["limit_up_date"])

    return {
        "code": code,
        "name": name,
        "total": total_score,
        "scores": {"ma": s1, "volume": s2, "kline": s3, "fund": s4},
        "pct_chg": f"{stock['pct_chg']:+.2f}",
        "amount": fmt_amount(amount),  # amount单位：元
        "turnover": f"{turnover:.2f}%",
        "mktcap": fmt_amount(mktcap * 10000),
        "limit_up": limit_up_str,
    }


def main():
    parser = argparse.ArgumentParser(
        description="四维共振选股器 v3.0 - 基于四维量化评分体系筛选高胜率股票"
    )
    parser.add_argument(
        "--min-score", type=int, default=DEFAULT_MIN_SCORE,
        help=f"最低入选分数（默认: {DEFAULT_MIN_SCORE}）"
    )
    parser.add_argument(
        "--top", type=int, default=DEFAULT_TOP_N,
        help=f"最大输出数量（默认: {DEFAULT_TOP_N}）"
    )
    parser.add_argument(
        "--output", type=str, default="both",
        choices=["html", "console", "both"],
        help="输出模式（默认: both）"
    )
    parser.add_argument(
        "--no-filter", action="store_true",
        help="不过滤近10日涨停条件"
    )
    parser.add_argument(
        "--workers", type=int, default=MAX_WORKERS,
        help=f"并发线程数（默认: {MAX_WORKERS}）"
    )
    args = parser.parse_args()

    print("=" * 72)
    print("  四维共振选股器 v3.0")
    print("=" * 72)

    # Step 1: 获取全A股实时行情（含预筛选）
    all_stocks = fetch_all_spot()
    if not all_stocks:
        print("  [ERROR] 未能获取行情数据，请检查网络连接。")
        return

    # Step 2: 使用线程池并发获取K线数据并评分
    print("[2/4] 计算均线与K线形态（并发）...")
    results = []
    total = len(all_stocks)
    completed = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_stock, stock, args): stock for stock in all_stocks}
        for future in as_completed(futures):
            completed += 1
            if completed % 200 == 0 or completed == 1:
                print(f"  处理进度: {completed}/{total}")
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception:
                pass

    print(f"  处理完成: {completed}/{total}")

    # 按总分降序排序
    results.sort(key=lambda x: x["total"], reverse=True)
    results = results[:args.top]

    print(f"\n[3/4] 评分与排序完成！")

    # 输出
    if args.output in ("console", "both"):
        print_console(results)

    if args.output in ("html", "both"):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        html_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            f"四维共振选股_{timestamp}.html"
        )
        generate_html(results, html_path)

    if not results:
        print("\n  未找到符合条件的股票，请降低 --min-score 参数后重试。")

    print("\n" + "=" * 72)
    print("  扫描完成！")
    print("=" * 72)


if __name__ == "__main__":
    main()