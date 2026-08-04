"""
日志处理器 —— 将 Scrapy 日志重定向到 GUI 控制台。
"""

import logging
from PyQt6.QtCore import QObject, pyqtSignal


class QTextEditLogger(logging.Handler):
    """
    自定义 logging Handler，将日志输出到 QTextEdit 控件。
    通过信号安全地跨线程更新 UI。
    """

    class _Signals(QObject):
        append_log = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__()
        self.signals = self._Signals(parent)
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "%H:%M:%S"
        ))

    def emit(self, record):
        msg = self.format(record)
        self.signals.append_log.emit(msg)

    def attach_to_widget(self, text_widget):
        """将信号连接到 QTextEdit"""
        self.signals.append_log.connect(text_widget.append)


class LogHandler:
    """统一管理日志路由"""

    def __init__(self, text_widget=None):
        self.handler = QTextEditLogger()
        self.handler.setLevel(logging.INFO)
        self.text_widget = text_widget

        if text_widget:
            self.handler.attach_to_widget(text_widget)

        # 捕获所有日志
        root_logger = logging.getLogger()
        root_logger.addHandler(self.handler)
        root_logger.setLevel(logging.INFO)

    def set_text_widget(self, widget):
        self.text_widget = widget
        self.handler.attach_to_widget(widget)

    def remove(self):
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.handler)