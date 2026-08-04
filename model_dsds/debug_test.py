#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""调试脚本：检查K线API和评分是否正常工作"""
import sys
sys.path.insert(0, '.')
from four_dim_scanner import fetch_kline_tencent, fetch_all_spot, score_ma_position, score_volume_price, score_kline, score_fund_flow

# 获取股票列表
stocks = fetch_all_spot()
print(f"Total stocks: {len(stocks)}")

# 测试前5只股票的K线获取
print("\n=== K-line API Test ===")
test_codes = stocks[:5]
for s in test_codes:
    code = s["code"]
    name = s["name"]
    ma_data = fetch_kline_tencent(code)
    if ma_data:
        s1 = score_ma_position(ma_data)
        s2 = score_volume_price(s)
        s3 = score_kline(ma_data)
        s4 = score_fund_flow(s)
        total = s1 + s2 + s3 + s4
        print(f"  {code} {name}: ma={s1} vol={s2} kline={s3} fund={s4} total={total} | close={ma_data['close']:.2f} ma5={ma_data['ma5']:.2f}")
    else:
        print(f"  {code} {name}: K-line FAIL")

# 统计有涨停的股票
print("\n=== Limit Up Scan (first 200 stocks) ===")
limit_up_count = 0
sealed_count = 0
for s in stocks[:200]:
    code = s["code"]
    ma_data = fetch_kline_tencent(code)
    if ma_data:
        if ma_data.get("has_limit_up"):
            limit_up_count += 1
            if ma_data.get("limit_up_sealed"):
                sealed_count += 1
                print(f"  {code} {s['name']}: LIMIT_UP {ma_data['limit_up_date']} sealed={ma_data['limit_up_sealed']}")

print(f"\nResult: {limit_up_count}/200 have limit_up, {sealed_count} sealed")
