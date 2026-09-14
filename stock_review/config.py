"""
股票复盘工具 - 配置文件
所有可调参数集中管理，方便后续修改
"""
import os

# ========== 数据过滤配置 ==========
NEW_STOCK_DAYS = 30            # 新股定义：上市天数 <= 30
SUB_NEW_STOCK_DAYS = 365       # 次新股定义：上市天数 <= 365

# ========== 采集数量配置 ==========
SECTOR_TOP_N = 10              # 板块资金流入/流出前N
STOCK_INFLOW_TOP_N = 30        # 个股资金流入前N
STOCK_OUTFLOW_TOP_N = 30       # 个股资金流出前N
TURNOVER_TOP_N = 20            # 成交额前N
LIMIT_UP_LOOKBACK_DAYS = 10    # 涨停回溯交易日数
DECLINE_LOOKBACK_DAYS = 5      # 下跌缩量回溯交易日数

# ========== 技术指标配置 ==========
VOLUME_RATIO_THRESHOLD = 1.0   # 放量倍数阈值（今日量 / 5日均量 >= 此值视为放量）
ABNORMAL_SECTOR_INFLOW_RANK = 20      # 异动板块：资金净流入排名 <= 此值
ABNORMAL_SECTOR_VOLUME_RATIO = 1.5    # 异动板块：成交额 / 近5日均值 >= 此值
ABNORMAL_SECTOR_CHANGE_THRESHOLD = 1.0 # 异动板块：涨幅 >= 此值(%)
ABNORMAL_SECTOR_MULTI_STOCK_COUNT = 3  # 异动板块：板块内放量上涨个股数量 >= 此值
ABNORMAL_LEADER_TOP_N = 3             # 每个异动板块取前N个龙头个股

# ========== 网络请求配置 ==========
REQUEST_TIMEOUT = 15           # 单次请求超时(秒)
MAX_RETRIES = 1                # 最大重试次数（AKShare不通时快速降级）
RETRY_BASE_DELAY = 1           # 初始重试延迟(秒)
REQUEST_INTERVAL = 0.5         # 连续请求间隔(秒)，防止限频
BATCH_INTERVAL = 1.0           # 批量请求间每批的间隔(秒)
BATCH_SIZE = 50                # 批量获取K线时每批的股票数

# ========== 数据库配置 ==========
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock_review.db")
DB_URI = f"sqlite:///{DB_PATH}"

# ========== 分页配置 ==========
DEFAULT_PAGE_SIZE = 20         # 默认每页条数
MAX_PAGE_SIZE = 100            # 最大每页条数

# ========== API配置 ==========
API_HOST = "0.0.0.0"
API_PORT = 5000
API_DEBUG = True

# ========== 东方财富直连 API（降级备用） ==========
EASTMONEY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 东方财富推送API基础URL
EM_PUSH2_URL = "https://push2.eastmoney.com/api/qt/clist/get"
EM_PUSH2HIS_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EM_ZT_POOL_URL = "https://push2ex.eastmoney.com/getTopicZTPool"

# A股市场代码（用于东方财富API）
EM_A_SHARE_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
EM_SECTOR_FS = "m:90+t:2"  # 行业板块

# ========== 数据分类枚举 ==========
CATEGORY_STOCK_INFLOW_TOP30 = "stock_inflow_top30"
CATEGORY_STOCK_OUTFLOW_TOP30 = "stock_outflow_top30"
CATEGORY_ABNORMAL_SECTOR_LEADER = "abnormal_sector_leader"
CATEGORY_VOLUME_MA5_CROSS_MA10 = "volume_ma5_cross_ma10"
CATEGORY_TURNOVER_TOP20 = "turnover_top20"
CATEGORY_LIMIT_UP_LAST_10_DAYS = "limit_up_last_10_days"
CATEGORY_DECLINE_SHRINK_VOLUME = "decline_shrink_volume"

# ========== 日志配置 ==========
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
