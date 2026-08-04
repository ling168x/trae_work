"""Device manager: multi-device management, profile templates, sampling switches."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .adb_bridge import AdbBridge, AdbDevice
from .models import MetricKey


class ProfileType(str, Enum):
    UNITY = "unity"
    GENERIC = "generic"
    CUSTOM = "custom"


@dataclass
class ProfileTemplate:
    """采样 Profile 模板，定义采集哪些指标及频率。"""

    name: str
    profile_type: ProfileType = ProfileType.GENERIC
    poll_interval_ms: int = 1000
    enabled_metrics: set[MetricKey] = field(default_factory=lambda: {
        MetricKey.FPS,
        MetricKey.FRAME_TIME_MS,
        MetricKey.CPU_TOTAL_PERCENT,
        MetricKey.CPU_APP_PERCENT,
        MetricKey.MEMORY_PSS_MB,
        MetricKey.MEMORY_RESIDENT_MB,
        MetricKey.TEMPERATURE_C,
        MetricKey.THERMAL_LEVEL,
        MetricKey.BATTERY_DRAIN_MA,
    })
    collect_gpu: bool = True
    collect_network: bool = False
    collect_thermal_zones: bool = True
    collect_frame_stats: bool = True
    # 告警阈值
    alert_thresholds: dict[MetricKey, tuple[float, str]] = field(default_factory=dict)
    # metadata
    tags: dict[str, str] = field(default_factory=dict)


# 预置 Profile 模板
UNITY_PROFILE = ProfileTemplate(
    name="Unity",
    profile_type=ProfileType.UNITY,
    poll_interval_ms=100,
    enabled_metrics={
        MetricKey.FPS,
        MetricKey.FRAME_TIME_MS,
        MetricKey.FRAME_TIME_P95_MS,
        MetricKey.CPU_TOTAL_PERCENT,
        MetricKey.CPU_APP_PERCENT,
        MetricKey.MEMORY_PSS_MB,
        MetricKey.MEMORY_RESIDENT_MB,
        MetricKey.TEMPERATURE_C,
        MetricKey.THERMAL_LEVEL,
        MetricKey.BATTERY_DRAIN_MA,
        MetricKey.GPU_UTIL_PERCENT,
        MetricKey.GPU_FREQ_MHZ,
        MetricKey.UNITY_MAIN_THREAD_MS,
        MetricKey.UNITY_RENDER_THREAD_MS,
        MetricKey.UNITY_GC_ALLOC_KB,
        MetricKey.UNITY_GC_COLLECT_COUNT,
    },
    collect_gpu=True,
    collect_network=False,
    collect_thermal_zones=True,
    collect_frame_stats=True,
    alert_thresholds={
        MetricKey.FPS: (45.0, "lt"),
        MetricKey.FRAME_TIME_MS: (33.3, "gt"),
        MetricKey.TEMPERATURE_C: (45.0, "gt"),
    },
    tags={"kind": "unity"},
)

GENERIC_PROFILE = ProfileTemplate(
    name="Generic",
    profile_type=ProfileType.GENERIC,
    poll_interval_ms=1000,
    enabled_metrics={
        MetricKey.FPS,
        MetricKey.FRAME_TIME_MS,
        MetricKey.CPU_TOTAL_PERCENT,
        MetricKey.CPU_APP_PERCENT,
        MetricKey.MEMORY_PSS_MB,
        MetricKey.MEMORY_RESIDENT_MB,
        MetricKey.TEMPERATURE_C,
        MetricKey.THERMAL_LEVEL,
        MetricKey.BATTERY_DRAIN_MA,
    },
    collect_gpu=True,
    collect_network=False,
    collect_thermal_zones=True,
    collect_frame_stats=True,
    alert_thresholds={
        MetricKey.FPS: (30.0, "lt"),
        MetricKey.TEMPERATURE_C: (45.0, "gt"),
    },
    tags={"kind": "generic"},
)


@dataclass
class DeviceSession:
    """单个设备的采集会话状态。"""

    serial: str
    device_info: AdbDevice
    profile: ProfileTemplate
    app_id: str
    is_active: bool = False
    started_at_ms: int = 0
    sample_count: int = 0
    last_error: str = ""


class DeviceManager:
    """多设备管理：并发设备接入、Profile 模板分配、采样开关。"""

    def __init__(self, bridge: AdbBridge | None = None) -> None:
        self.bridge = bridge or AdbBridge()
        self._sessions: dict[str, DeviceSession] = {}
        self._templates: dict[str, ProfileTemplate] = {
            ProfileType.UNITY.value: UNITY_PROFILE,
            ProfileType.GENERIC.value: GENERIC_PROFILE,
        }

    # ── Device Discovery ──────────────────────────────────────────

    def discover(self) -> list[AdbDevice]:
        """发现当前连接的设备。"""
        return self.bridge.list_devices()

    def get_ready_devices(self) -> list[AdbDevice]:
        """获取所有就绪的设备。"""
        return [d for d in self.discover() if d.is_ready]

    def refresh_device_info(self, serial: str) -> AdbDevice:
        """刷新设备详细信息。"""
        return self.bridge.get_device_info(serial)

    # ── Session Management ────────────────────────────────────────

    def add_session(self, serial: str, app_id: str, profile: ProfileTemplate | None = None) -> DeviceSession:
        """为设备创建采集会话。"""
        if profile is None:
            profile = GENERIC_PROFILE
        dev_info = self.bridge.get_device_info(serial)
        session = DeviceSession(
            serial=serial,
            device_info=dev_info,
            profile=profile,
            app_id=app_id,
        )
        self._sessions[serial] = session
        return session

    def remove_session(self, serial: str) -> None:
        """移除设备会话。"""
        self._sessions.pop(serial, None)

    def get_session(self, serial: str) -> DeviceSession | None:
        """获取设备会话。"""
        return self._sessions.get(serial)

    def list_sessions(self) -> list[DeviceSession]:
        """列出所有活跃会话。"""
        return list(self._sessions.values())

    def activate_session(self, serial: str) -> bool:
        """激活设备会话。"""
        session = self._sessions.get(serial)
        if session:
            session.is_active = True
            return True
        return False

    def deactivate_session(self, serial: str) -> bool:
        """停用设备会话。"""
        session = self._sessions.get(serial)
        if session:
            session.is_active = False
            return True
        return False

    # ── Profile Templates ─────────────────────────────────────────

    def register_template(self, name: str, template: ProfileTemplate) -> None:
        """注册自定义 Profile 模板。"""
        self._templates[name] = template

    def get_template(self, name: str) -> ProfileTemplate | None:
        """获取 Profile 模板。"""
        return self._templates.get(name)

    def list_templates(self) -> list[str]:
        """列出所有可用模板名称。"""
        return list(self._templates.keys())

    def create_custom_profile(
        self,
        name: str,
        poll_interval_ms: int = 1000,
        enabled_metrics: set[MetricKey] | None = None,
        **kwargs: Any,
    ) -> ProfileTemplate:
        """创建自定义 Profile。"""
        template = ProfileTemplate(
            name=name,
            profile_type=ProfileType.CUSTOM,
            poll_interval_ms=poll_interval_ms,
            enabled_metrics=enabled_metrics or set(),
            **kwargs,
        )
        self._templates[name] = template
        return template

    # ── Stats ─────────────────────────────────────────────────────

    def active_device_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.is_active)

    def total_device_count(self) -> int:
        return len(self._sessions)

    def summary(self) -> dict[str, object]:
        return {
            "active_devices": self.active_device_count(),
            "total_devices": self.total_device_count(),
            "sessions": [
                {
                    "serial": s.serial,
                    "model": s.device_info.model,
                    "app_id": s.app_id,
                    "profile": s.profile.name,
                    "is_active": s.is_active,
                    "sample_count": s.sample_count,
                }
                for s in self._sessions.values()
            ],
        }