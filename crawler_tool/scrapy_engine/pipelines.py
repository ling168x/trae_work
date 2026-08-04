"""
通用 Pipeline：图片下载、文本清洗、JSON 导出。
"""

import os
import csv
import json
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

from scrapy.pipelines.images import ImagesPipeline

logger = logging.getLogger(__name__)


class ImageDownloadPipeline(ImagesPipeline):
    """
    图片下载 Pipeline：继承 Scrapy 内置 ImagesPipeline，智能命名。
    """

    def file_path(self, request, response=None, info=None, *, item=None):
        parsed = urlparse(request.url)
        domain = parsed.netloc.replace(":", "_")
        ext = os.path.splitext(parsed.path)[1] or ".jpg"
        url_hash = hashlib.md5(request.url.encode()).hexdigest()[:12]
        return f"{domain}/{url_hash}{ext}"

    def item_completed(self, results, item, info):
        for ok, result in results:
            if ok:
                logger.info(f"Image saved: {result.get('path', 'unknown')}")
            else:
                logger.warning(f"Image download failed: {result}")
        return item


class TextPipeline:
    """
    文本/网页内容提取 Pipeline：提取页面正文，导出 CSV/JSON/TXT。
    """

    def __init__(self):
        self.output_dir = "text_output"
        self.output_format = "json"
        self.items = []

    @classmethod
    def from_crawler(cls, crawler):
        pipe = cls()
        pipe.output_dir = crawler.settings.get("TEXT_OUTPUT_DIR", "text_output")
        pipe.output_format = crawler.settings.get("TEXT_OUTPUT_FORMAT", "json")
        return pipe

    def process_item(self, item):
        if item.get("type") == "text":
            self.items.append(dict(item))
        return item

    def close_spider(self):
        if not self.items:
            return
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        if self.output_format == "csv":
            filepath = os.path.join(self.output_dir, "extracted_text.csv")
            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=["url", "title", "text", "timestamp"])
                writer.writeheader()
                writer.writerows(self.items)
            logger.info(f"Text data exported to {filepath}")

        elif self.output_format == "json":
            filepath = os.path.join(self.output_dir, "extracted_text.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.items, f, ensure_ascii=False, indent=2)
            logger.info(f"Text data exported to {filepath}")

        elif self.output_format == "txt":
            filepath = os.path.join(self.output_dir, "extracted_text.txt")
            with open(filepath, "w", encoding="utf-8") as f:
                for item in self.items:
                    f.write(f"=== {item.get('title', '')} ===\n")
                    f.write(f"URL: {item.get('url', '')}\n\n")
                    f.write(item.get("text", "") + "\n\n")
                    f.write("-" * 60 + "\n\n")
            logger.info(f"Text data exported to {filepath}")


class JsonPipeline:
    """
    JSON API 数据 Pipeline：存储 API 返回的 JSON 数据。
    """

    def __init__(self):
        self.output_dir = "json_output"
        self.items = []

    @classmethod
    def from_crawler(cls, crawler):
        pipe = cls()
        pipe.output_dir = crawler.settings.get("JSON_OUTPUT_DIR", "json_output")
        return pipe

    def process_item(self, item):
        if item.get("type") == "json_data":
            self.items.append(dict(item))
        return item

    def close_spider(self):
        if not self.items:
            return
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        filepath = os.path.join(self.output_dir, "api_data.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON API data exported to {filepath}")