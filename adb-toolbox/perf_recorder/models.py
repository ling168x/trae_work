from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MetricSource(str, Enum):
    ANDROID_SYSTEM = "android.system"
    ANDROID_UNITY_SDK = "android.unity_sdk"
    IOS_PUBLIC = "ios.public"
    IOS_ENTERPRISE = "ios.enterprise"
    IOS_UNITY_SDK = "ios.unity_sdk"
    AGGREGATED = "aggregated"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class MetricKey(str, Enum):
    FPS = "fps"
    FRAME_TIME_MS = "frame_time_ms"
    FRAME_TIME_P95_MS = "frame_time_p95_ms"
    CPU_TOTAL_PERCENT = "cpu_total_percent"
    CPU_APP_PERCENT = "cpu_app_percent"
    GPU_UTIL_PERCENT = "gpu_util_percent"
    GPU_FREQ_MHZ = "gpu_freq_mhz"
    MEMORY_PSS_MB = "memory_pss_mb"
    MEMORY_RESIDENT_MB = "memory_resident_mb"
    TEMPERATURE_C = "temperature_c"
    THERMAL_LEVEL = "thermal_level"
    BATTERY_DRAIN_MA = "battery_drain_ma"
    UNITY_MAIN_THREAD_MS = "unity_main_thread_ms"
    UNITY_RENDER_THREAD_MS = "unity_render_thread_ms"
    UNITY_GC_ALLOC_KB = "unity_gc_alloc_kb"
    UNITY_GC_COLLECT_COUNT = "unity_gc_collect_count"
    NETWORK_RTT_MS = "network_rtt_ms"
    NETWORK_THROUGHPUT_KBPS = "network_throughput_kbps"


@dataclass(slots=True)
class MetricSample:
    timestamp_ms: int
    device_id: str
    app_id: str
    metric_key: MetricKey
    value: float
    unit: str
    source: MetricSource
    confidence: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    sequence: int = 0
    tags: dict[str, str] = field(default_factory=dict)

    def as_record(self) -> dict[str, Any]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "device_id": self.device_id,
            "app_id": self.app_id,
            "metric_key": self.metric_key.value,
            "value": self.value,
            "unit": self.unit,
            "source": self.source.value,
            "confidence": self.confidence.value,
            "sequence": self.sequence,
            "tags": dict(self.tags),
        }


@dataclass(frozen=True, slots=True)
class SamplingPolicy:
    metric_key: MetricKey
    interval_ms: int
    priority: str


P0_SAMPLING_POLICIES: tuple[SamplingPolicy, ...] = (
    SamplingPolicy(MetricKey.FPS, interval_ms=100, priority="P0"),
    SamplingPolicy(MetricKey.FRAME_TIME_MS, interval_ms=100, priority="P0"),
    SamplingPolicy(MetricKey.CPU_TOTAL_PERCENT, interval_ms=1000, priority="P0"),
    SamplingPolicy(MetricKey.CPU_APP_PERCENT, interval_ms=1000, priority="P0"),
    SamplingPolicy(MetricKey.MEMORY_PSS_MB, interval_ms=1000, priority="P0"),
    SamplingPolicy(MetricKey.TEMPERATURE_C, interval_ms=1000, priority="P0"),
)


def infer_fps_confidence(system_fps: float | None, sdk_fps: float | None) -> ConfidenceLevel:
    if system_fps is None and sdk_fps is None:
        return ConfidenceLevel.UNKNOWN
    if system_fps is None or sdk_fps is None:
        return ConfidenceLevel.MEDIUM
    if system_fps <= 0 or sdk_fps <= 0:
        return ConfidenceLevel.LOW

    delta_ratio = abs(system_fps - sdk_fps) / max(system_fps, sdk_fps)
    if delta_ratio <= 0.05:
        return ConfidenceLevel.HIGH
    if delta_ratio <= 0.12:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW
