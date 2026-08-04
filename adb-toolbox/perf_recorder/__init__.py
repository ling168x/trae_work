"""Cross-platform performance recorder core package.

Architecture:
    adb_bridge -> collector (Android/iOS/Unity) -> stream_bus -> storage + dashboard + alert
    device_manager -> session_manager -> report_service
"""

from .adb_bridge import AdbBridge, AdbDevice, AndroidProcess
from .alert_manager import AlertEvent, AlertManager, AlertOperator, AlertRule
from .android_collector import AndroidCollector
from .collector_base import Collector
from .dashboard import ConsoleDashboard
from .device_manager import (
    DeviceManager,
    DeviceSession,
    ProfileTemplate,
    ProfileType,
    UNITY_PROFILE,
    GENERIC_PROFILE,
)
from .host import PerfRecorderHost, SessionConfig
from .ios_bridge import list_ios_devices, validate_enterprise_channel
from .ios_collector import IOSCollector
from .models import (
    ConfidenceLevel,
    MetricKey,
    MetricSample,
    MetricSource,
    SamplingPolicy,
    P0_SAMPLING_POLICIES,
    infer_fps_confidence,
)
from .report import ReportService
from .session_manager import SessionManager, SessionMeta
from .storage import SQLiteMetricStorage
from .stream_bus import MetricStreamBus, RingBuffer, StreamBusConfig
from .unity_collector import UnityProbeCollector

__all__ = [
    # Models
    "MetricSample",
    "MetricKey",
    "MetricSource",
    "ConfidenceLevel",
    "SamplingPolicy",
    "P0_SAMPLING_POLICIES",
    "infer_fps_confidence",
    # ADB Bridge
    "AdbBridge",
    "AdbDevice",
    "AndroidProcess",
    # Collectors
    "Collector",
    "AndroidCollector",
    "IOSCollector",
    "UnityProbeCollector",
    # Stream Bus
    "MetricStreamBus",
    "RingBuffer",
    "StreamBusConfig",
    # Device Manager
    "DeviceManager",
    "DeviceSession",
    "ProfileTemplate",
    "ProfileType",
    "UNITY_PROFILE",
    "GENERIC_PROFILE",
    # Session Manager
    "SessionManager",
    "SessionMeta",
    # Alert Manager
    "AlertManager",
    "AlertEvent",
    "AlertRule",
    "AlertOperator",
    # Dashboard
    "ConsoleDashboard",
    # Host
    "PerfRecorderHost",
    "SessionConfig",
    # Storage
    "SQLiteMetricStorage",
    # Report
    "ReportService",
    # iOS Bridge
    "list_ios_devices",
    "validate_enterprise_channel",
]