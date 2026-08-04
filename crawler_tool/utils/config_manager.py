"""
配置管理器 —— GUI 与 Scrapy 之间的桥梁。
负责将 GUI 配置转换为 Scrapy 可识别的 settings 与 spider 参数。
"""

import os
from scrapy.settings import Settings
from scrapy_engine.middlewares import PROXY_LIST


def _get_default_settings():
    """直接创建 Settings 对象并加载默认设置模块（避免 get_project_settings 路径问题）"""
    settings = Settings()
    settings_module_path = "scrapy_engine.settings"
    settings.setmodule(settings_module_path, priority="default")
    return settings


class ConfigManager:
    """解析 GUI 配置并生成 Scrapy 运行参数"""

    def __init__(self):
        self.settings = _get_default_settings()

    def build_spider_kwargs(self, gui_config: dict) -> dict:
        """
        将 GUI 传入的字典转换为 UniversalSpider 的 kwargs。
        """
        from urllib.parse import urlparse
        url = gui_config.get("url", "")
        allowed_domains = []
        if url:
            parsed = urlparse(url)
            allowed_domains = [parsed.netloc]

        return {
            "mode": gui_config.get("mode", "text"),
            "start_urls": [url] if url else [],
            "max_pages": gui_config.get("max_pages", 100),
            "custom_xpath": gui_config.get("custom_xpath", ""),
            "custom_css": gui_config.get("custom_css", ""),
            "allowed_domains": allowed_domains,
        }

    def apply_settings(self, gui_config: dict):
        """
        根据 GUI 配置覆写 Scrapy settings。
        """
        # 速率控制
        self.settings.set("DOWNLOAD_DELAY", gui_config.get("delay", 2))
        self.settings.set("CONCURRENT_REQUESTS", gui_config.get("concurrency", 4))
        self.settings.set("CONCURRENT_REQUESTS_PER_DOMAIN", gui_config.get("concurrency", 4))
        self.settings.set("DEPTH_LIMIT", gui_config.get("max_pages", 0))

        # robots.txt
        if not gui_config.get("robotstxt", True):
            self.settings.set("ROBOTSTXT_OBEY", False)

        # 反爬强度
        anti_mode = gui_config.get("anti_mode", "basic")
        if anti_mode == "basic":
            self._apply_basic_mode()
        elif anti_mode == "aggressive":
            self._apply_aggressive_mode()
        elif anti_mode == "dynamic":
            self._apply_dynamic_mode()

        # 保存设置
        save_format = gui_config.get("save_format", "json")
        save_path = gui_config.get("save_path", os.getcwd())

        self.settings.set("TEXT_OUTPUT_FORMAT", save_format)
        self.settings.set("TEXT_OUTPUT_DIR", os.path.join(save_path, "text_output"))
        self.settings.set("JSON_OUTPUT_DIR", os.path.join(save_path, "json_output"))
        self.settings.set("IMAGES_STORE", os.path.join(save_path, "images"))

        # 代理列表
        proxy_text = gui_config.get("proxies", "")
        PROXY_LIST.clear()
        if proxy_text:
            PROXY_LIST.extend([p.strip() for p in proxy_text.splitlines() if p.strip()])

        return self.settings

    def get_settings_dict(self, gui_config: dict) -> dict:
        """
        将所有 settings 转换为可序列化的 dict，用于跨进程传递。
        """
        self.apply_settings(gui_config)
        # 将 Settings 对象转为普通 dict
        result = {}
        for key in [
            "DOWNLOAD_DELAY", "CONCURRENT_REQUESTS", "CONCURRENT_REQUESTS_PER_DOMAIN",
            "DEPTH_LIMIT", "ROBOTSTXT_OBEY",
            "AUTOTHROTTLE_ENABLED", "AUTOTHROTTLE_START_DELAY", "AUTOTHROTTLE_MAX_DELAY",
            "AUTOTHROTTLE_TARGET_CONCURRENCY", "RETRY_TIMES", "RETRY_ENABLED",
            "TEXT_OUTPUT_FORMAT", "TEXT_OUTPUT_DIR", "JSON_OUTPUT_DIR",
            "IMAGES_STORE", "RANDOMIZE_DOWNLOAD_DELAY", "LOG_LEVEL",
            "DOWNLOADER_MIDDLEWARES", "ITEM_PIPELINES",
        ]:
            if key in self.settings:
                result[key] = self.settings.get(key)

        result["proxy_list"] = list(PROXY_LIST)
        return result

    def _apply_basic_mode(self):
        self.settings.set("AUTOTHROTTLE_ENABLED", True)
        self.settings.set("RETRY_TIMES", 3)

    def _apply_aggressive_mode(self):
        current_delay = self.settings.get("DOWNLOAD_DELAY", 2)
        self.settings.set("DOWNLOAD_DELAY", max(current_delay, 3))
        self.settings.set("AUTOTHROTTLE_ENABLED", True)
        self.settings.set("AUTOTHROTTLE_START_DELAY", 3)
        self.settings.set("RETRY_TIMES", 5)
        self.settings.set("CONCURRENT_REQUESTS", 1)
        self.settings.set("CONCURRENT_REQUESTS_PER_DOMAIN", 1)

    def _apply_dynamic_mode(self):
        current_delay = self.settings.get("DOWNLOAD_DELAY", 2)
        self.settings.set("DOWNLOAD_DELAY", max(current_delay, 4))
        self.settings.set("DOWNLOAD_HANDLERS", {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        })
        self.settings.set("TWISTED_REACTOR", "twisted.internet.asyncioreactor.AsyncioSelectorReactor")
        self.settings.set("PLAYWRIGHT_BROWSER_TYPE", "chromium")
        self.settings.set("PLAYWRIGHT_LAUNCH_OPTIONS", {
            "headless": True,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
        })