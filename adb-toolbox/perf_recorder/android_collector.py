"""Enhanced Android collector: non-invasive ADB-based metrics with vendor-aware GPU/temp paths."""

from __future__ import annotations

import re
import time
from statistics import median
from typing import Any

from .adb_bridge import AdbBridge
from .collector_base import Collector
from .models import ConfidenceLevel, MetricKey, MetricSample, MetricSource


class AndroidCollector(Collector):
    """无侵入 Android 性能采集器，通过 ADB 拉取系统指标。"""

    def __init__(
        self,
        serial: str,
        app_id: str,
        bridge: AdbBridge | None = None,
        *,
        collect_gpu: bool = True,
        collect_network: bool = False,
        collect_thermal_zones: bool = True,
        collect_frame_stats: bool = True,
    ) -> None:
        self.serial = serial
        self.app_id = app_id
        self.bridge = bridge or AdbBridge()
        self.collect_gpu = collect_gpu
        self.collect_network = collect_network
        self.collect_thermal_zones = collect_thermal_zones
        self.collect_frame_stats = collect_frame_stats
        self.seq = 0

        # 缓存设备能力
        self._gpu_vendor: str | None = None
        self._gpu_node_path: str | None = None
        self._thermal_nodes: list[str] = []
        self._thermal_types: dict[str, str] = {}
        self._prev_battery_ua: float | None = None
        self._prev_battery_ts: int = 0
        self._frame_time_history: list[float] = []

    def _next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def _shell(self, cmd: str) -> str:
        return self.bridge.shell(self.serial, cmd)

    def _lazy_init(self) -> None:
        """延迟初始化设备能力探测。"""
        if self._gpu_vendor is None:
            self._gpu_vendor = self.bridge.detect_gpu_vendor(self.serial)
            self._gpu_node_path = self.bridge.get_gpu_node_path(self.serial)
        if self.collect_thermal_zones and not self._thermal_nodes:
            self._thermal_nodes = self.bridge.get_temperature_nodes(self.serial)
            self._thermal_types = self.bridge.get_temperature_types(self.serial)

    def _make_sample(
        self,
        now_ms: int,
        key: MetricKey,
        value: float,
        unit: str,
        source: MetricSource = MetricSource.ANDROID_SYSTEM,
        confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM,
        **tags: str,
    ) -> MetricSample:
        return MetricSample(
            timestamp_ms=now_ms,
            device_id=self.serial,
            app_id=self.app_id,
            metric_key=key,
            value=value,
            unit=unit,
            source=source,
            confidence=confidence,
            sequence=self._next_seq(),
            tags=tags if tags else {},
        )

    # ── Poll ──────────────────────────────────────────────────────

    def poll(self) -> list[MetricSample]:
        self._lazy_init()
        now = int(time.time() * 1000)
        out: list[MetricSample] = []

        out.extend(self._poll_cpu(now))
        out.extend(self._poll_memory(now))
        out.extend(self._poll_temperature(now))
        out.extend(self._poll_battery(now))
        if self.collect_gpu:
            out.extend(self._poll_gpu(now))
        if self.collect_frame_stats:
            out.extend(self._poll_frame_stats(now))
        if self.collect_network:
            out.extend(self._poll_network(now))

        return out

    # ── CPU ───────────────────────────────────────────────────────

    def _poll_cpu(self, now: int) -> list[MetricSample]:
        out: list[MetricSample] = []

        # Total CPU usage
        cpu_text = self._shell("top -n 1 -b 2>/dev/null")
        cpu_match = re.search(r"(\d+)%cpu", cpu_text.lower())
        if cpu_match:
            out.append(self._make_sample(now, MetricKey.CPU_TOTAL_PERCENT, float(cpu_match.group(1)), "%"))

        # App CPU
        if self.app_id:
            app_cpu_text = self._shell(f"dumpsys cpuinfo 2>/dev/null | grep -E '{re.escape(self.app_id)}'")
            app_cpu_match = re.search(r"([\d.]+)%", app_cpu_text)
            if app_cpu_match:
                out.append(self._make_sample(now, MetricKey.CPU_APP_PERCENT, float(app_cpu_match.group(1)), "%"))

        return out

    # ── Memory ────────────────────────────────────────────────────

    def _poll_memory(self, now: int) -> list[MetricSample]:
        out: list[MetricSample] = []
        if not self.app_id:
            return out

        mem_text = self._shell(f"dumpsys meminfo {self.app_id} 2>/dev/null")
        if not mem_text:
            return out

        # PSS (Total)
        pss_match = re.search(r"TOTAL PSS:\s+(\d+)", mem_text)
        if pss_match:
            out.append(self._make_sample(now, MetricKey.MEMORY_PSS_MB, float(pss_match.group(1)) / 1024.0, "MB", confidence=ConfidenceLevel.HIGH))

        # Resident (Native Heap + Dalvik + Stack + .so mmap 等作为近似)
        # 更准确的方式是读取 /proc/[pid]/status VmRSS
        pid = self.bridge.get_pid(self.serial, self.app_id)
        if pid:
            status = self._shell(f"cat /proc/{pid}/status 2>/dev/null")
            rss_match = re.search(r"VmRSS:\s+(\d+)", status)
            if rss_match:
                out.append(self._make_sample(now, MetricKey.MEMORY_RESIDENT_MB, float(rss_match.group(1)) / 1024.0, "MB", confidence=ConfidenceLevel.HIGH))

        return out

    # ── Temperature & Thermal ─────────────────────────────────────

    def _poll_temperature(self, now: int) -> list[MetricSample]:
        out: list[MetricSample] = []

        # Battery temperature (通用)
        battery_text = self._shell("dumpsys battery 2>/dev/null")
        temp_match = re.search(r"temperature:\s*(\d+)", battery_text)
        if temp_match:
            out.append(self._make_sample(now, MetricKey.TEMPERATURE_C, float(temp_match.group(1)) / 10.0, "C", confidence=ConfidenceLevel.MEDIUM))

        # Thermal zones (多传感器)
        for node in self._thermal_nodes:
            type_name = self._thermal_types.get(node, node.split("/")[-1])
            temp_val = self._shell(f"cat {node}/temp 2>/dev/null").strip()
            if temp_val and temp_val.lstrip("-").isdigit():
                out.append(
                    self._make_sample(
                        now,
                        MetricKey.TEMPERATURE_C,
                        float(temp_val) / 1000.0 if len(temp_val) > 3 else float(temp_val),
                        "C",
                        confidence=ConfidenceLevel.MEDIUM,
                        sensor=type_name,
                        node=node,
                    )
                )

        # Thermal service level
        thermal_text = self._shell("dumpsys thermalservice 2>/dev/null")
        # 尝试解析 thermal level
        level_match = re.search(r"status=(\d+)", thermal_text)
        if level_match:
            out.append(self._make_sample(now, MetricKey.THERMAL_LEVEL, float(level_match.group(1)), "level", confidence=ConfidenceLevel.MEDIUM))

        return out

    # ── Battery ───────────────────────────────────────────────────

    def _poll_battery(self, now: int) -> list[MetricSample]:
        out: list[MetricSample] = []

        battery_text = self._shell("dumpsys battery 2>/dev/null")
        # Current (mA)
        current_match = re.search(r"current now:\s*(-?\d+)", battery_text)
        if current_match:
            current_now = int(current_match.group(1))
            # 部分设备单位是 mA，部分是 μA
            if abs(current_now) > 10000:
                current_ma = current_now / 1000.0
            else:
                current_ma = float(current_now) / -1.0 if current_now < 0 else float(current_now)
            out.append(self._make_sample(now, MetricKey.BATTERY_DRAIN_MA, abs(current_ma), "mA", confidence=ConfidenceLevel.MEDIUM, source="dumpsys_battery"))

        # 或者通过 /sys/class/power_supply/battery/current_now
        current_sys = self._shell("cat /sys/class/power_supply/battery/current_now 2>/dev/null").strip()
        if current_sys and current_sys.lstrip("-").isdigit():
            current_ua = int(current_sys)
            current_ma = abs(current_ua) / 1000.0
            out.append(self._make_sample(now, MetricKey.BATTERY_DRAIN_MA, current_ma, "mA", confidence=ConfidenceLevel.HIGH, source="sysfs"))

        # 电压
        voltage_sys = self._shell("cat /sys/class/power_supply/battery/voltage_now 2>/dev/null").strip()
        if voltage_sys and voltage_sys.isdigit():
            voltage_v = int(voltage_sys) / 1_000_000.0
            out.append(self._make_sample(now, MetricKey.BATTERY_DRAIN_MA, voltage_v, "V", confidence=ConfidenceLevel.HIGH, source="sysfs_voltage"))

        return out

    # ── GPU ───────────────────────────────────────────────────────

    def _poll_gpu(self, now: int) -> list[MetricSample]:
        out: list[MetricSample] = []

        # Qualcomm (kgsl)
        gpu_util_text = self._shell(f"cat {self._gpu_node_path} 2>/dev/null") if self._gpu_node_path else ""
        if not gpu_util_text:
            # fallback: try common paths
            gpu_util_text = self._shell("cat /sys/class/kgsl/kgsl-3d0/gpubusy 2>/dev/null")

        gpu_match = re.search(r"(\d+)\s+(\d+)", gpu_util_text)
        if gpu_match and int(gpu_match.group(2)) > 0:
            util = (int(gpu_match.group(1)) / int(gpu_match.group(2))) * 100.0
            out.append(self._make_sample(now, MetricKey.GPU_UTIL_PERCENT, util, "%", confidence=ConfidenceLevel.MEDIUM))

        # Mali utilization
        mali_util = self._shell("cat /sys/class/misc/mali0/device/utilization 2>/dev/null")
        if mali_util:
            mali_match = re.search(r"(\d+)\s*/\s*(\d+)", mali_util)
            if mali_match:
                util = (int(mali_match.group(1)) / int(mali_match.group(2))) * 100.0
                out.append(self._make_sample(now, MetricKey.GPU_UTIL_PERCENT, util, "%", confidence=ConfidenceLevel.MEDIUM))

        # GPU frequency
        # Qualcomm
        gpu_freq = self._shell("cat /sys/class/kgsl/kgsl-3d0/gpuclk 2>/dev/null").strip()
        if gpu_freq and gpu_freq.isdigit():
            out.append(self._make_sample(now, MetricKey.GPU_FREQ_MHZ, int(gpu_freq) / 1_000_000.0, "MHz", confidence=ConfidenceLevel.MEDIUM))

        # Mali freq
        mali_freq = self._shell("cat /sys/class/misc/mali0/device/clock 2>/dev/null").strip()
        if not mali_freq:
            mali_freq = self._shell("cat /sys/class/devfreq/*/cur_freq 2>/dev/null | head -1").strip()
        if mali_freq and mali_freq.isdigit():
            out.append(self._make_sample(now, MetricKey.GPU_FREQ_MHZ, int(mali_freq) / 1_000_000.0, "MHz", confidence=ConfidenceLevel.MEDIUM))

        return out

    # ── Frame Stats (非侵入 FPS) ──────────────────────────────────

    def _poll_frame_stats(self, now: int) -> list[MetricSample]:
        out: list[MetricSample] = []
        if not self.app_id:
            return out

        # gfxinfo framestats
        gfx_text = self._shell(f"dumpsys gfxinfo {self.app_id} framestats 2>/dev/null")
        if not gfx_text:
            return out

        # 解析帧时间数据
        # framestats 格式: ---PROFILEDATA--- 后每行 13 个 int 字段（单位 ns）
        # 第1个字段是 INTENDED_VSYNC 到实际完成的时间（近似帧时间）
        in_profile = False
        frame_times_ns: list[float] = []
        for line in gfx_text.splitlines():
            if "PROFILEDATA" in line:
                in_profile = True
                continue
            if not in_profile:
                continue
            if line.startswith("---") or not line.strip():
                continue
            fields = line.split(",")
            if len(fields) < 13:
                continue
            try:
                # 帧时间 = 第1个字段（INTENDED_VSYNC ns）
                frame_ns = float(fields[0])
                if frame_ns > 0:
                    frame_times_ns.append(frame_ns)
            except (ValueError, IndexError):
                continue

        if frame_times_ns:
            frame_times_ms = [t / 1_000_000.0 for t in frame_times_ns[-60:]]
            avg_ms = sum(frame_times_ms) / len(frame_times_ms)
            sorted_ms = sorted(frame_times_ms)
            n = len(sorted_ms)

            fps = 1000.0 / avg_ms if avg_ms > 0 else 0.0
            out.append(self._make_sample(now, MetricKey.FPS, fps, "fps", confidence=ConfidenceLevel.MEDIUM, source_type="gfxinfo"))
            out.append(self._make_sample(now, MetricKey.FRAME_TIME_MS, avg_ms, "ms", confidence=ConfidenceLevel.MEDIUM, source_type="gfxinfo"))

            if n >= 2:
                out.append(self._make_sample(now, MetricKey.FRAME_TIME_P95_MS, sorted_ms[int(n * 0.95)], "ms", confidence=ConfidenceLevel.MEDIUM, source_type="gfxinfo"))

            # 存储历史用于计算 Jank
            self._frame_time_history = frame_times_ms

        # Total frames rendered
        total_frames = self._shell(f"dumpsys gfxinfo {self.app_id} 2>/dev/null | grep 'Total frames rendered'")
        frames_match = re.search(r"Total frames rendered:\s*(\d+)", total_frames)
        if frames_match:
            out.append(
                self._make_sample(
                    now,
                    MetricKey.FPS,
                    float(frames_match.group(1)),
                    "frames_total",
                    confidence=ConfidenceLevel.HIGH,
                    source_type="total_frames_rendered",
                )
            )

        return out

    # ── Network ───────────────────────────────────────────────────

    def _poll_network(self, now: int) -> list[MetricSample]:
        out: list[MetricSample] = []
        if not self.app_id:
            return out

        pid = self.bridge.get_pid(self.serial, self.app_id)
        if not pid:
            return out

        # 读取 /proc/[pid]/net/dev 获取网络流量
        net_dev = self._shell(f"cat /proc/{pid}/net/dev 2>/dev/null")
        rx_bytes = 0
        tx_bytes = 0
        for line in net_dev.splitlines():
            if ":" not in line:
                continue
            _, data = line.split(":", 1)
            fields = data.split()
            if len(fields) >= 9:
                try:
                    rx_bytes += int(fields[0])
                    tx_bytes += int(fields[8])
                except (ValueError, IndexError):
                    continue

        if rx_bytes > 0 or tx_bytes > 0:
            out.append(self._make_sample(now, MetricKey.NETWORK_THROUGHPUT_KBPS, (rx_bytes + tx_bytes) / 1024.0, "KB", confidence=ConfidenceLevel.LOW, direction="total"))

        # Ping RTT (简单检测)
        ping_result = self._shell("ping -c 1 -W 1 8.8.8.8 2>/dev/null")
        rtt_match = re.search(r"time=([\d.]+)\s*ms", ping_result)
        if rtt_match:
            out.append(self._make_sample(now, MetricKey.NETWORK_RTT_MS, float(rtt_match.group(1)), "ms", confidence=ConfidenceLevel.LOW))

        return out