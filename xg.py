#!/usr/bin/env python3
"""
五维共振选股器 v2.0
Five-Dimensional Resonance Stock Scanner

筛选条件：
  维度1 - 均线位置：乖离率合理，均线多头或拐头 (满分8)
  维度2 - 量价信号：缩量企稳或温和放量 (满分8)
  维度3 - K线确认：温和波动，非涨停跌停，RSI合理 (满分8)
  维度4 - 资金方向：主力净流入为正 (满分8)
  维度5 - 回购增持：公司回购+股东增持，基本面安全垫 (满分8)
  过滤：剔除ST股，市值>30亿

用法：
  python five_dim_scanner.py [--output html|json|both] [--min-score 10] [--min-dim 2]
"""

import argparse
import json
import os
import sys
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

# ========== 配置 ==========
MCP_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    ".skills/skill_quant-stock-analysis/scripts/quant_stock.py"
)
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ========== 第五维度：回购+增持数据库 ==========
# 数据来源：证券时报、上海证券报等公开公告（2026年7月下旬-8月）
# 更新时间：2026-08-03
BUYBACK_DB = {
    # ===== 回购金额>10亿（大额回购） =====
    "300750.SZ": {  # 宁德时代
        "name": "宁德时代", "buyback": True, "amount_max": 400, "amount_min": 200,
        "cancel": True, "double": False, "shareholder_add": False,
        "note": "拟回购200-400亿注销，刷新A股单次回购纪录"
    },
    "300308.SZ": {  # 中际旭创
        "name": "中际旭创", "buyback": True, "amount_max": 80, "amount_min": 40,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "拟回购40-80亿，回购金额历史前列"
    },
    "603986.SH": {  # 兆易创新
        "name": "兆易创新", "buyback": True, "amount_max": 20, "amount_min": 10,
        "cancel": True, "double": True, "shareholder_add": True,
        "note": "拟回购10-20亿注销 + 实控人增持≥10亿 + 锁仓承诺12个月"
    },
    "601138.SH": {  # 工业富联
        "name": "工业富联", "buyback": True, "amount_max": 20, "amount_min": 10,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "拟回购10-20亿"
    },
    "002475.SZ": {  # 立讯精密
        "name": "立讯精密", "buyback": True, "amount_max": 20, "amount_min": 10,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "拟回购10-20亿"
    },

    # ===== 回购金额5-10亿 =====
    "300274.SZ": {  # 阳光电源
        "name": "阳光电源", "buyback": True, "amount_max": 10, "amount_min": 5,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "拟回购5-10亿"
    },
    "600406.SH": {  # 国电南瑞
        "name": "国电南瑞", "buyback": True, "amount_max": 10, "amount_min": 5,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "拟回购5-10亿"
    },
    "000725.SZ": {  # 京东方A
        "name": "京东方A", "buyback": True, "amount_max": 10, "amount_min": 5,
        "cancel": True, "double": True, "shareholder_add": True,
        "note": "拟回购5-10亿注销 + 股东增持均>1亿"
    },
    "300408.SZ": {  # 三环集团
        "name": "三环集团", "buyback": True, "amount_max": 10, "amount_min": 5,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "拟5-10亿回购，一期8.95亿已完成，二期启动"
    },

    # ===== 回购金额3-5亿 =====
    "300001.SZ": {  # 特锐德
        "name": "特锐德", "buyback": True, "amount_max": 6, "amount_min": 3,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "拟3-6亿回购用于股权激励"
    },
    "300017.SZ": {  # 网宿科技
        "name": "网宿科技", "buyback": True, "amount_max": 6, "amount_min": 3,
        "cancel": True, "double": False, "shareholder_add": False,
        "note": "拟3-6亿回购全部注销"
    },

    # ===== 回购金额1-3亿 =====
    "300223.SZ": {  # 北京君正
        "name": "北京君正", "buyback": True, "amount_max": 2, "amount_min": 1,
        "cancel": False, "double": False, "shareholder_add": True,
        "note": "控股股东提议1-2亿回购"
    },
    "000967.SZ": {  # 盈峰环境
        "name": "盈峰环境", "buyback": True, "amount_max": 2, "amount_min": 1,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "拟1-2亿回购，含专项贷款资金"
    },
    "002517.SZ": {  # 恺英网络
        "name": "恺英网络", "buyback": True, "amount_max": 3, "amount_min": 1,
        "cancel": False, "double": True, "shareholder_add": True,
        "note": "年内回购>1亿 + 重要股东净增持>1亿"
    },
    "605208.SH": {  # 永茂泰
        "name": "永茂泰", "buyback": True, "amount_max": 3, "amount_min": 1.5,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "董事长提议1.5-3亿回购"
    },
    "300489.SZ": {  # 光智科技
        "name": "光智科技", "buyback": False, "amount_max": 0, "amount_min": 0,
        "cancel": False, "double": True, "shareholder_add": True,
        "note": "控股股东12个月不减持 + 高管增持1200-2200万"
    },
    "300925.SZ": {  # 法本信息
        "name": "法本信息", "buyback": True, "amount_max": 0.6, "amount_min": 0.3,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "拟3000-6000万回购"
    },

    # ===== 回购金额<1亿 =====
    "300222.SZ": {  # 科大智能
        "name": "科大智能", "buyback": True, "amount_max": 1, "amount_min": 0.5,
        "cancel": True, "double": False, "shareholder_add": False,
        "note": "拟5000万-1亿回购注销"
    },
    "301186.SZ": {  # 超达装备
        "name": "超达装备", "buyback": True, "amount_max": 1, "amount_min": 0.5,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "回购上调至5000万-1亿"
    },

    # ===== 有回购公告但金额待确认 =====
    "002230.SZ": {  # 科大讯飞
        "name": "科大讯飞", "buyback": True, "amount_max": 0, "amount_min": 0,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "已发布回购方案"
    },
    "688525.SH": {  # 佰维存储
        "name": "佰维存储", "buyback": True, "amount_max": 0, "amount_min": 0,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "已发布回购方案"
    },
    "301308.SZ": {  # 江波龙
        "name": "江波龙", "buyback": True, "amount_max": 0, "amount_min": 0,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "已发布回购方案"
    },
    "688111.SH": {  # 金山办公
        "name": "金山办公", "buyback": True, "amount_max": 0, "amount_min": 0,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "已发布回购方案"
    },
    "603160.SH": {  # 汇顶科技
        "name": "汇顶科技", "buyback": True, "amount_max": 0, "amount_min": 0,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "年内回购>1亿"
    },
    "601222.SH": {  # 林洋能源
        "name": "林洋能源", "buyback": True, "amount_max": 0, "amount_min": 0,
        "cancel": False, "double": False, "shareholder_add": False,
        "note": "年内回购>1亿"
    },
    "002643.SZ": {  # 万润股份
        "name": "万润股份", "buyback": False, "amount_max": 0, "amount_min": 0,
        "cancel": False, "double": False, "shareholder_add": True,
        "note": "重要股东净增持>1亿"
    },
}


# ========== MCP查询 ==========
def query_mcp(demand: str, timeout: int = 120) -> Optional[List[Dict]]:
    """调用MCP获取股票数据，返回data列表"""
    try:
        result = subprocess.run(
            ["python", MCP_SCRIPT, "-d", demand],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            print(f"  [WARN] MCP返回非零退出码: {result.stderr[:200]}")
            return None

        parsed = json.loads(result.stdout)
        if parsed.get("status") != "success":
            print(f"  [WARN] MCP状态异常: {parsed.get('error', 'unknown')[:200]}")
            return None

        content = parsed.get("content", "")
        data = _extract_data(content)
        return data

    except subprocess.TimeoutExpired:
        print("  [WARN] MCP查询超时")
        return None
    except Exception as e:
        print(f"  [WARN] MCP查询异常: {e}")
        return None


def _extract_data(content: str) -> List[Dict]:
    """从MCP返回内容中提取data列表"""
    try:
        obj = json.loads(content)
        if isinstance(obj, dict) and "data" in obj:
            return obj["data"]
        if isinstance(obj, list):
            return obj
    except json.JSONDecodeError:
        pass

    import re
    json_match = re.search(r'\{.*"data".*\}', content, re.DOTALL)
    if json_match:
        try:
            obj = json.loads(json_match.group())
            return obj.get("data", [])
        except json.JSONDecodeError:
            pass

    try:
        obj = eval(content)
        if isinstance(obj, dict):
            inner = obj.get("text", "")
            inner_obj = json.loads(inner) if isinstance(inner, str) else inner
            if isinstance(inner_obj, dict) and "data" in inner_obj:
                return inner_obj["data"]
        if isinstance(obj, list):
            return obj
    except:
        pass

    print(f"  [WARN] 无法解析MCP返回数据，前200字符: {content[:200]}")
    return []


# ========== 工具函数 ==========
def safe_float(val, default=0.0) -> float:
    if val is None or val == '' or val == 'None':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def get_field(stock: Dict, *keys) -> Any:
    for key in keys:
        if key in stock:
            return stock[key]
    return None


# ========== 五维评分系统 ==========
def score_ma_position(stock: Dict) -> Tuple[int, List[str], List[str]]:
    """维度1：均线位置 (满分8分)"""
    score = 0
    passed = []
    failed = []

    bias5 = safe_float(get_field(stock, '5日均值乖离率'))
    bias10 = safe_float(get_field(stock, '10日均值乖离率'))
    bias60 = safe_float(get_field(stock, '60日均层乖离率', '60日均值乖离率'))
    ma5 = safe_float(get_field(stock, '5日均值'))
    ma10 = safe_float(get_field(stock, '10日均值'))
    ma20 = safe_float(get_field(stock, '20日均值'))

    if -3 <= bias5 <= 3:
        score += 3
        passed.append(f"5日乖离{bias5:+.2f}%在±3%内（极佳）")
    elif -5 <= bias5 <= 5:
        score += 2
        passed.append(f"5日乖离{bias5:+.2f}%在±5%内（良好）")
    elif -8 <= bias5 <= 8:
        score += 1
        passed.append(f"5日乖离{bias5:+.2f}%在±8%内（一般）")
    else:
        failed.append(f"5日乖离{bias5:+.2f}%偏离过大")

    if -5 <= bias10 <= 5:
        score += 1
        passed.append(f"10日乖离{bias10:+.2f}%在±5%内")
    else:
        failed.append(f"10日乖离{bias10:+.2f}%偏离")

    if -15 <= bias60 <= 5:
        score += 1
        passed.append(f"60日乖离{bias60:+.2f}%合理")
    else:
        failed.append(f"60日乖离{bias60:+.2f}%偏离")

    if ma5 > 0 and ma10 > 0 and ma20 > 0:
        if ma5 > ma10 > ma20:
            score += 3
            passed.append("5>10>20日均线多头排列")
        elif ma5 > ma10:
            score += 1
            passed.append("5日>10日均线")
        else:
            failed.append("均线非多头排列")
    else:
        failed.append("均线数据不完整")

    return score, passed, failed


def score_volume_price(stock: Dict) -> Tuple[int, List[str], List[str]]:
    """维度2：量价信号 (满分8分)"""
    score = 0
    passed = []
    failed = []

    vol_ratio = safe_float(get_field(stock, '量比'))
    turnover = safe_float(get_field(stock, '换手率'))
    amp5d = safe_float(get_field(stock, '5日最大振幅'))
    change = safe_float(get_field(stock, '涨跌幅'))

    if vol_ratio < 0.8:
        score += 3
        passed.append(f"量比{vol_ratio:.2f}缩量企稳")
    elif vol_ratio <= 1.2:
        score += 2
        passed.append(f"量比{vol_ratio:.2f}温和")
    elif vol_ratio <= 2.0:
        if turnover <= 8:
            score += 3
            passed.append(f"量比{vol_ratio:.2f}温和放量，换手{turnover:.1f}%健康")
        else:
            score += 1
            passed.append(f"量比{vol_ratio:.2f}放量但换手{turnover:.1f}%偏高")
    elif vol_ratio <= 3.0:
        failed.append(f"量比{vol_ratio:.2f}偏大")
    else:
        failed.append(f"量比{vol_ratio:.2f}过大，疑似放量滞涨")

    if 1 <= turnover <= 8:
        score += 2
        passed.append(f"换手率{turnover:.1f}%健康")
    elif 8 < turnover <= 15:
        score += 1
        passed.append(f"换手率{turnover:.1f}%偏高但可接受")
    elif turnover > 15:
        failed.append(f"换手率{turnover:.1f}%过高")
    else:
        failed.append(f"换手率{turnover:.1f}%过低")

    if amp5d < 8:
        score += 1
        passed.append(f"5日最大振幅{amp5d:.1f}%波动收敛")
    elif amp5d < 15:
        failed.append(f"5日最大振幅{amp5d:.1f}%波动偏大")
    else:
        failed.append(f"5日最大振幅{amp5d:.1f}%波动剧烈")

    if vol_ratio >= 2.5 and change < 1:
        failed.append("放量滞涨嫌疑")
    else:
        score += 2
        passed.append("无放量滞涨")

    return score, passed, failed


def score_kline(stock: Dict) -> Tuple[int, List[str], List[str]]:
    """维度3：K线确认 (满分8分)"""
    score = 0
    passed = []
    failed = []

    change = safe_float(get_field(stock, '涨跌幅'))
    amplitude = safe_float(get_field(stock, '振幅'))
    rsi = safe_float(get_field(stock, 'RSI'))

    if 0 < change <= 3:
        score += 3
        passed.append(f"涨跌{change:+.2f}%温和上涨")
    elif 3 < change <= 5:
        score += 2
        passed.append(f"涨跌{change:+.2f}%偏强上涨")
    elif -2 <= change <= 0:
        score += 1
        passed.append(f"涨跌{change:+.2f}%小幅回调")
    elif change > 5:
        if change < 9.5:
            failed.append(f"涨跌{change:+.2f}%涨幅过大")
        else:
            failed.append(f"涨跌{change:+.2f}%涨停/接近涨停")
    else:
        failed.append(f"涨跌{change:+.2f}%跌幅过大")

    if amplitude < 5:
        score += 2
        passed.append(f"振幅{amplitude:.1f}%波动收敛")
    elif amplitude < 8:
        score += 1
        passed.append(f"振幅{amplitude:.1f}%波动适中")
    else:
        failed.append(f"振幅{amplitude:.1f}%波动过大")

    if abs(change) < 9.5:
        score += 1
        passed.append("非涨停跌停")
    else:
        failed.append("涨停或跌停")

    if 40 <= rsi <= 60:
        score += 2
        passed.append(f"RSI {rsi:.1f}多空平衡区")
    elif 35 <= rsi <= 65:
        score += 1
        passed.append(f"RSI {rsi:.1f}区间合理")
    elif rsi > 70:
        failed.append(f"RSI {rsi:.1f}超买")
    elif rsi < 30:
        failed.append(f"RSI {rsi:.1f}超卖")
    else:
        if rsi > 65:
            failed.append(f"RSI {rsi:.1f}偏高")
        else:
            passed.append(f"RSI {rsi:.1f}可接受")

    return score, passed, failed


def score_capital_flow(stock: Dict) -> Tuple[int, List[str], List[str]]:
    """维度4：资金方向 (满分8分)"""
    score = 0
    passed = []
    failed = []

    flow_5d = safe_float(get_field(stock, '5日主力资金净流入'))
    big_net = safe_float(get_field(stock, '超大单净流入')) + safe_float(get_field(stock, '大单净流入'))
    super_big = safe_float(get_field(stock, '超大单净流入'))
    flow_ratio = safe_float(get_field(stock, '主力资金净流入比'))
    efficiency = safe_float(get_field(stock, '资金撬动效率'))

    if flow_5d > 0:
        score += 3
        passed.append(f"5日主力净流入+{flow_5d/1e8:.2f}亿")
    else:
        failed.append(f"5日主力净流入{flow_5d/1e8:+.2f}亿为负")

    if big_net > 0:
        score += 2
        passed.append(f"当日主力(超大+大单)净流入+{big_net/1e8:.2f}亿")
    else:
        failed.append(f"当日主力净流入{big_net/1e8:+.2f}亿为负")

    if flow_ratio > 2:
        score += 1
        passed.append(f"主力净流入比{flow_ratio:.1f}%>2%")
    elif flow_ratio > 0:
        passed.append(f"主力净流入比{flow_ratio:.1f}%偏低")
    else:
        failed.append(f"主力净流入比{flow_ratio:.1f}%为负")

    if super_big > 0:
        score += 1
        passed.append(f"超大单净流入+{super_big/1e4:.0f}万（机构行为）")
    else:
        failed.append("超大单净流出")

    if efficiency > 0:
        score += 1
        passed.append(f"资金撬动效率{efficiency:.4f}>0")
    else:
        failed.append(f"资金撬动效率{efficiency:.4f}≤0")

    return score, passed, failed


def score_buyback(stock: Dict) -> Tuple[int, List[str], List[str]]:
    """
    维度5：回购+增持 (满分8分)
    - 有回购方案（在途）: +2
    - 注销式回购: +2（直接增厚EPS，最实在）
    - 回购金额>10亿: +2, 5-10亿: +1
    - 回购+增持双管齐下: +1
    - 实控人/控股股东增持或锁仓承诺: +1
    数据来源：证券时报、上海证券报等公开公告
    """
    score = 0
    passed = []
    failed = []

    code = str(get_field(stock, '股票代码') or '')
    info = BUYBACK_DB.get(code)

    if not info:
        # 无回购信息
        failed.append("无回购/增持公告")
        return score, passed, failed

    # 有回购方案
    if info.get("buyback"):
        score += 2
        amt_min = info.get("amount_min", 0)
        amt_max = info.get("amount_max", 0)
        if amt_max > 0:
            passed.append(f"在途回购方案{amt_min}-{amt_max}亿元")
        else:
            passed.append("已发布回购方案（金额待确认）")

        # 回购金额
        if amt_max >= 10:
            score += 2
            passed.append(f"大额回购≥10亿（龙头级）")
        elif amt_max >= 5:
            score += 1
            passed.append(f"中等回购5-10亿")
        elif amt_max > 0:
            passed.append(f"回购{amt_min}-{amt_max}亿")

        # 注销式回购
        if info.get("cancel"):
            score += 2
            passed.append("注销式回购（直接增厚EPS）")
        else:
            passed.append("非注销式回购（用于激励/出售）")
    else:
        failed.append("无回购方案")

    # 回购+增持双管齐下
    if info.get("double"):
        score += 1
        passed.append("回购+股东增持双管齐下")

    # 实控人/控股股东增持或锁仓
    if info.get("shareholder_add"):
        score += 1
        passed.append("实控人/控股股东增持或锁仓承诺")

    return score, passed, failed


# ========== 主筛选逻辑 ==========
def apply_five_dim_filter(stock: Dict, min_dim_score: int = 2) -> Optional[Dict]:
    """应用五维共振筛选"""
    name = str(get_field(stock, '证券简称', 'secu_cn_abbr') or '')
    if 'ST' in name.upper():
        return None

    mcap = safe_float(get_field(stock, '总市值'))
    if mcap < 30e8:
        return None

    ma_score, ma_pass, ma_fail = score_ma_position(stock)
    vp_score, vp_pass, vp_fail = score_volume_price(stock)
    kl_score, kl_pass, kl_fail = score_kline(stock)
    cf_score, cf_pass, cf_fail = score_capital_flow(stock)
    bb_score, bb_pass, bb_fail = score_buyback(stock)

    total = ma_score + vp_score + kl_score + cf_score + bb_score

    # 前四维每维至少min_dim_score分，第五维不限（无回购信息不扣分）
    if ma_score < min_dim_score or vp_score < min_dim_score or \
       kl_score < min_dim_score or cf_score < min_dim_score:
        return None

    return {
        'stock': stock,
        'scores': {
            'ma': ma_score, 'vp': vp_score,
            'kl': kl_score, 'cf': cf_score,
            'bb': bb_score, 'total': total
        },
        'details': {
            'ma': {'pass': ma_pass, 'fail': ma_fail},
            'vp': {'pass': vp_pass, 'fail': vp_fail},
            'kl': {'pass': kl_pass, 'fail': kl_fail},
            'cf': {'pass': cf_pass, 'fail': cf_fail},
            'bb': {'pass': bb_pass, 'fail': bb_fail}
        }
    }


def scan_market(min_dim_score: int = 2, min_total: int = 10) -> List[Dict]:
    """执行多策略扫描"""
    strategies = [
        {
            'name': '缩量企稳型',
            'demand': (
                "筛选A股非ST股票，5日乖离率在-5%到5%之间，"
                "量比小于1.2，换手率1-8%，"
                "5日主力资金净流入为正，RSI在35-65之间，"
                "当日涨跌幅-2%到5%，振幅小于8%，市值大于30亿"
            )
        },
        {
            'name': '温和放量突破型',
            'demand': (
                "筛选A股非ST股票，5日乖离率在-5%到5%之间，"
                "量比在1到2之间，换手率2-10%，"
                "5日主力资金净流入为正，RSI在40-65之间，"
                "当日涨跌幅0-5%，市值大于30亿"
            )
        },
        {
            'name': '均线多头回踩型',
            'demand': (
                "筛选A股非ST股票，5日乖离率在-3%到3%之间，"
                "10日乖离率在-5%到5%之间，"
                "5日主力资金净流入为正，"
                "当日涨跌幅-2%到4%，振幅小于6%，市值大于30亿"
            )
        },
        {
            'name': '底部放量启动型',
            'demand': (
                "筛选A股非ST股票，60日乖离率在-15%到0之间，"
                "5日主力资金净流入为正，量比大于1.5，"
                "当日涨跌幅0-5%，RSI在40-60之间，市值大于30亿"
            )
        },
        {
            'name': '回购潮重点标的',
            'demand': (
                "筛选A股非ST股票，以下公司优先调取数据："
                "宁德时代、中际旭创、兆易创新、工业富联、立讯精密、"
                "京东方A、阳光电源、国电南瑞、三环集团、网宿科技、"
                "佰维存储、江波龙、金山办公、科大讯飞，"
                "5日主力资金净流入为正，市值大于30亿"
            )
        }
    ]

    all_stocks = {}

    for i, strategy in enumerate(strategies):
        print(f"\n{'='*60}")
        print(f"策略{i+1}/{len(strategies)}: {strategy['name']}")
        print(f"{'='*60}")
        print(f"  查询条件: {strategy['demand'][:80]}...")

        data = query_mcp(strategy['demand'])
        if not data:
            print("  未获取到数据，跳过")
            continue

        print(f"  获取到 {len(data)} 只股票")
        for stock in data:
            code = str(get_field(stock, '股票代码', 'secu_code') or '')
            if code and code not in all_stocks:
                all_stocks[code] = stock

    print(f"\n{'='*60}")
    print(f"去重后共 {len(all_stocks)} 只股票，开始五维共振筛选...")
    print(f"{'='*60}")

    results = []
    for code, stock in all_stocks.items():
        result = apply_five_dim_filter(stock, min_dim_score)
        if result and result['scores']['total'] >= min_total:
            results.append(result)

    results.sort(key=lambda x: (
        x['scores']['total'],
        x['scores']['bb'],  # 回购维度优先排序
        x['scores']['cf'],
        x['scores']['ma']
    ), reverse=True)

    return results


# ========== 报告生成 ==========
def generate_html_report(results: List[Dict], output_path: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    trade_date = ""
    if results:
        trade_date = str(get_field(results[0]['stock'], '交易日') or '')

    rows_html = ""
    for i, r in enumerate(results):
        s = r['stock']
        scores = r['scores']
        details = r['details']

        code = str(get_field(s, '股票代码') or '')
        name = str(get_field(s, '证券简称') or '')
        industry = str(get_field(s, '行业分类名称二级') or '')
        close = safe_float(get_field(s, '收盘价'))
        change = safe_float(get_field(s, '涨跌幅'))
        mcap = safe_float(get_field(s, '总市值')) / 1e8
        turnover = safe_float(get_field(s, '换手率'))
        vol_ratio = safe_float(get_field(s, '量比'))
        rsi = safe_float(get_field(s, 'RSI'))
        flow_5d = safe_float(get_field(s, '5日主力资金净流入')) / 1e8
        bias5 = safe_float(get_field(s, '5日均值乖离率'))

        def score_color(sc, mx):
            if sc >= mx * 0.7: return '#3fb950'
            if sc >= mx * 0.4: return '#d29922'
            return '#f85149'

        ma_c = score_color(scores['ma'], 8)
        vp_c = score_color(scores['vp'], 8)
        kl_c = score_color(scores['kl'], 8)
        cf_c = score_color(scores['cf'], 8)
        bb_c = score_color(scores['bb'], 8)
        tt_c = score_color(scores['total'], 40)

        detail_id = f"detail_{i}"
        detail_parts = []
        dim_names = {'ma': '均线位置', 'vp': '量价信号', 'kl': 'K线确认', 'cf': '资金方向', 'bb': '回购增持'}
        dim_colors = {'ma': '#f0883e', 'vp': '#58a6ff', 'kl': '#7ee787', 'cf': '#d29922', 'bb': '#bc8cff'}
        for dim_key in ['ma', 'vp', 'kl', 'cf', 'bb']:
            d = details[dim_key]
            lines = []
            for p in d['pass']:
                lines.append(f'<div class="detail-pass">✓ {p}</div>')
            for f in d['fail']:
                lines.append(f'<div class="detail-fail">✗ {f}</div>')
            detail_parts.append(
                f'<div class="detail-dim"><span style="color:{dim_colors[dim_key]};font-weight:bold;">'
                f'{dim_names[dim_key]}({scores[dim_key]}/8)</span>'
                f'{"".join(lines)}</div>'
            )

        change_color = '#3fb950' if change > 0 else '#f85149' if change < 0 else '#8b949e'

        # 回购标记
        bb_tag = ""
        if scores['bb'] >= 6:
            bb_tag = '<span class="bb-tag gold">💎回购强</span>'
        elif scores['bb'] >= 4:
            bb_tag = '<span class="bb-tag silver">📦回购</span>'
        elif scores['bb'] >= 2:
            bb_tag = '<span class="bb-tag bronze">📋回购</span>'

        rows_html += f"""
        <tr class="stock-row" onclick="toggleDetail('{detail_id}')">
            <td>{i+1}</td>
            <td class="stock-name">{name}{bb_tag}</td>
            <td class="stock-code">{code}</td>
            <td>{industry}</td>
            <td>{close:.2f}</td>
            <td style="color:{change_color}">{change:+.2f}%</td>
            <td>{mcap:.0f}亿</td>
            <td>{bias5:+.2f}%</td>
            <td>{turnover:.1f}%</td>
            <td>{vol_ratio:.2f}</td>
            <td>{rsi:.1f}</td>
            <td style="color:{'#3fb950' if flow_5d > 0 else '#f85149'}">{flow_5d:+.2f}亿</td>
            <td style="color:{ma_c};font-weight:bold">{scores['ma']}</td>
            <td style="color:{vp_c};font-weight:bold">{scores['vp']}</td>
            <td style="color:{kl_c};font-weight:bold">{scores['kl']}</td>
            <td style="color:{cf_c};font-weight:bold">{scores['cf']}</td>
            <td style="color:{bb_c};font-weight:bold">{scores['bb']}</td>
            <td style="color:{tt_c};font-weight:bold;font-size:15px">{scores['total']}</td>
        </tr>
        <tr id="{detail_id}" class="detail-row" style="display:none">
            <td colspan="18">
                <div class="detail-container">
                    {''.join(detail_parts)}
                </div>
            </td>
        </tr>
        """

    total_scanned = len(results)
    score_dist = {}
    for r in results:
        t = r['scores']['total']
        score_dist[t] = score_dist.get(t, 0) + 1

    dist_bars = ""
    max_count = max(score_dist.values()) if score_dist else 1
    for score_val in sorted(score_dist.keys(), reverse=True):
        count = score_dist[score_val]
        pct = count / max_count * 100
        dist_bars += f"""
        <div class="dist-row">
            <span class="dist-label">{score_val}分</span>
            <div class="dist-bar-bg"><div class="dist-bar" style="width:{pct}%"></div></div>
            <span class="dist-count">{count}只</span>
        </div>"""

    # 回购交叉命中统计
    buyback_hits = [r for r in results if r['scores']['bb'] >= 2]
    buyback_high = [r for r in results if r['scores']['bb'] >= 6]

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>五维共振选股器 — 扫描报告</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0d1117; color: #c9d1d9;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
    line-height: 1.5; padding: 20px;
  }}
  .container {{ max-width: 1500px; margin: 0 auto; }}
  h1 {{ color: #58a6ff; font-size: 24px; text-align: center; margin: 20px 0 5px; }}
  .meta {{ text-align: center; color: #8b949e; font-size: 13px; margin-bottom: 25px; }}

  .stats-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin: 20px 0; }}
  .stat-card {{
    background: #161b22; border: 1px solid #30363d;
    border-radius: 8px; padding: 15px; text-align: center;
  }}
  .stat-card .num {{ font-size: 28px; font-weight: bold; }}
  .stat-card .label {{ color: #8b949e; font-size: 12px; margin-top: 4px; }}

  .dist-section, .table-section, .criteria-section {{
    background: #161b22; border: 1px solid #30363d;
    border-radius: 8px; margin: 20px 0; overflow: hidden;
  }}
  .dist-section {{ padding: 20px; }}
  .dist-section h3 {{ color: #f0883e; margin-bottom: 12px; }}
  .dist-row {{ display: flex; align-items: center; gap: 10px; margin: 6px 0; }}
  .dist-label {{ width: 50px; text-align: right; color: #8b949e; font-size: 13px; }}
  .dist-bar-bg {{ flex: 1; height: 18px; background: #21262d; border-radius: 4px; overflow: hidden; }}
  .dist-bar {{ height: 100%; background: linear-gradient(90deg, #1f6feb, #58a6ff); border-radius: 4px; }}
  .dist-count {{ width: 50px; color: #c9d1d9; font-size: 13px; }}

  .table-header {{
    background: linear-gradient(135deg, #1a2332, #1f2937);
    padding: 12px 20px; border-bottom: 1px solid #30363d;
    display: flex; justify-content: space-between; align-items: center;
  }}
  .table-header h3 {{ color: #f0883e; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  thead th {{
    background: #1a2332; color: #58a6ff; padding: 8px 4px;
    text-align: center; border-bottom: 2px solid #30363d;
    position: sticky; top: 0; white-space: nowrap;
  }}
  tbody td {{
    padding: 6px 4px; text-align: center; border-bottom: 1px solid #21262d;
    white-space: nowrap;
  }}
  tbody tr:hover {{ background: #1a2332; }}
  tbody tr.stock-row {{ cursor: pointer; }}
  .stock-name {{ color: #f0883e; font-weight: bold; text-align: left !important; }}
  .stock-code {{ color: #8b949e; text-align: left !important; }}

  .bb-tag {{
    display: inline-block; font-size: 10px; padding: 1px 5px;
    border-radius: 3px; margin-left: 4px; font-weight: normal;
  }}
  .bb-tag.gold {{ background: rgba(188,140,255,0.2); color: #bc8cff; border: 1px solid #bc8cff; }}
  .bb-tag.silver {{ background: rgba(210,153,34,0.15); color: #d29922; border: 1px solid #d29922; }}
  .bb-tag.bronze {{ background: rgba(139,148,158,0.15); color: #8b949e; border: 1px solid #8b949e; }}

  .detail-row td {{ background: #0d1117; padding: 15px 20px; }}
  .detail-container {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; max-width: 1100px; margin: 0 auto; }}
  .detail-dim {{ background: #161b22; border-radius: 6px; padding: 10px 12px; }}
  .detail-pass {{ color: #3fb950; font-size: 12px; padding: 2px 0; }}
  .detail-fail {{ color: #f85149; font-size: 12px; padding: 2px 0; }}

  .criteria-section {{ padding: 20px; }}
  .criteria-section h3 {{ color: #7ee787; margin-bottom: 12px; }}
  .criteria-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
  .criteria-card {{
    background: #0d1117; border-radius: 6px; padding: 12px; border-left: 3px solid;
  }}
  .criteria-card .title {{ font-weight: bold; margin-bottom: 6px; }}
  .criteria-card .item {{ font-size: 12px; color: #8b949e; padding: 1px 0; }}

  .new-dim-banner {{
    background: linear-gradient(135deg, rgba(188,140,255,0.1), rgba(88,166,255,0.1));
    border: 1px solid #bc8cff; border-radius: 8px;
    padding: 15px 20px; margin: 20px 0; text-align: center;
  }}
  .new-dim-banner h3 {{ color: #bc8cff; margin-bottom: 6px; }}
  .new-dim-banner p {{ color: #8b949e; font-size: 13px; }}

  .disclaimer {{
    text-align: center; color: #8b949e; font-size: 11px;
    margin-top: 30px; padding: 15px; border-top: 1px solid #21262d;
  }}

  @media (max-width: 768px) {{
    .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
    .criteria-grid {{ grid-template-columns: 1fr; }}
    .detail-container {{ grid-template-columns: 1fr; }}
    table {{ font-size: 10px; }}
  }}
</style>
<script>
function toggleDetail(id) {{
  var el = document.getElementById(id);
  el.style.display = el.style.display === 'none' ? 'table-row' : 'none';
}}
</script>
</head>
<body>
<div class="container">
  <h1>📈 五维共振选股器 — 扫描报告</h1>
  <p class="meta">扫描时间: {now} | 数据日期: {trade_date} | 符合条件: {total_scanned}只</p>

  <div class="new-dim-banner">
    <h3>🆕 新增第五维度：回购+增持</h3>
    <p>7月下旬A股科技赛道回购潮：120+份回购方案，上限总额超770亿，注销式回购占比提升，13家回购+增持双管齐下</p>
    <p style="color:#bc8cff">数据来源：证券时报、上海证券报等公开公告 | 更新：2026-08-03</p>
  </div>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="num" style="color:#58a6ff">{total_scanned}</div>
      <div class="label">符合条件股票数</div>
    </div>
    <div class="stat-card">
      <div class="num" style="color:#3fb950">{sum(1 for r in results if r['scores']['total']>=24)}</div>
      <div class="label">高分股(≥24分)</div>
    </div>
    <div class="stat-card">
      <div class="num" style="color:#bc8cff">{len(buyback_hits)}</div>
      <div class="label">回购共振股</div>
    </div>
    <div class="stat-card">
      <div class="num" style="color:#f0883e">{len(buyback_high)}</div>
      <div class="label">回购强共振股</div>
    </div>
    <div class="stat-card">
      <div class="num" style="color:#7ee787">{sum(1 for r in results if r['scores']['cf']>=6)}</div>
      <div class="label">资金面强势(≥6分)</div>
    </div>
  </div>

  <div class="dist-section">
    <h3>📊 分数分布</h3>
    {dist_bars}
  </div>

  <div class="table-section">
    <div class="table-header">
      <h3>🏆 五维共振选股结果（点击行展开详情）</h3>
      <span style="color:#8b949e;font-size:12px">满分40分 | 每维度满分8分</span>
    </div>
    <div style="overflow-x:auto">
    <table>
      <thead>
        <tr>
          <th>#</th><th>名称</th><th>代码</th><th>行业</th>
          <th>收盘价</th><th>涨跌幅</th><th>总市值</th>
          <th>5日乖离</th><th>换手率</th><th>量比</th><th>RSI</th><th>5日主力流入</th>
          <th style="color:#f0883e">均线</th><th style="color:#58a6ff">量价</th>
          <th style="color:#7ee787">K线</th><th style="color:#d29922">资金</th>
          <th style="color:#bc8cff">回购</th><th>总分</th>
        </tr>
      </thead>
      <tbody>
        {rows_html if rows_html else '<tr><td colspan="18" style="padding:40px;text-align:center;color:#8b949e">暂无符合条件的股票</td></tr>'}
      </tbody>
    </table>
    </div>
  </div>

  <div class="criteria-section">
    <h3>📋 五维共振筛选标准</h3>
    <div class="criteria-grid">
      <div class="criteria-card" style="border-color:#f0883e">
        <div class="title" style="color:#f0883e">维度1: 均线位置 (8分)</div>
        <div class="item">• 5日乖离率±3%内: +3 | ±5%内: +2</div>
        <div class="item">• 10日乖离率±5%内: +1</div>
        <div class="item">• 60日乖离率-15%~+5%: +1</div>
        <div class="item">• 5>10>20日多头排列: +3</div>
      </div>
      <div class="criteria-card" style="border-color:#58a6ff">
        <div class="title" style="color:#58a6ff">维度2: 量价信号 (8分)</div>
        <div class="item">• 缩量企稳(量比<0.8): +3 | 温和: +2</div>
        <div class="item">• 温和放量(量比1-2,换手2-8%): +3</div>
        <div class="item">• 换手率1-8%: +2 | 5日振幅<8%: +1</div>
        <div class="item">• 无放量滞涨: +2</div>
      </div>
      <div class="criteria-card" style="border-color:#7ee787">
        <div class="title" style="color:#7ee787">维度3: K线确认 (8分)</div>
        <div class="item">• 涨跌幅0-3%: +3 | 3-5%: +2</div>
        <div class="item">• 振幅<5%: +2 | <8%: +1</div>
        <div class="item">• 非涨停跌停: +1</div>
        <div class="item">• RSI 40-60: +2 | 35-65: +1</div>
      </div>
      <div class="criteria-card" style="border-color:#d29922">
        <div class="title" style="color:#d29922">维度4: 资金方向 (8分)</div>
        <div class="item">• 5日主力净流入>0: +3</div>
        <div class="item">• 当日主力净流入>0: +2</div>
        <div class="item">• 主力净流入比>2%: +1</div>
        <div class="item">• 超大单净流入>0: +1 | 撬动效率>0: +1</div>
      </div>
      <div class="criteria-card" style="border-color:#bc8cff">
        <div class="title" style="color:#bc8cff">维度5: 回购+增持 (8分) 🆕</div>
        <div class="item">• 有在途回购方案: +2</div>
        <div class="item">• 注销式回购: +2（直接增厚EPS）</div>
        <div class="item">• 回购金额≥10亿: +2 | 5-10亿: +1</div>
        <div class="item">• 回购+增持双管齐下: +1</div>
        <div class="item">• 实控人增持/锁仓承诺: +1</div>
      </div>
    </div>
  </div>

  <div class="disclaimer">
    ⚠️ AI生成内容仅供参考，不构成投资建议；投资有风险，决策请结合自身情况并咨询专业人士。<br>
    数据来源：恒生聚源A股数据库 | 回购数据来源：证券时报/上海证券报公开公告 | 每前四维度≥2分且总分≥10分方可入选
  </div>
</div>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return output_path


def generate_json_report(results: List[Dict], output_path: str) -> str:
    output = []
    for r in results:
        s = r['stock']
        entry = {
            '代码': str(get_field(s, '股票代码') or ''),
            '名称': str(get_field(s, '证券简称') or ''),
            '行业': str(get_field(s, '行业分类名称二级') or ''),
            '收盘价': safe_float(get_field(s, '收盘价')),
            '涨跌幅': safe_float(get_field(s, '涨跌幅')),
            '总市值(亿)': round(safe_float(get_field(s, '总市值')) / 1e8, 2),
            '5日乖离率': safe_float(get_field(s, '5日均值乖离率')),
            '换手率': safe_float(get_field(s, '换手率')),
            '量比': safe_float(get_field(s, '量比')),
            'RSI': safe_float(get_field(s, 'RSI')),
            '5日主力净流入(亿)': round(safe_float(get_field(s, '5日主力资金净流入')) / 1e8, 4),
            '五维评分': r['scores'],
            '均线位置': r['details']['ma'],
            '量价信号': r['details']['vp'],
            'K线确认': r['details']['kl'],
            '资金方向': r['details']['cf'],
            '回购增持': r['details']['bb'],
        }
        output.append(entry)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return output_path


def main():
    parser = argparse.ArgumentParser(description='五维共振选股器 v2.0')
    parser.add_argument('--output', choices=['html', 'json', 'both'], default='both')
    parser.add_argument('--min-score', type=int, default=10, help='最低总分阈值 (默认10)')
    parser.add_argument('--min-dim', type=int, default=2, help='前四维每维度最低分 (默认2)')
    args = parser.parse_args()

    print("=" * 60)
    print("  📈 五维共振选股器 v2.0")
    print("  量价 + K线 + 均线 + 资金 + 回购增持 五维共振")
    print("=" * 60)

    results = scan_market(min_dim_score=args.min_dim, min_total=args.min_score)

    print(f"\n{'='*60}")
    print(f"  筛选完成！共 {len(results)} 只股票符合五维共振条件")
    print(f"{'='*60}")

    if not results:
        print("\n暂无符合条件的股票。")
        return

    print(f"\n{'排名':<4} {'代码':<12} {'名称':<10} {'总分':>4} "
          f"{'均线':>4} {'量价':>4} {'K线':>4} {'资金':>4} {'回购':>4} "
          f"{'涨跌幅':>7} {'5日乖离':>7} {'5日主力(亿)':>10}")
    print("-" * 100)
    for i, r in enumerate(results[:30]):
        s = r['stock']
        sc = r['scores']
        code = str(get_field(s, '股票代码') or '')
        name = str(get_field(s, '证券简称') or '')[:8]
        change = safe_float(get_field(s, '涨跌幅'))
        bias5 = safe_float(get_field(s, '5日均值乖离率'))
        flow5d = safe_float(get_field(s, '5日主力资金净流入')) / 1e8
        print(f"{i+1:<4} {code:<12} {name:<10} {sc['total']:>4} "
              f"{sc['ma']:>4} {sc['vp']:>4} {sc['kl']:>4} {sc['cf']:>4} {sc['bb']:>4}  "
              f"{change:>+6.2f}% {bias5:>+6.2f}% {flow5d:>+8.2f}")

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    if args.output in ('html', 'both'):
        html_path = os.path.join(OUTPUT_DIR, f"五维共振选股_{ts}.html")
        generate_html_report(results, html_path)
        print(f"\n✅ HTML报告: {html_path}")
    if args.output in ('json', 'both'):
        json_path = os.path.join(OUTPUT_DIR, f"五维共振选股_{ts}.json")
        generate_json_report(results, json_path)
        print(f"✅ JSON报告: {json_path}")


if __name__ == '__main__':
    main()
