#!/usr/bin/env python3
"""
股票复盘工具 - Flask API 服务
提供 RESTful 接口，支持按日期/股票/板块/分类查询，分页返回

启动: python app.py
访问: http://localhost:5000
"""
import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
from flask_cors import CORS

import config
from database import DatabaseManager

# ===== 初始化 =====
app = Flask(__name__)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format=config.LOG_FORMAT,
)
logger = logging.getLogger("api")

db = DatabaseManager()


# ===== 辅助函数 =====

def get_page_params():
    """从请求参数中提取分页参数"""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", config.DEFAULT_PAGE_SIZE, type=int)
    page = max(1, page)
    page_size = min(max(1, page_size), config.MAX_PAGE_SIZE)
    return page, page_size


def parse_date(date_str: str):
    """解析日期参数"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def success_response(data, total=None, page=None, page_size=None):
    """统一成功响应格式"""
    resp = {"code": 0, "message": "success", "data": data}
    if total is not None:
        resp["total"] = total
        resp["page"] = page
        resp["page_size"] = page_size
    return jsonify(resp)


def error_response(message, code=400):
    """统一错误响应格式"""
    return jsonify({"code": code, "message": message, "data": None}), code


# ===== API 路由 =====

@app.route("/", methods=["GET"])
def index():
    """API 根路径 - 返回接口列表"""
    return jsonify({
        "service": "股票复盘数据查询 API",
        "version": "1.0.0",
        "endpoints": {
            "GET /api/review/daily": "查询某天完整复盘结果 (参数: date)",
            "GET /api/review/sectors": "查询板块资金流向 (参数: date, flow_type, sector_name, page, page_size)",
            "GET /api/review/stocks": "查询个股复盘结果 (参数: date, category, stock_code, stock_name, sector_name, page, page_size)",
            "GET /api/review/stock_history": "查询个股历史入选记录 (参数: stock_code, page, page_size)",
            "GET /api/review/categories": "获取数据分类枚举",
            "GET /api/review/dates": "获取已有复盘日期列表",
        },
    })


@app.route("/api/review/daily", methods=["GET"])
def get_daily_review():
    """
    查询某天的完整复盘结果
    参数:
        date: 交易日期 (YYYY-MM-DD)，必填
    """
    date_str = request.args.get("date", "")
    trade_date = parse_date(date_str)
    if not trade_date:
        return error_response("请提供有效的日期参数 (格式: YYYY-MM-DD)")

    result = db.query_daily_review(trade_date)
    if result is None:
        return error_response(f"{date_str} 暂无复盘数据", 404)
    return success_response(result)


@app.route("/api/review/sectors", methods=["GET"])
def get_sector_flows():
    """
    查询板块资金流向
    参数:
        date: 交易日期 (YYYY-MM-DD)
        flow_type: 流向类型 (inflow/outflow/abnormal)
        sector_name: 板块名称（模糊搜索）
        page: 页码 (默认 1)
        page_size: 每页条数 (默认 20)
    """
    trade_date = parse_date(request.args.get("date", ""))
    flow_type = request.args.get("flow_type", "")
    sector_name = request.args.get("sector_name", "")
    page, page_size = get_page_params()

    result = db.query_sector_flows(
        trade_date=trade_date,
        flow_type=flow_type or None,
        sector_name=sector_name or None,
        page=page,
        page_size=page_size,
    )
    return success_response(
        result["data"],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@app.route("/api/review/stocks", methods=["GET"])
def get_stock_results():
    """
    查询个股复盘结果
    参数:
        date: 交易日期 (YYYY-MM-DD)
        category: 数据分类 (见分类枚举)
        stock_code: 股票代码（精确匹配）
        stock_name: 股票名称（模糊搜索）
        sector_name: 板块名称（模糊搜索）
        page: 页码 (默认 1)
        page_size: 每页条数 (默认 20)
    """
    trade_date = parse_date(request.args.get("date", ""))
    category = request.args.get("category", "")
    stock_code = request.args.get("stock_code", "")
    stock_name = request.args.get("stock_name", "")
    sector_name = request.args.get("sector_name", "")
    page, page_size = get_page_params()

    result = db.query_stock_results(
        trade_date=trade_date,
        category=category or None,
        stock_code=stock_code or None,
        stock_name=stock_name or None,
        sector_name=sector_name or None,
        page=page,
        page_size=page_size,
    )
    return success_response(
        result["data"],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@app.route("/api/review/stock_history", methods=["GET"])
def get_stock_history():
    """
    查询个股历史入选记录
    参数:
        stock_code: 股票代码，必填
        page: 页码
        page_size: 每页条数
    """
    stock_code = request.args.get("stock_code", "")
    if not stock_code:
        return error_response("请提供 stock_code 参数")

    page, page_size = get_page_params()
    result = db.query_stock_history(stock_code, page=page, page_size=page_size)
    return success_response(
        result["data"],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@app.route("/api/review/categories", methods=["GET"])
def get_categories():
    """获取数据分类枚举"""
    categories = [
        {"value": config.CATEGORY_STOCK_INFLOW_TOP30, "label": "资金流入前30股"},
        {"value": config.CATEGORY_STOCK_OUTFLOW_TOP30, "label": "资金流出前30股"},
        {"value": config.CATEGORY_ABNORMAL_SECTOR_LEADER, "label": "异动板块带领个股"},
        {"value": config.CATEGORY_VOLUME_MA5_CROSS_MA10, "label": "放量且5日线上穿10日线"},
        {"value": config.CATEGORY_TURNOVER_TOP20, "label": "资金成交量前20股"},
        {"value": config.CATEGORY_LIMIT_UP_LAST_10_DAYS, "label": "近10日涨停股"},
        {"value": config.CATEGORY_DECLINE_SHRINK_VOLUME, "label": "近期下跌缩量/今日下跌放量"},
    ]
    return success_response(categories)


@app.route("/api/review/dates", methods=["GET"])
def get_review_dates():
    """获取已有复盘日期列表"""
    from database import ReviewDaily
    session = db.get_session()
    try:
        records = session.query(ReviewDaily.trade_date) \
            .order_by(ReviewDaily.trade_date.desc()) \
            .limit(100).all()
        dates = [r[0].isoformat() for r in records if r[0]]
        return success_response(dates)
    finally:
        session.close()


# ===== 错误处理 =====

@app.errorhandler(404)
def not_found(e):
    return error_response("接口不存在", 404)


@app.errorhandler(500)
def internal_error(e):
    logger.error(f"服务器内部错误: {e}")
    return error_response("服务器内部错误", 500)


# ===== 启动 =====

if __name__ == "__main__":
    logger.info(f"启动 API 服务: http://{config.API_HOST}:{config.API_PORT}")
    logger.info("按 Ctrl+C 停止")
    app.run(
        host=config.API_HOST,
        port=config.API_PORT,
        debug=config.API_DEBUG,
    )
