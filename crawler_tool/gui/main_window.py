"""
主 GUI 界面 —— PyQt6 实现。
包含配置区、控制区、日志控制台、进度监控。
"""

import os
import sys
import multiprocessing
import logging
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QTextEdit, QFileDialog, QPlainTextEdit, QGridLayout,
    QProgressBar, QMessageBox, QCheckBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont

from utils.config_manager import ConfigManager
from gui.log_handler import LogHandler

logger = logging.getLogger(__name__)


# ============================================================
# 子进程入口 —— 必须是模块级函数才能被 pickle 序列化
# ============================================================
def _scrapy_worker(settings_dict: dict, spider_kwargs: dict, project_root: str):
    """
    在独立子进程中运行 Scrapy CrawlerProcess。
    必须放在模块级别，否则 multiprocessing 无法 pickle。
    """
    import sys
    import os

    # 设置子进程的工作目录和路径
    os.chdir(project_root)
    sys.path.insert(0, project_root)
    os.environ["SCRAPY_SETTINGS_MODULE"] = "scrapy_engine.settings"

    from scrapy.settings import Settings
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.log import configure_logging
    from scrapy_engine.spiders.universal_spider import UniversalSpider
    from scrapy_engine import middlewares

    # 注入代理列表
    middlewares.PROXY_LIST.clear()
    middlewares.PROXY_LIST.extend(settings_dict.pop("proxy_list", []))

    # 构建 Settings
    settings = Settings()
    settings.setmodule("scrapy_engine.settings", priority="default")

    # 覆写 GUI 传入的配置
    for key, value in settings_dict.items():
        if key != "proxy_list":
            settings.set(key, value)

    configure_logging(settings, install_root_handler=True)

    process = CrawlerProcess(settings)
    process.crawl(UniversalSpider, **spider_kwargs)
    process.start()


class CrawlerSignals(QObject):
    """爬虫进度信号"""
    progress_update = pyqtSignal(int, int)
    status_update = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("通用爬虫工具 - Universal Crawler Tool")
        self.setMinimumSize(1000, 750)
        self.resize(1100, 800)

        self.config_manager = ConfigManager()
        self.crawler_process = None   # multiprocessing.Process
        self.is_running = False
        self.signals = CrawlerSignals()

        # 统计
        self.downloaded_count = 0
        self.failed_count = 0
        self.start_time = None

        self._build_ui()
        self._connect_signals()
        self._setup_logger()

    # ---------- UI 构建 ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        config_group = self._build_config_panel()
        main_layout.addWidget(config_group)

        control_layout = QHBoxLayout()
        control_layout.addWidget(self._build_control_panel())
        control_layout.addWidget(self._build_progress_panel())
        main_layout.addLayout(control_layout)

        log_group = self._build_log_panel()
        main_layout.addWidget(log_group, 1)

    def _build_config_panel(self):
        group = QGroupBox("爬虫配置")
        layout = QGridLayout(group)
        layout.setSpacing(8)

        layout.addWidget(QLabel("目标 URL:"), 0, 0)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        layout.addWidget(self.url_input, 0, 1, 1, 3)

        layout.addWidget(QLabel("内容类型:"), 1, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "网页文本提取 (text)",
            "全站图片下载 (image)",
            "JSON API 数据解析 (json)",
            "自定义规则 (custom)",
        ])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_combo, 1, 1)

        layout.addWidget(QLabel("反爬强度:"), 1, 2)
        self.anti_combo = QComboBox()
        self.anti_combo.addItems([
            "基础模式 (Scrapy)",
            "强力伪装 (代理/Header)",
            "动态渲染 (Playwright)",
        ])
        layout.addWidget(self.anti_combo, 1, 3)

        # 自定义规则面板
        self.custom_rules_group = QWidget()
        custom_layout = QHBoxLayout(self.custom_rules_group)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.addWidget(QLabel("XPath:"))
        self.xpath_input = QLineEdit()
        self.xpath_input.setPlaceholderText("//div[@class='content']/text()")
        custom_layout.addWidget(self.xpath_input)
        custom_layout.addWidget(QLabel("CSS:"))
        self.css_input = QLineEdit()
        self.css_input.setPlaceholderText("div.content p::text")
        custom_layout.addWidget(self.css_input)
        layout.addWidget(self.custom_rules_group, 2, 0, 1, 4)
        self.custom_rules_group.hide()

        # 速率与安全
        rate_group = QGroupBox("速率与安全设置")
        rate_layout = QGridLayout(rate_group)
        rate_layout.setSpacing(6)
        rate_layout.addWidget(QLabel("爬取延迟(秒):"), 0, 0)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(0.5, 30)
        self.delay_spin.setValue(2.0)
        self.delay_spin.setSingleStep(0.5)
        rate_layout.addWidget(self.delay_spin, 0, 1)
        rate_layout.addWidget(QLabel("并发数:"), 0, 2)
        self.concurrency_spin = QSpinBox()
        self.concurrency_spin.setRange(1, 16)
        self.concurrency_spin.setValue(4)
        rate_layout.addWidget(self.concurrency_spin, 0, 3)
        rate_layout.addWidget(QLabel("最大页数:"), 1, 0)
        self.max_pages_spin = QSpinBox()
        self.max_pages_spin.setRange(1, 10000)
        self.max_pages_spin.setValue(100)
        rate_layout.addWidget(self.max_pages_spin, 1, 1)
        self.robotstxt_check = QCheckBox("遵守 robots.txt")
        self.robotstxt_check.setChecked(True)
        rate_layout.addWidget(self.robotstxt_check, 1, 2)
        layout.addWidget(rate_group, 3, 0, 1, 4)

        # 保存设置
        save_group = QGroupBox("保存设置")
        save_layout = QGridLayout(save_group)
        save_layout.setSpacing(6)
        save_layout.addWidget(QLabel("保存格式:"), 0, 0)
        self.save_format_combo = QComboBox()
        self.save_format_combo.addItems(["JSON", "CSV", "TXT"])
        save_layout.addWidget(self.save_format_combo, 0, 1)
        save_layout.addWidget(QLabel("保存路径:"), 0, 2)
        path_layout = QHBoxLayout()
        self.save_path_input = QLineEdit()
        self.save_path_input.setText(os.path.join(os.getcwd(), "output"))
        self.save_path_input.setReadOnly(True)
        path_layout.addWidget(self.save_path_input)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_save_path)
        path_layout.addWidget(browse_btn)
        save_layout.addLayout(path_layout, 0, 3)
        layout.addWidget(save_group, 4, 0, 1, 4)

        return group

    def _build_control_panel(self):
        group = QGroupBox("控制")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ 启动")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; padding: 8px 16px; "
            "font-size: 14px; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #45a049; }"
            "QPushButton:disabled { background-color: #ccc; }"
        )
        self.start_btn.clicked.connect(self._start_crawler)
        btn_layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("⏸ 暂停")
        self.pause_btn.setStyleSheet(
            "QPushButton { background-color: #FF9800; color: white; padding: 8px 16px; "
            "font-size: 14px; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #e68900; }"
            "QPushButton:disabled { background-color: #ccc; }"
        )
        self.pause_btn.clicked.connect(self._toggle_pause)
        self.pause_btn.setEnabled(False)
        btn_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setStyleSheet(
            "QPushButton { background-color: #f44336; color: white; padding: 8px 16px; "
            "font-size: 14px; font-weight: bold; border-radius: 4px; }"
            "QPushButton:hover { background-color: #d32f2f; }"
            "QPushButton:disabled { background-color: #ccc; }"
        )
        self.stop_btn.clicked.connect(self._stop_crawler)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        proxy_label = QLabel("代理列表 (每行一个 IP:Port):")
        proxy_label.setStyleSheet("font-size: 11px; color: #666;")
        layout.addWidget(proxy_label)
        self.proxy_input = QPlainTextEdit()
        self.proxy_input.setMaximumHeight(80)
        self.proxy_input.setPlaceholderText("127.0.0.1:8080\n192.168.1.1:3128")
        layout.addWidget(self.proxy_input)

        return group

    def _build_progress_panel(self):
        group = QGroupBox("进度监控")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("已下载:"))
        self.downloaded_label = QLabel("0")
        self.downloaded_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        stats_layout.addWidget(self.downloaded_label)
        stats_layout.addWidget(QLabel("失败:"))
        self.failed_label = QLabel("0")
        self.failed_label.setStyleSheet("font-weight: bold; color: #f44336;")
        stats_layout.addWidget(self.failed_label)
        stats_layout.addWidget(QLabel("耗时:"))
        self.elapsed_label = QLabel("00:00:00")
        self.elapsed_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.elapsed_label)
        stats_layout.addStretch()
        layout.addLayout(stats_layout)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)

        return group

    def _build_log_panel(self):
        group = QGroupBox("日志控制台")
        layout = QVBoxLayout(group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.log_text)

        clear_btn = QPushButton("清空日志")
        clear_btn.clicked.connect(self.log_text.clear)
        layout.addWidget(clear_btn, alignment=Qt.AlignmentFlag.AlignRight)

        return group

    # ---------- 信号连接 ----------
    def _connect_signals(self):
        self.signals.progress_update.connect(self._on_progress_update)
        self.signals.status_update.connect(self._on_status_update)
        self.signals.finished.connect(self._on_crawler_finished)
        self.signals.error.connect(self._on_crawler_error)

        self._timer = QTimer()
        self._timer.timeout.connect(self._update_elapsed)
        self._timer.setInterval(1000)

        # 子进程监控定时器
        self._process_monitor = QTimer()
        self._process_monitor.timeout.connect(self._check_process)
        self._process_monitor.setInterval(500)

    def _setup_logger(self):
        self.log_handler = LogHandler(self.log_text)

    # ---------- 槽函数 ----------
    def _on_mode_changed(self, idx):
        mode_key = self.mode_combo.currentText().split("(")[-1].rstrip(")")
        self.custom_rules_group.setVisible(mode_key == "custom")

    def _browse_save_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录")
        if path:
            self.save_path_input.setText(path)

    def _start_crawler(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "输入错误", "请输入目标 URL")
            return

        self._set_controls_enabled(True)
        self.log_text.clear()
        self.downloaded_count = 0
        self.failed_count = 0
        self.progress_bar.setValue(0)
        self.downloaded_label.setText("0")
        self.failed_label.setText("0")
        self.start_time = datetime.now()
        self._timer.start()

        gui_config = self._collect_gui_config()
        settings_dict = self.config_manager.get_settings_dict(gui_config)
        spider_kwargs = self.config_manager.build_spider_kwargs(gui_config)

        # 项目根目录 (crawler_tool/)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 使用 multiprocessing 在独立进程中运行 Scrapy
        self.crawler_process = multiprocessing.Process(
            target=_scrapy_worker,
            args=(settings_dict, spider_kwargs, project_root),
            daemon=True,
        )
        self.crawler_process.start()

        self._process_monitor.start()
        self.signals.status_update.emit("爬虫运行中...")
        logger.info(f"启动爬虫: {url}")
        logger.info(f"模式: {gui_config['mode']} | 反爬: {gui_config['anti_mode']} | 延迟: {gui_config['delay']}s")

    def _check_process(self):
        """监控子进程状态"""
        if self.crawler_process is None:
            self._process_monitor.stop()
            return
        if not self.crawler_process.is_alive():
            self._process_monitor.stop()
            exit_code = self.crawler_process.exitcode
            self.crawler_process = None
            if exit_code == 0:
                self.signals.finished.emit()
            elif exit_code is not None:
                self.signals.error.emit(f"子进程异常退出，退出码: {exit_code}")

    def _toggle_pause(self):
        if self.crawler_process:
            # 暂停/恢复通过 SIGSTOP/SIGCONT 在 Windows 上不可用
            # 改为终止并提示
            QMessageBox.information(self, "提示", "暂停功能在当前版本通过终止爬虫实现。\n点击停止后重新启动即可。")

    def _stop_crawler(self):
        if self.crawler_process and self.crawler_process.is_alive():
            self.crawler_process.terminate()
            self.crawler_process.join(timeout=3)
            if self.crawler_process.is_alive():
                self.crawler_process.kill()
            self.crawler_process = None
        self._process_monitor.stop()
        self._set_controls_enabled(False)
        self._timer.stop()
        self.signals.status_update.emit("爬虫已停止")
        logger.info("爬虫已停止")

    def _on_progress_update(self, current, total):
        if total > 0:
            self.progress_bar.setValue(int(current / total * 100))
        self.downloaded_label.setText(str(current))

    def _on_status_update(self, msg):
        self.status_label.setText(msg)

    def _on_crawler_finished(self):
        self._set_controls_enabled(False)
        self._timer.stop()
        self.signals.status_update.emit("爬取完成")
        logger.info("爬取完成")

    def _on_crawler_error(self, err_msg):
        self._set_controls_enabled(False)
        self._timer.stop()
        self.signals.status_update.emit("爬取出错")
        logger.error(f"爬虫错误: {err_msg}")

    def _update_elapsed(self):
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            total_sec = int(elapsed.total_seconds())
            h, m, s = total_sec // 3600, (total_sec % 3600) // 60, total_sec % 60
            self.elapsed_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _set_controls_enabled(self, running: bool):
        self.is_running = running
        self.start_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running)
        self.stop_btn.setEnabled(running)
        self.url_input.setEnabled(not running)
        self.mode_combo.setEnabled(not running)
        self.anti_combo.setEnabled(not running)

    def _collect_gui_config(self) -> dict:
        mode_text = self.mode_combo.currentText().split("(")[-1].rstrip(")")
        anti_text = self.anti_combo.currentText()
        if "基础" in anti_text:
            anti_key = "basic"
        elif "强力" in anti_text:
            anti_key = "aggressive"
        else:
            anti_key = "dynamic"

        return {
            "url": self.url_input.text().strip(),
            "mode": mode_text,
            "anti_mode": anti_key,
            "delay": self.delay_spin.value(),
            "concurrency": self.concurrency_spin.value(),
            "max_pages": self.max_pages_spin.value(),
            "save_format": self.save_format_combo.currentText().lower(),
            "save_path": self.save_path_input.text(),
            "proxies": self.proxy_input.toPlainText(),
            "custom_xpath": self.xpath_input.text().strip(),
            "custom_css": self.css_input.text().strip(),
            "robotstxt": self.robotstxt_check.isChecked(),
        }


def main():
    # 必须在创建 QApplication 之前设置 multiprocessing 的启动方式
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    app.setStyleSheet("""
        QGroupBox {
            font-weight: bold;
            border: 1px solid #ddd;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 16px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
        }
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            padding: 4px;
            border: 1px solid #ccc;
            border-radius: 3px;
        }
        QLineEdit:focus, QComboBox:focus {
            border-color: #4CAF50;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()