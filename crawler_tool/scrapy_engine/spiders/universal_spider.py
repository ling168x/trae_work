"""
通用适配爬虫 —— 支持图片、文本、JSON、自定义规则四种模式。
"""

import json
import re
import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

import scrapy

logger = logging.getLogger(__name__)


class UniversalSpider(scrapy.Spider):
    name = "universal_spider"

    def __init__(self, mode="text", start_urls=None, allowed_domains=None,
                 max_pages=100, custom_xpath="", custom_css="", **kwargs):
        super().__init__(**kwargs)

        self.mode = mode
        self.max_pages = int(max_pages)
        self.custom_xpath = custom_xpath
        self.custom_css = custom_css

        if start_urls:
            self.start_urls = list(start_urls) if isinstance(start_urls, (list, tuple)) else [start_urls]

        if allowed_domains:
            self.allowed_domains = list(allowed_domains) if isinstance(allowed_domains, (list, tuple)) else [allowed_domains]

        self.page_count = 0

    def parse(self, response):
        """主解析入口，根据 mode 分发"""
        self.page_count += 1

        if self.max_pages and self.page_count > self.max_pages:
            logger.info(f"Reached max pages limit: {self.max_pages}")
            return

        status = response.status
        logger.info(f"[{self.page_count}] Crawling: {response.url}  (HTTP {status})")

        # 非 200 响应：记录状态但不中断
        if status != 200:
            logger.warning(f"Got HTTP {status} for {response.url}")
            if status == 403:
                logger.warning(f"403 Forbidden - 网站可能启用了反爬保护，建议使用代理或降低请求频率")
            # 仍然尝试提取文本（有些网站 403 页面可能包含有用信息）
            if self.mode == "text":
                yield self._parse_text(response)
            return

        if self.mode == "image":
            yield from self._parse_images(response)
        elif self.mode == "text":
            yield self._parse_text(response)
        elif self.mode == "json":
            yield self._parse_json(response)
        elif self.mode == "custom":
            yield from self._parse_custom(response)

        # 跟进站内链接
        yield from self._follow_links(response)

    # ---------- 图片模式 ----------
    def _parse_images(self, response):
        for img in response.css("img"):
            src = img.attrib.get("src") or img.attrib.get("data-src") or ""
            if src:
                abs_url = urljoin(response.url, src)
                yield {
                    "type": "image",
                    "image_urls": [abs_url],
                    "referer": response.url,
                }

    # ---------- 文本模式 ----------
    def _parse_text(self, response):
        body_text = " ".join(response.css("body ::text").getall()).strip()
        body_text = re.sub(r"\s+", " ", body_text)[:50000]

        title = response.css("title::text").get("") or ""
        title = title.strip()

        return {
            "type": "text",
            "url": response.url,
            "title": title,
            "text": body_text,
            "timestamp": datetime.now().isoformat(),
        }

    # ---------- JSON 模式 ----------
    def _parse_json(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            logger.warning(f"Response is not valid JSON: {response.url}")
            return {
                "type": "json_data",
                "url": response.url,
                "raw": response.text[:5000],
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "type": "json_data",
            "url": response.url,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }

    # ---------- 自定义规则模式 ----------
    def _parse_custom(self, response):
        results = []

        if self.custom_xpath:
            nodes = response.xpath(self.custom_xpath)
            for node in nodes:
                val = node.get() if hasattr(node, "get") else str(node)
                results.append({
                    "type": "custom",
                    "url": response.url,
                    "xpath": self.custom_xpath,
                    "text": val,
                })

        if self.custom_css:
            nodes = response.css(self.custom_css)
            for node in nodes:
                val = node.get() if hasattr(node, "get") else str(node)
                results.append({
                    "type": "custom",
                    "url": response.url,
                    "css": self.custom_css,
                    "text": val,
                })

        if not results:
            logger.warning(f"No matches for custom rules on {response.url}")
            results.append({
                "type": "custom",
                "url": response.url,
                "raw": response.text[:5000],
            })

        yield from results

    # ---------- 链接跟进 ----------
    def _follow_links(self, response):
        if self.max_pages and self.page_count >= self.max_pages:
            return

        skip_ext = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
                    ".pdf", ".zip", ".rar", ".7z", ".mp4", ".avi", ".mov",
                    ".css", ".js", ".ico", ".woff", ".woff2", ".ttf")

        for link in response.css("a::attr(href)").getall():
            abs_url = urljoin(response.url, link)
            parsed = urlparse(abs_url)

            # 仅 http/https
            if parsed.scheme not in ("http", "https"):
                continue

            # 仅同域名
            if self.allowed_domains and parsed.netloc not in self.allowed_domains:
                continue

            # 过滤静态资源
            if parsed.path.lower().endswith(skip_ext):
                continue

            yield scrapy.Request(abs_url, callback=self.parse)