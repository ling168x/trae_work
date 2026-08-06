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

# K线缓存模块
from kline_cache import get_klines

warnings.filterwarnings("ignore")

# ============================================================
# 全局配置
# ============================================================
MARKET_CAP_MIN = 30  # 最小市值（亿）
LIMIT_UP_DAYS = 10  # 涨停检测天数
LIMIT_UP_THRESHOLD_MAIN = 9.5  # 主板涨停阈值（%）
LIMIT_UP_THRESHOLD_STAR = 19.5  # 科创/创业板涨停阈值（%）
MAX_MA5_DEVIATION = 10  # 偏离5日线最大百分比
MAX_RETRIES = 3  # 最大重试次数
REQUEST_TIMEOUT = 15  # 请求超时（秒）
REQUEST_INTERVAL = 0.3  # 请求间隔（秒）
DEFAULT_MIN_SCORE = 20  # 默认最低入选分数
DEFAULT_TOP_N = 50  # 默认输出数量
MAX_WORKERS = 5  # 并发线程数
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


def get_market_type(code: str) -> str:
    """
    判断股票市场类型。
    返回: 'star'(科创板20%), 'chinext'(创业板20%), 'main'(主板10%)
    """
    # 科创板：688开头（上海）
    if code.startswith("688"):
        return "star"
    # 创业板：300/301开头（深圳）
    if code.startswith(("300", "301")):
        return "chinext"
    return "main"


def get_limit_up_threshold(code: str) -> float:
    """根据股票代码获取涨停阈值（%）。"""
    market_type = get_market_type(code)
    if market_type in ("star", "chinext"):
        return LIMIT_UP_THRESHOLD_STAR
    return LIMIT_UP_THRESHOLD_MAIN


# ============================================================
# 数据获取层
# ============================================================
def fetch_fundamentals(code: str) -> Dict[str, Any]:
    """
    从腾讯财经API获取基本面数据（行业、PE、PB、ROE、营收、利润等）。
    """
    prefix = get_market_prefix(code)
    full_code = f"{prefix}{code}"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/stockinfo/jiankuang?code={full_code}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        data = resp.json()
        if data.get("code") != 0:
            return {}

        result = {}
        # 公司简介
        gsjj = data.get("data", {}).get("gsjj", {})
        if gsjj:
            result["industry"] = ""
            plates = gsjj.get("plate", [])
            if plates:
                result["industry"] = plates[0].get("name", "")
            result["region"] = gsjj.get("dy", "")
            result["listed_date"] = gsjj.get("riqi", "")
            result["business"] = gsjj.get("yw", "")

        # 主要财务指标
        zyzb = data.get("data", {}).get("zyzb", {})
        if zyzb:
            detail = zyzb.get("detail", {})
            result["report_date"] = zyzb.get("date", "")
            result["eps"] = detail.get("mgsy", "")  # 每股收益
            result["net_profit"] = detail.get("jlr", "")  # 净利润
            result["profit_growth"] = detail.get("jlrzzl", "")  # 净利润增长率
            result["revenue"] = detail.get("yyzsr", "")  # 营业总收入
            result["revenue_growth"] = detail.get("zsrzzl", "")  # 收入增长率
            result["bps"] = detail.get("mgjzc", "")  # 每股净资产
            result["roe"] = detail.get("jzcsyl", "")  # 净资产收益率
            result["debt_ratio"] = detail.get("zcfzl", "")  # 资产负债率
            result["pe_ttm"] = detail.get("syl", "")  # 市盈率
            result["pb_mrq"] = detail.get("sjl", "")  # 市净率

        return result
    except Exception:
        return {}
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
    获取单只股票的K线历史数据（带本地缓存），计算MA5/MA10/MA20/MA60、RSI，
    并检测近10日是否有涨停（区分科创/创业板20%与主板10%）。
    涨停判定：涨幅达到涨停阈值且尾盘封住涨停板（收盘价=涨停价）。
    返回: 均线/K线数据字典，失败返回None。
    """
    try:
        # 使用缓存模块获取K线数据
        klines = get_klines(code, min_days=MIN_TRADING_DAYS)
        if not klines or len(klines) < MIN_TRADING_DAYS:
            return None

        # 缓存返回的格式: [{"date", "open", "close", "high", "low", "volume", "amount"}, ...]
        closes = [k["close"] for k in klines]
        highs = [k["high"] for k in klines]
        lows = [k["low"] for k in klines]
        opens = [k["open"] for k in klines]
        dates = [k["date"] for k in klines]

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

        # 获取该股票的涨停阈值
        limit_up_threshold = get_limit_up_threshold(code)

        # 检测近10日涨停，且尾盘封住涨停板
        has_limit_up = False
        limit_up_date = None
        limit_up_sealed = False
        recent = klines[-LIMIT_UP_DAYS - 1:]
        for i in range(1, len(recent)):
            prev_close = recent[i - 1]["close"]
            cur_close = recent[i]["close"]
            cur_high = recent[i]["high"]
            if prev_close > 0:
                chg = (cur_close - prev_close) / prev_close * 100
                if chg >= limit_up_threshold:
                    has_limit_up = True
                    limit_up_date = recent[i]["date"]
                    limit_up_sealed = (cur_close >= cur_high - 0.001) and (cur_close >= prev_close * (1 + limit_up_threshold / 100) - 0.001)
                    break

        # 计算偏离5日线的百分比
        ma5_deviation = abs((closes[-1] - ma5) / ma5 * 100) if ma5 > 0 else 0

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
            "volume": klines[-1]["volume"],
            "has_limit_up": has_limit_up,
            "limit_up_date": limit_up_date,
            "limit_up_sealed": limit_up_sealed,
            "limit_up_threshold": limit_up_threshold,
            "ma5_deviation": round(ma5_deviation, 2),
            "market_type": get_market_type(code),
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
# 支撑位/压力位 + 买入建议
# ============================================================
def calc_support_resistance(ma_data: Optional[Dict]) -> Dict[str, Any]:
    """
    基于K线数据计算支撑位和压力位。
    支撑位：MA20、MA60、近20日最低价、近60日最低价
    压力位：MA5、MA10、近20日最高价、近60日最高价
    """
    if ma_data is None:
        return {"support": [], "resistance": [], "support_avg": 0, "resistance_avg": 0}

    close = ma_data["close"]
    ma5, ma10, ma20, ma60 = ma_data["ma5"], ma_data["ma10"], ma_data["ma20"], ma_data["ma60"]

    # 支撑位（取更低的值更保守）
    supports = sorted([ma20, ma60], reverse=True)
    # 压力位（取更高的值更保守）
    resistances = sorted([ma5, ma10])

    # 计算平均支撑/压力
    support_avg = round(sum(supports) / len(supports), 2) if supports else 0
    resistance_avg = round(sum(resistances) / len(resistances), 2) if resistances else 0

    # 计算距支撑/压力的距离百分比
    dist_to_support = round((close - support_avg) / support_avg * 100, 2) if support_avg else 0
    dist_to_resistance = round((resistance_avg - close) / close * 100, 2) if resistance_avg else 0
    # 收益风险比
    risk_reward = round(dist_to_resistance / abs(dist_to_support), 2) if dist_to_support != 0 else 0

    return {
        "supports": [f"{s:.2f}" for s in supports],
        "resistances": [f"{r:.2f}" for r in resistances],
        "support_avg": support_avg,
        "resistance_avg": resistance_avg,
        "dist_to_support": dist_to_support,
        "dist_to_resistance": dist_to_resistance,
        "risk_reward": risk_reward,
    }


def evaluate_buy(result: Dict, stock: Dict, sr: Dict, fund: Dict) -> str:
    """
    综合评估是否值得买入。
    返回: 买入建议字符串（强烈买入/建议买入/观望/谨慎/不建议）
    """
    total = result["total"]
    scores = result["scores"]
    pct_chg = stock.get("pct_chg", 0)
    pe = stock.get("pe", 0)
    pb = stock.get("pb", 0)
    risk_reward = sr.get("risk_reward", 0)
    limit_up = result.get("limit_up", "无") != "无"

    # 基本面评级
    fund_rating = ""
    if fund:
        roe_str = fund.get("roe", "")
        profit_growth = fund.get("profit_growth", "")
        debt_str = fund.get("debt_ratio", "")
        try:
            roe = safe_float(roe_str.replace("%", ""))
            debt = safe_float(debt_str.replace("%", ""))
            profit_g = safe_float(profit_growth.replace("%", ""))
            if roe > 15 and debt < 50 and profit_g > 0:
                fund_rating = "优秀"
            elif roe > 10 and debt < 70:
                fund_rating = "良好"
            elif roe > 5:
                fund_rating = "一般"
            else:
                fund_rating = "偏弱"
        except Exception:
            fund_rating = "数据不足"

    # 综合评分
    score = 0
    reasons = []

    # 四维评分贡献
    if total >= 28:
        score += 40
    elif total >= 24:
        score += 30
    elif total >= 18:
        score += 20
    elif total >= 12:
        score += 10
    else:
        score += 5

    # 均线多头排列
    if scores["ma"] >= 6:
        score += 15
        reasons.append("均线多头排列")
    elif scores["ma"] >= 4:
        score += 8

    # 量价配合
    if scores["volume"] >= 6:
        score += 10
        reasons.append("量价配合良好")

    # K线形态
    if scores["kline"] >= 6:
        score += 10
        reasons.append("K线形态强势")

    # 资金活跃
    if scores["fund"] >= 6:
        score += 10
        reasons.append("资金活跃")

    # 基本面
    if fund_rating == "优秀":
        score += 15
        reasons.append("基本面优秀")
    elif fund_rating == "良好":
        score += 10
        reasons.append("基本面良好")
    elif fund_rating == "偏弱":
        score -= 5

    # 风险收益比
    if risk_reward > 2:
        score += 10
        reasons.append("收益风险比高")
    elif risk_reward > 1:
        score += 5
    elif risk_reward < 0.5:
        score -= 5

    # 追高风险（涨停后可能高位）
    if limit_up and pct_chg > 5:
        score -= 10
        reasons.append("短期涨幅过大需谨慎")

    # 估值
    if 0 < pe < 20:
        score += 5
    elif pe > 100:
        score -= 5

    if score >= 75:
        return "强烈买入", reasons
    elif score >= 55:
        return "建议买入", reasons
    elif score >= 35:
        return "观望", reasons
    elif score >= 20:
        return "谨慎", reasons
    else:
        return "不建议", reasons


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
        buy = r.get("buy_signal", "—")
        buy_class = {
            "强烈买入": "buy-strong", "建议买入": "buy-recommend",
            "观望": "buy-watch", "谨慎": "buy-caution", "不建议": "buy-avoid"
        }.get(buy, "")
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
            <td class="{buy_class}">{buy}</td>
            <td>{r['pct_chg']}</td>
            <td>{r['amount']}</td>
            <td>{r['turnover']}</td>
            <td>{r['mktcap']}</td>
            <td>{r.get('pe','—')}</td>
            <td>{r.get('pb','—')}</td>
            <td>{r.get('roe','—')}</td>
            <td>{r.get('eps','—')}</td>
            <td>{r.get('industry','—')}</td>
            <td>{r.get('market_type','—')}</td>
            <td>{r.get('ma5_dev','—')}</td>
            <td>{r.get('support','—')}</td>
            <td>{r.get('resistance','—')}</td>
            <td>{r.get('risk_reward','—')}</td>
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
    .buy-strong {{ background: #d4edda; color: #155724; font-weight: 700; padding: 2px 8px; border-radius: 4px; }}
    .buy-recommend {{ background: #e8f5e9; color: #2e7d32; font-weight: 600; padding: 2px 8px; border-radius: 4px; }}
    .buy-watch {{ background: #fff3cd; color: #856404; padding: 2px 8px; border-radius: 4px; }}
    .buy-caution {{ background: #ffeeba; color: #d39e00; padding: 2px 8px; border-radius: 4px; }}
    .buy-avoid {{ background: #f8d7da; color: #721c24; padding: 2px 8px; border-radius: 4px; }}
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
                <th>买入建议</th>
                <th>涨跌幅</th><th>成交额</th><th>换手率</th><th>市值</th>
                <th>PE</th><th>PB</th><th>ROE</th><th>EPS</th><th>行业</th>
                <th>支撑位</th><th>压力位</th><th>收益风险比</th><th>市场类型</th><th>偏离MA5</th><th>近10日涨停(封板)</th>
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
        buy = r.get("buy_signal", "—")
        buy_icon = {"强烈买入": "[强烈买入]", "建议买入": "[建议买入]", "观望": "[观望]", "谨慎": "[谨慎]", "不建议": "[不建议]"}.get(buy, "")

        print(f"\n  {'─' * 68}")
        print(f"  {i:>2}. {r['name']}({r['code']})  {buy_icon}")
        print(f"  {'─' * 68}")
        print(f"      四维评分  总分:{r['total']:>2}  均线:{dims['ma']}  量价:{dims['volume']}  K线:{dims['kline']}  资金:{dims['fund']}")
        print(f"      行情数据  涨幅:{r['pct_chg']}%  成交额:{r['amount']}  换手率:{r['turnover']}  市值:{r['mktcap']}")
        print(f"      市场类型  {r.get('market_type','—')}  偏离5日线:{r.get('ma5_dev','—')}")
        print(f"      基本面    行业:{r.get('industry','—')}  PE:{r.get('pe','—')}  PB:{r.get('pb','—')}  ROE:{r.get('roe','—')}  EPS:{r.get('eps','—')}")
        print(f"      财务健康  净利润增长:{r.get('profit_growth','—')}  资产负债率:{r.get('debt_ratio','—')}")
        print(f"      技术位    支撑位:{r.get('support','—')}  压力位:{r.get('resistance','—')}  收益风险比:{r.get('risk_reward','—')}")
        if r.get("limit_up") and r["limit_up"] != "无":
            print(f"      涨停记录  近10日涨停: {r['limit_up']}  偏离MA5: {r.get('ma5_dev','—')}")
        reasons = r.get("buy_reasons", [])
        if reasons:
            print(f"      买入理由  {', '.join(reasons)}")


# ============================================================
# 主流程
# ============================================================
def process_stock(stock: Dict, args) -> Optional[Dict]:
    """处理单只股票：获取K线、评分、基本面、支撑压力位、买入建议。"""
    code = stock["code"]
    name = stock["name"]

    # 获取K线数据
    ma_data = fetch_kline_tencent(code)

    # 确定过滤模式（--no-filter 等同于 mode=1）
    filter_mode = getattr(args, "filter_mode", 2)
    if args.no_filter:
        filter_mode = 1

    # 模式2/3：近10天必须有过涨停且尾盘封板
    if filter_mode >= 2 and ma_data:
        if not ma_data.get("has_limit_up"):
            return None
        if not ma_data.get("limit_up_sealed"):
            return None

    # 模式3：MA5偏离<=15%，且回踩5日线，且10日线有支撑
    if filter_mode >= 3 and ma_data:
        # MA5偏离不超过15%
        if ma_data.get("ma5_deviation", 0) > 15:
            return None
        close = ma_data["close"]
        ma5 = ma_data["ma5"]
        ma10 = ma_data["ma10"]
        # 回踩5日线：收盘价距5日线在±3%以内
        if ma5 > 0:
            pullback_ratio = abs(close - ma5) / ma5 * 100
            if pullback_ratio > 3:
                return None
        # 10日线有支撑：收盘价在10日线上方或附近（下方不超过2%）
        if ma10 > 0:
            dist_to_ma10 = (close - ma10) / ma10 * 100
            if dist_to_ma10 < -2:
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
    pe = stock.get("pe", 0)
    pb = stock.get("pb", 0)
    limit_up_str = "无"
    if ma_data and ma_data.get("limit_up_date"):
        sealed_str = "封板" if ma_data.get("limit_up_sealed") else "未封板"
        market_label = {"star": "科创", "chinext": "创业板", "main": "主板"}.get(
            ma_data.get("market_type", "main"), "主板")
        threshold = ma_data.get("limit_up_threshold", 10)
        limit_up_str = f"{ma_data['limit_up_date']}({market_label}{threshold:.0f}%-{sealed_str})"

    result = {
        "code": code,
        "name": name,
        "total": total_score,
        "scores": {"ma": s1, "volume": s2, "kline": s3, "fund": s4},
        "pct_chg": f"{stock['pct_chg']:+.2f}",
        "amount": fmt_amount(amount),
        "turnover": f"{turnover:.2f}%",
        "mktcap": fmt_amount(mktcap * 10000),
        "limit_up": limit_up_str,
        "ma5_dev": f"{ma_data.get('ma5_deviation', 0):.2f}%" if ma_data else "—",
        "market_type": {"star": "科创板", "chinext": "创业板", "main": "主板"}.get(
            ma_data.get("market_type", "main") if ma_data else "main", "主板"),
        "pe": f"{pe:.2f}",
        "pb": f"{pb:.2f}",
    }

    # 计算支撑位/压力位
    sr = calc_support_resistance(ma_data)
    result["support"] = "/".join(sr["supports"]) if sr["supports"] else "—"
    result["resistance"] = "/".join(sr["resistances"]) if sr["resistances"] else "—"
    result["risk_reward"] = f"{sr['risk_reward']:.1f}"

    # 获取基本面
    fund = fetch_fundamentals(code)
    result["industry"] = fund.get("industry", "—")
    result["roe"] = fund.get("roe", "—")
    result["eps"] = fund.get("eps", "—")
    result["profit_growth"] = fund.get("profit_growth", "—")
    result["debt_ratio"] = fund.get("debt_ratio", "—")

    # 买入建议
    buy_label, buy_reasons = evaluate_buy(result, stock, sr, fund)
    result["buy_signal"] = buy_label
    result["buy_reasons"] = buy_reasons

    return result


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
        help="不过滤近10日涨停条件（等同 --filter-mode 1）"
    )
    parser.add_argument(
        "--filter-mode", type=int, default=2,
        choices=[1, 2, 3],
        help="过滤模式: 1=仅积分, 2=积分+涨停+封板, 3=积分+涨停+封板+MA5偏离15%+回踩5日线+10日线支撑"
    )
    parser.add_argument(
        "--workers", type=int, default=MAX_WORKERS,
        help=f"并发线程数（默认: {MAX_WORKERS}）"
    )
    parser.add_argument(
        "--cache-all", action="store_true",
        help="批量下载所有股票K线数据到本地缓存后退出"
    )
    parser.add_argument(
        "--cache-force", action="store_true",
        help="强制刷新K线缓存"
    )
    parser.add_argument(
        "--cache-stats", action="store_true",
        help="仅显示缓存统计信息"
    )
    args = parser.parse_args()

    # 处理缓存相关命令
    if args.cache_stats:
        from kline_cache import get_cache_stats
        stats = get_cache_stats()
        print(f"K线缓存统计: {stats['total']} 只, {stats['size_mb']} MB")
        print(f"  今日新鲜(收盘后): {stats['fresh']}  今日盘中(待刷新): {stats['stale']}  过期: {stats['old']}")
        return

    if args.cache_all:
        from kline_cache import ensure_cache
        ensure_cache(force=args.cache_force, workers=args.workers)
        return

    # 确定过滤模式
    if args.no_filter:
        args.filter_mode = 1

    mode_desc = {
        1: "仅积分，不过滤涨停",
        2: "积分 + 近10日涨停 + 尾盘封板",
        3: "积分 + 涨停 + 封板 + MA5偏离<=15% + 回踩5日线 + 10日线支撑",
    }

    print("=" * 72)
    print("  四维共振选股器 v3.0")
    print(f"  过滤模式: 模式{args.filter_mode} - {mode_desc[args.filter_mode]}")

    # 显示缓存统计
    from kline_cache import get_cache_stats
    cache_stats = get_cache_stats()
    print(f"  K线缓存: {cache_stats['total']} 只, {cache_stats.get('size_mb', 0)} MB  "
          f"新鲜:{cache_stats.get('fresh', 0)} 盘中:{cache_stats.get('stale', 0)} 过期:{cache_stats.get('old', 0)}")
    print("=" * 72)

    # Step 1: 获取全A股实时行情（含预筛选）
    all_stocks = fetch_all_spot()
    if not all_stocks:
        print("  [ERROR] 未能获取行情数据，请检查网络连接。")
        return

    # Step 2: 使用线程池并发获取K线数据并评分
    print("[2/4] 计算均线与K线形态（并发，使用本地缓存）...")
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