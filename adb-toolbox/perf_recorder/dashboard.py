"""Console dashboard: real-time terminal-based performance monitor."""

from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from typing import Callable

from .models import MetricKey, MetricSample


class ConsoleDashboard:
    """
    实时控制台看板：
    - FPS 曲线（文本条形图）
    - 帧时间分位图
    - CPU/GPU/温度同轴联动
    - 异常区间高亮
    """

    def __init__(
        self,
        refresh_interval_ms: int = 1000,
        max_history: int = 60,
        width: int = 80,
    ) -> None:
        self.refresh_interval_ms = refresh_interval_ms
        self.max_history = max_history
        self.width = width or self._terminal_width()
        # 历史数据缓冲区
        self._history: dict[tuple[str, str, MetricKey], list[float]] = defaultdict(list)
        self._last_render = 0
        self._running = False
        self._alerts: list[str] = []
        self._custom_lines: list[Callable[[], str]] = []

    def _terminal_width(self) -> int:
        try:
            return os.get_terminal_size().columns
        except (OSError, ValueError):
            return 80

    def add_custom_line(self, fn: Callable[[], str]) -> None:
        """添加自定义行（如设备状态、流统计）。"""
        self._custom_lines.append(fn)

    def add_alert(self, message: str) -> None:
        self._alerts.append(f"[{time.strftime('%H:%M:%S')}] {message}")

    def feed(self, samples: list[MetricSample]) -> None:
        """喂入采样数据。"""
        for s in samples:
            key = (s.device_id, s.app_id, s.metric_key)
            hist = self._history[key]
            hist.append(s.value)
            if len(hist) > self.max_history:
                hist.pop(0)

    def render(self) -> str:
        """生成当前帧的控制台输出。"""
        lines: list[str] = []
        lines.append("=" * self.width)
        lines.append("  Perf Recorder - Real-time Dashboard")
        lines.append("=" * self.width)

        # 告警区
        if self._alerts:
            lines.append("  [!] Alerts:")
            for alert in self._alerts[-5:]:
                lines.append(f"      {alert}")
            lines.append("")

        # 按设备分组显示
        devices: dict[str, list[tuple[tuple[str, str, MetricKey], list[float]]]] = defaultdict(list)
        for key, hist in self._history.items():
            devices[key[0]].append((key, hist))

        for device_id, metrics in devices.items():
            lines.append(f"  Device: {device_id}")
            lines.append("  " + "-" * (self.width - 4))

            # FPS 曲线
            for (dev_id, app_id, mkey), hist in metrics:
                if mkey == MetricKey.FPS:
                    latest = hist[-1] if hist else 0
                    bar = self._make_bar(hist, max_val=60, label="FPS")
                    lines.append(f"  {bar} {latest:.1f}")
                    break

            # CPU
            cpu_vals: list[float] = []
            for (dev_id, app_id, mkey), hist in metrics:
                if mkey == MetricKey.CPU_APP_PERCENT:
                    cpu_vals = hist
                    break
            if cpu_vals:
                latest = cpu_vals[-1]
                bar = self._make_bar(cpu_vals, max_val=100, label="CPU")
                lines.append(f"  {bar} {latest:.1f}%")

            # Memory
            mem_vals: list[float] = []
            for (dev_id, app_id, mkey), hist in metrics:
                if mkey == MetricKey.MEMORY_PSS_MB:
                    mem_vals = hist
                    break
            if mem_vals:
                latest = mem_vals[-1]
                lines.append(f"  Memory (PSS): {latest:.0f} MB")

            # Temperature
            temp_vals: list[float] = []
            for (dev_id, app_id, mkey), hist in metrics:
                if mkey == MetricKey.TEMPERATURE_C:
                    temp_vals = hist
                    break
            if temp_vals:
                latest = temp_vals[-1]
                lines.append(f"  Temperature:   {latest:.1f}°C")

            # GPU
            gpu_vals: list[float] = []
            for (dev_id, app_id, mkey), hist in metrics:
                if mkey == MetricKey.GPU_UTIL_PERCENT:
                    gpu_vals = hist
                    break
            if gpu_vals:
                latest = gpu_vals[-1]
                bar = self._make_bar(gpu_vals, max_val=100, label="GPU")
                lines.append(f"  {bar} {latest:.1f}%")

            # Frame Time
            ft_vals: list[float] = []
            for (dev_id, app_id, mkey), hist in metrics:
                if mkey == MetricKey.FRAME_TIME_MS:
                    ft_vals = hist
                    break
            if ft_vals:
                latest = ft_vals[-1]
                sorted_vals = sorted(ft_vals)
                p50 = sorted_vals[len(sorted_vals) // 2] if sorted_vals else 0
                p95 = sorted_vals[int(len(sorted_vals) * 0.95)] if len(sorted_vals) >= 2 else 0
                lines.append(f"  FrameTime:     avg={latest:.1f}ms  p50={p50:.1f}ms  p95={p95:.1f}ms")

            lines.append("")

        # 自定义行
        for fn in self._custom_lines:
            lines.append(f"  {fn()}")

        lines.append("=" * self.width)
        return "\n".join(lines)

    def _make_bar(self, values: list[float], max_val: float, label: str) -> str:
        """生成文本条形图。"""
        bar_width = 20
        if not values:
            return f"{label:>5} [{' ' * bar_width}]"
        # 取最近 N 个值
        recent = values[-bar_width:]
        chars = []
        for v in recent:
            ratio = min(v / max_val, 1.0) if max_val > 0 else 0
            if ratio >= 0.8:
                chars.append("#")
            elif ratio >= 0.5:
                chars.append("=")
            elif ratio >= 0.3:
                chars.append("-")
            else:
                chars.append(".")
        bar = "".join(chars).ljust(bar_width)
        return f"{label:>5} [{bar}]"

    def run(self, stop_event: Callable[[], bool] | None = None) -> None:
        """运行实时看板（阻塞式，按 Ctrl+C 退出）。"""
        self._running = True
        try:
            while self._running:
                if stop_event and stop_event():
                    break
                now = time.time() * 1000
                if now - self._last_render >= self.refresh_interval_ms:
                    sys.stdout.write("\033[2J\033[H")  # clear screen
                    sys.stdout.write(self.render())
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    self._last_render = now
                time.sleep(0.1)
        except KeyboardInterrupt:
            self._running = False

    def stop(self) -> None:
        self._running = False