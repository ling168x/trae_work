"""Perf Recorder GUI - PerfDog-style real-time performance monitor."""

from __future__ import annotations

import sys
import time
import os
from datetime import datetime
from pathlib import Path
from collections import deque
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt5 import QtCore, QtGui, QtWidgets
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import matplotlib.ticker as ticker

from perf_recorder import (
    PerfRecorderHost, SessionConfig, AdbBridge, AdbDevice,
    MetricKey, MetricSample, AlertManager, AlertRule, AlertOperator,
    UNITY_PROFILE, GENERIC_PROFILE,
)

# ── Color Theme ──────────────────────────────────────────────────
THEME = {
    "bg_dark": "#1a1a2e",
    "bg_card": "#16213e",
    "bg_input": "#0f3460",
    "accent": "#e94560",
    "accent_green": "#4ecca3",
    "accent_yellow": "#ffc107",
    "text": "#eeeeee",
    "text_muted": "#888888",
    "chart_bg": "#0f1a2e",
    "chart_grid": "#1a2a4e",
    "fps_color": "#e94560",
    "cpu_color": "#4ecca3",
    "gpu_color": "#9b59b6",
    "mem_color": "#3498db",
    "temp_color": "#ffc107",
    "frame_color": "#e67e22",
}

CHART_COLORS = {
    "fps": THEME["fps_color"],
    "cpu_app_percent": THEME["cpu_color"],
    "cpu_total_percent": "#2ecc71",
    "gpu_util_percent": THEME["gpu_color"],
    "memory_pss_mb": THEME["mem_color"],
    "temperature_c": THEME["temp_color"],
    "frame_time_ms": THEME["frame_color"],
}

# ── Data Collector Worker ────────────────────────────────────────

class CollectWorker(QtCore.QThread):
    """后台采集线程，通过信号将数据发送到主线程。"""
    samples_ready = QtCore.pyqtSignal(list)
    status_update = QtCore.pyqtSignal(str)
    session_finished = QtCore.pyqtSignal(dict)
    error_occurred = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.host: PerfRecorderHost | None = None
        self.config: SessionConfig | None = None
        self._running = False

    def setup(self, host: PerfRecorderHost, config: SessionConfig) -> None:
        self.host = host
        self.config = config

    def run(self) -> None:
        if not self.host or not self.config:
            return
        self._running = True
        end_at = time.time() + self.config.duration_sec
        last_poll = 0

        while time.time() < end_at and self._running:
            now = int(time.time() * 1000)
            if now - last_poll < self.config.poll_interval_ms:
                time.sleep(0.02)
                continue
            last_poll = now

            samples: list[MetricSample] = []
            for c in self.host._collectors:
                try:
                    samples.extend(c.poll())
                except Exception:
                    pass

            if samples:
                self.samples_ready.emit(samples)
                self.host.stream_bus.publish(samples)
                triggered = self.host.alert_manager.evaluate(samples)
                for alert in triggered:
                    self.status_update.emit(f"ALERT: {alert.rule.label}")

                emit_batch = self.host.stream_bus.emit()
                for s in emit_batch:
                    self.host.storage.write(s)

        self.host.session_manager.end_session()
        self.session_finished.emit({"status": "completed"})

    def stop(self) -> None:
        self._running = False


# ── Realtime Chart Widget ────────────────────────────────────────

class RealtimeChart(FigureCanvas):
    """单个实时折线图，支持多指标叠加。"""

    def __init__(self, title: str, ylabel: str, max_points: int = 120) -> None:
        self.fig = Figure(figsize=(8, 2.2), dpi=100, facecolor=THEME["chart_bg"])
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(THEME["chart_bg"])
        super().__init__(self.fig)

        self.max_points = max_points
        self.title = title
        self.ylabel = ylabel
        self.lines: dict[str, Any] = {}
        self.data: dict[str, deque[tuple[float, float]]] = {}  # key -> [(time, value), ...]

        self._setup_style()
        self.fig.tight_layout(pad=1.5)

    def _setup_style(self) -> None:
        self.ax.set_title(self.title, color=THEME["text"], fontsize=10, fontweight="bold", pad=4)
        self.ax.set_ylabel(self.ylabel, color=THEME["text_muted"], fontsize=8)
        self.ax.tick_params(colors=THEME["text_muted"], labelsize=7)
        self.ax.grid(True, color=THEME["chart_grid"], linewidth=0.5, alpha=0.6)
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)
        self.ax.spines["bottom"].set_color(THEME["chart_grid"])
        self.ax.spines["left"].set_color(THEME["chart_grid"])
        self.ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: ""))

    def add_line(self, key: str, color: str, label: str = "") -> None:
        if key in self.lines:
            return
        (line,) = self.ax.plot([], [], color=color, linewidth=1.2, label=label or key, alpha=0.9)
        self.lines[key] = line
        self.data[key] = deque(maxlen=self.max_points)
        if len(self.lines) > 1:
            self.ax.legend(loc="upper right", fontsize=6, labelcolor=THEME["text_muted"],
                           framealpha=0.3, facecolor=THEME["bg_card"], edgecolor="none")

    def push(self, key: str, timestamp: float, value: float) -> None:
        if key not in self.data:
            return
        self.data[key].append((timestamp, value))

    def refresh(self) -> None:
        for key, line in self.lines.items():
            d = self.data[key]
            if not d:
                continue
            xs = [p[0] for p in d]
            ys = [p[1] for p in d]
            line.set_data(xs, ys)

        all_xs: list[float] = []
        for d in self.data.values():
            if d:
                all_xs.extend([p[0] for p in d])
        if all_xs:
            margin = max(5.0, (max(all_xs) - min(all_xs)) * 0.05)
            self.ax.set_xlim(min(all_xs) - margin, max(all_xs) + margin)

        # Auto Y range
        all_ys: list[float] = []
        for d in self.data.values():
            if d:
                all_ys.extend([p[1] for p in d])
        if all_ys:
            y_min = min(all_ys)
            y_max = max(all_ys)
            y_range = y_max - y_min or 1
            self.ax.set_ylim(y_min - y_range * 0.1, y_max + y_range * 0.15)

        self.draw_idle()


# ── Device List Widget ───────────────────────────────────────────

class DeviceListWidget(QtWidgets.QWidget):
    device_selected = QtCore.pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.bridge = AdbBridge()
        self._layout = QtWidgets.QVBoxLayout(self)
        self._layout.setContentsMargins(6, 6, 6, 6)

        title = QtWidgets.QLabel("DEVICES")
        title.setStyleSheet(f"color:{THEME['accent']};font-weight:bold;font-size:11px;")
        self._layout.addWidget(title)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background: {THEME['bg_input']};
                color: {THEME['text']};
                border: 1px solid {THEME['chart_grid']};
                border-radius: 4px;
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 6px 8px;
                border-bottom: 1px solid {THEME['chart_grid']};
            }}
            QListWidget::item:selected {{
                background: {THEME['accent']};
                color: white;
            }}
            QListWidget::item:hover {{
                background: {THEME['bg_card']};
            }}
        """)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self._layout.addWidget(self.list_widget)

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.setStyleSheet(self._btn_style())
        self.refresh_btn.clicked.connect(self.refresh)
        self._layout.addWidget(self.refresh_btn)

        self.refresh()

    def _btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: {THEME['bg_input']};
                color: {THEME['text']};
                border: 1px solid {THEME['chart_grid']};
                border-radius: 4px;
                padding: 6px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background: {THEME['accent']}; }}
        """

    def refresh(self) -> None:
        self.list_widget.clear()
        try:
            devices = self.bridge.list_devices()
            for d in devices:
                icon = "O" if d.is_ready else "X"
                item = QtWidgets.QListWidgetItem(f"{icon}  {d.serial}  [{d.model or 'unknown'}]")
                item.setData(QtCore.Qt.UserRole, d.serial)
                if not d.is_ready:
                    item.setForeground(QtGui.QColor(THEME["text_muted"]))
                self.list_widget.addItem(item)
        except Exception:
            item = QtWidgets.QListWidgetItem("No ADB / devices found")
            item.setForeground(QtGui.QColor(THEME["text_muted"]))
            self.list_widget.addItem(item)

    def _on_item_clicked(self, item: QtWidgets.QListWidgetItem) -> None:
        serial = item.data(QtCore.Qt.UserRole)
        if serial:
            self.device_selected.emit(serial)

    def selected_serial(self) -> str | None:
        item = self.list_widget.currentItem()
        if item:
            return item.data(QtCore.Qt.UserRole)
        # 返回第一个就绪设备
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            if it and it.data(QtCore.Qt.UserRole):
                return it.data(QtCore.Qt.UserRole)
        return None


# ── Control Panel ────────────────────────────────────────────────

class ControlPanel(QtWidgets.QWidget):
    start_clicked = QtCore.pyqtSignal(dict)
    stop_clicked = QtCore.pyqtSignal()
    export_clicked = QtCore.pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(6, 6, 6, 6)

        # App ID
        self._layout.addWidget(QtWidgets.QLabel("App:"))
        self.app_input = QtWidgets.QLineEdit("com.example.game")
        self.app_input.setStyleSheet(self._input_style())
        self.app_input.setFixedWidth(200)
        self._layout.addWidget(self.app_input)

        # Duration
        self._layout.addWidget(QtWidgets.QLabel("Duration(s):"))
        self.duration_spin = QtWidgets.QSpinBox()
        self.duration_spin.setRange(10, 3600)
        self.duration_spin.setValue(60)
        self.duration_spin.setStyleSheet(self._input_style())
        self._layout.addWidget(self.duration_spin)

        # Profile
        self._layout.addWidget(QtWidgets.QLabel("Profile:"))
        self.profile_combo = QtWidgets.QComboBox()
        self.profile_combo.addItems(["unity", "generic"])
        self.profile_combo.setStyleSheet(self._input_style())
        self._layout.addWidget(self.profile_combo)

        self._layout.addStretch()

        # Buttons
        self.start_btn = QtWidgets.QPushButton("START")
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {THEME['accent_green']};
                color: #1a1a2e;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
            }}
            QPushButton:hover {{ background: #5ee0b5; }}
            QPushButton:disabled {{ background: #555; color: #888; }}
        """)
        self.start_btn.clicked.connect(self._on_start)
        self._layout.addWidget(self.start_btn)

        self.stop_btn = QtWidgets.QPushButton("STOP")
        self.stop_btn.setStyleSheet(f"""
            QPushButton {{
                background: {THEME['accent']};
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
            }}
            QPushButton:hover {{ background: #ff5a7a; }}
            QPushButton:disabled {{ background: #555; color: #888; }}
        """)
        self.stop_btn.clicked.connect(lambda: self.stop_clicked.emit())
        self.stop_btn.setEnabled(False)
        self._layout.addWidget(self.stop_btn)

        self.export_btn = QtWidgets.QPushButton("Export")
        self.export_btn.setStyleSheet(self._btn_style())
        self.export_btn.clicked.connect(lambda: self.export_clicked.emit())
        self._layout.addWidget(self.export_btn)

    def _input_style(self) -> str:
        return f"""
            background: {THEME['bg_input']};
            color: {THEME['text']};
            border: 1px solid {THEME['chart_grid']};
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 12px;
        """

    def _btn_style(self) -> str:
        return f"""
            QPushButton {{
                background: {THEME['bg_input']};
                color: {THEME['text']};
                border: 1px solid {THEME['chart_grid']};
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 12px;
            }}
            QPushButton:hover {{ background: {THEME['accent']}; }}
        """

    def _on_start(self) -> None:
        self.start_clicked.emit({
            "app_id": self.app_input.text().strip(),
            "duration_sec": self.duration_spin.value(),
            "profile_name": self.profile_combo.currentText(),
        })

    def set_recording(self, recording: bool) -> None:
        self.start_btn.setEnabled(not recording)
        self.stop_btn.setEnabled(recording)
        self.app_input.setEnabled(not recording)
        self.duration_spin.setEnabled(not recording)
        self.profile_combo.setEnabled(not recording)


# ── Status Bar ───────────────────────────────────────────────────

class StatusBar(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 4)

        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setStyleSheet(f"color:{THEME['accent_green']};font-size:11px;")
        self._layout.addWidget(self.status_label)

        self._layout.addStretch()

        self.sample_label = QtWidgets.QLabel("Samples: 0")
        self.sample_label.setStyleSheet(f"color:{THEME['text_muted']};font-size:11px;")
        self._layout.addWidget(self.sample_label)

        sep = QtWidgets.QLabel("  |  ")
        sep.setStyleSheet(f"color:{THEME['chart_grid']};")
        self._layout.addWidget(sep)

        self.time_label = QtWidgets.QLabel("00:00")
        self.time_label.setStyleSheet(f"color:{THEME['text_muted']};font-size:11px;")
        self._layout.addWidget(self.time_label)

    def set_status(self, text: str, color: str = THEME["accent_green"]) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color:{color};font-size:11px;")

    def set_samples(self, count: int) -> None:
        self.sample_label.setText(f"Samples: {count}")

    def set_time(self, seconds: int) -> None:
        self.time_label.setText(f"{seconds // 60:02d}:{seconds % 60:02d}")


# ── Main Window ──────────────────────────────────────────────────

class PerfRecorderGUI(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Perf Recorder - Performance Monitor")
        self.setMinimumSize(1280, 820)
        self.resize(1400, 900)
        self.setStyleSheet(f"background-color: {THEME['bg_dark']}; color: {THEME['text']};")

        # 核心组件
        self.host: PerfRecorderHost | None = None
        self.worker: CollectWorker | None = None
        self._sample_count = 0
        self._start_time = 0
        self._charts: dict[str, RealtimeChart] = {}
        self._chart_keys_map: dict[str, list[str]] = {}
        self._recording = False

        self._init_ui()
        self._init_host()

    def _init_host(self) -> None:
        try:
            self.host = PerfRecorderHost(db_path="./perf_data.db")
            self.status_bar.set_status("Connected", THEME["accent_green"])
        except Exception as e:
            self.status_bar.set_status(f"Init error: {e}", THEME["accent"])

    # ── UI Layout ─────────────────────────────────────────────────

    def _init_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 标题栏
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("PERF RECORDER")
        title.setStyleSheet(f"color:{THEME['accent']};font-size:18px;font-weight:bold;letter-spacing:2px;")
        header.addWidget(title)
        header.addStretch()
        version = QtWidgets.QLabel("v1.0  |  Android/iOS Performance Monitor")
        version.setStyleSheet(f"color:{THEME['text_muted']};font-size:10px;")
        header.addWidget(version)
        main_layout.addLayout(header)

        # 控制栏
        self.control_panel = ControlPanel()
        self.control_panel.start_clicked.connect(self._on_start)
        self.control_panel.stop_clicked.connect(self._on_stop)
        self.control_panel.export_clicked.connect(self._on_export)
        main_layout.addWidget(self.control_panel)

        # 主体：左侧设备列表 + 右侧图表
        body = QtWidgets.QHBoxLayout()
        body.setSpacing(8)

        # 左侧面板
        left_panel = QtWidgets.QVBoxLayout()
        self.device_list = DeviceListWidget()
        self.device_list.device_selected.connect(self._on_device_selected)
        left_panel.addWidget(self.device_list, stretch=1)

        # 设备信息
        self.device_info = QtWidgets.QLabel("Select a device")
        self.device_info.setStyleSheet(f"""
            color: {THEME['text_muted']};
            font-size: 10px;
            padding: 8px;
            background: {THEME['bg_input']};
            border-radius: 4px;
        """)
        self.device_info.setWordWrap(True)
        left_panel.addWidget(self.device_info)

        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setFixedWidth(260)
        body.addWidget(left_widget)

        # 右侧图表面板
        chart_scroll = QtWidgets.QScrollArea()
        chart_scroll.setWidgetResizable(True)
        chart_scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {THEME['bg_dark']}; }}")

        chart_container = QtWidgets.QWidget()
        chart_layout = QtWidgets.QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(4)

        # 创建图表
        chart_defs = [
            ("fps_chart", "FPS", "fps", ["fps"], False),
            ("frame_chart", "Frame Time", "ms", ["frame_time_ms", "frame_time_p95_ms"], False),
            ("cpu_chart", "CPU Usage", "%", ["cpu_app_percent", "cpu_total_percent"], False),
            ("gpu_chart", "GPU", "% / MHz", ["gpu_util_percent", "gpu_freq_mhz"], True),
            ("mem_chart", "Memory", "MB", ["memory_pss_mb", "memory_resident_mb"], False),
            ("temp_chart", "Temperature", "C", ["temperature_c"], False),
        ]

        for chart_id, title, ylabel, keys, is_dual in chart_defs:
            chart = RealtimeChart(title, ylabel, max_points=150)
            for k in keys:
                color = CHART_COLORS.get(k, THEME["text"])
                label = k.replace("_", " ").title()
                chart.add_line(k, color, label)
            chart.setMinimumHeight(160)
            chart.setMaximumHeight(200)
            chart_layout.addWidget(chart)
            self._charts[chart_id] = chart
            self._chart_keys_map[chart_id] = keys

        chart_layout.addStretch()
        chart_scroll.setWidget(chart_container)
        body.addWidget(chart_scroll, stretch=1)

        main_layout.addLayout(body, stretch=1)

        # 状态栏
        self.status_bar = StatusBar()
        main_layout.addWidget(self.status_bar)

        # 定时器：刷新图表
        self._chart_timer = QtCore.QTimer()
        self._chart_timer.timeout.connect(self._refresh_charts)
        self._chart_timer.start(250)  # 每 250ms 刷新一次

        # 定时器：更新计时
        self._time_timer = QtCore.QTimer()
        self._time_timer.timeout.connect(self._update_time)
        self._time_timer.start(1000)

    # ── Event Handlers ────────────────────────────────────────────

    def _on_device_selected(self, serial: str) -> None:
        try:
            info = self.host.bridge.get_device_info(serial) if self.host else None
            if info:
                self.device_info.setText(
                    f"Model: {info.model}\n"
                    f"Manufacturer: {info.manufacturer}\n"
                    f"Android: {info.android_version} (SDK {info.sdk_level})\n"
                    f"ABI: {info.abi}\n"
                    f"GPU: {self.host.bridge.detect_gpu_vendor(serial)}"
                )
        except Exception:
            pass

    def _on_start(self, params: dict) -> None:
        serial = self.device_list.selected_serial()
        if not serial:
            QtWidgets.QMessageBox.warning(self, "Error", "No device selected!")
            return
        if not params.get("app_id"):
            QtWidgets.QMessageBox.warning(self, "Error", "App ID is required!")
            return
        if not self.host:
            self._init_host()
            if not self.host:
                return

        self._recording = True
        self._sample_count = 0
        self._start_time = int(time.time())

        self.control_panel.set_recording(True)
        self.status_bar.set_status("Recording...", THEME["accent"])

        # 配置并启动
        self.host.setup_device(serial, params["app_id"], profile_name=params["profile_name"])
        config = SessionConfig(
            app_id=params["app_id"],
            duration_sec=params["duration_sec"],
            poll_interval_ms=500,
            profile_name=params["profile_name"],
            device_serials=[serial],
        )

        self.worker = CollectWorker()
        self.worker.setup(self.host, config)
        self.worker.samples_ready.connect(self._on_samples)
        self.worker.status_update.connect(lambda msg: self.status_bar.set_status(msg, THEME["accent_yellow"]))
        self.worker.session_finished.connect(self._on_finished)
        self.worker.start()

        self.status_bar.set_status(f"Recording [{params['app_id']}] ...", THEME["accent"])

    def _on_stop(self) -> None:
        if self.worker:
            self.worker.stop()
            self.worker.wait(2000)
        self._recording = False
        self.control_panel.set_recording(False)
        self.status_bar.set_status("Stopped", THEME["accent_yellow"])

    def _on_samples(self, samples: list[MetricSample]) -> None:
        self._sample_count += len(samples)
        now = time.time()

        for s in samples:
            key = s.metric_key.value
            for chart_id, keys in self._chart_keys_map.items():
                if key in keys and chart_id in self._charts:
                    self._charts[chart_id].push(key, now, s.value)

        self.status_bar.set_samples(self._sample_count)

    def _on_finished(self, result: dict) -> None:
        self._recording = False
        self.control_panel.set_recording(False)
        self.status_bar.set_status("Recording completed", THEME["accent_green"])
        QtWidgets.QMessageBox.information(self, "Done", f"Recording finished!\n{self._sample_count} samples collected.")

    def _on_export(self) -> None:
        if not self.host:
            return
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select output directory")
        if not out_dir:
            return
        try:
            paths = self.host.export_report(out_dir, title=f"Perf Report - {datetime.now():%Y-%m-%d %H:%M:%S}")
            QtWidgets.QMessageBox.information(
                self, "Export Success",
                f"Reports saved:\nHTML: {paths['html']}\nCSV: {paths['csv']}\nJSON: {paths['json']}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", str(e))

    def _refresh_charts(self) -> None:
        for chart in self._charts.values():
            chart.refresh()

    def _update_time(self) -> None:
        if self._recording and self._start_time:
            elapsed = int(time.time()) - self._start_time
            self.status_bar.set_time(elapsed)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self._recording:
            reply = QtWidgets.QMessageBox.question(
                self, "Confirm", "Recording in progress. Stop and exit?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply == QtWidgets.QMessageBox.No:
                event.ignore()
                return
            self._on_stop()
        if self.worker:
            self.worker.stop()
            self.worker.wait(2000)
        if self.host:
            self.host.close()
        event.accept()


# ── Entry Point ──────────────────────────────────────────────────

def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    # 全局暗色主题
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(THEME["bg_dark"]))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(THEME["text"]))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(THEME["bg_input"]))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(THEME["text"]))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(THEME["bg_input"]))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(THEME["text"]))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(THEME["accent"]))
    app.setPalette(palette)

    window = PerfRecorderGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()