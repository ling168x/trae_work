"""
Scrapy 默认配置 —— 速率限制、反爬基础设置。
运行时由 config_manager.py 动态覆盖部分参数。
"""

BOT_NAME = "universal_crawler"

SPIDER_MODULES = ["scrapy_engine.spiders"]
NEWSPIDER_MODULE = "scrapy_engine.spiders"

# ---------- 礼貌爬取 ----------
ROBOTSTXT_OBEY = True
DOWNLOAD_DELAY = 2          # 默认 2 秒间隔
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 4

# ---------- 自动限速 ----------
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# ---------- 重试 ----------
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429, 403]

# ---------- 允许非 200 响应通过 ----------
HTTPERROR_ALLOWED_CODES = [403, 404, 500, 502, 503]

# ---------- 中间件 ----------
DOWNLOADER_MIDDLEWARES = {
    "scrapy_engine.middlewares.UserAgentMiddleware": 400,
    "scrapy_engine.middlewares.ProxyMiddleware": 410,
    "scrapy_engine.middlewares.RefererMiddleware": 420,
    "scrapy_engine.middlewares.CookieMiddleware": 430,
    "scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware": None,
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
}

# ---------- Pipeline ----------
ITEM_PIPELINES = {
    "scrapy_engine.pipelines.ImageDownloadPipeline": 300,
    "scrapy_engine.pipelines.TextPipeline": 310,
    "scrapy_engine.pipelines.JsonPipeline": 320,
}

# ---------- 图片存储 ----------
IMAGES_STORE = "downloaded_images"

# ---------- 日志 ----------
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"

# ---------- 深度限制 ----------
DEPTH_LIMIT = 0   # 0 = 不限，运行时由 GUI 覆盖

# ---------- 请求头伪装 ----------
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}