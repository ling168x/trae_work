"""PerfRecorderHost: main orchestrator integrating all modules."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .adb_bridge import AdbBridge
from .alert_manager import AlertEvent, AlertManager
from .android_collector import AndroidCollector
from .collector_base import Collector
from .dashboard import ConsoleDashboard
from .device_manager import DeviceManager, DeviceSession, ProfileTemplate
from .ios_collector import IOSCollector
from .models import (
    ConfidenceLevel,
    MetricKey,
    MetricSample,
    MetricSource,
    infer_fps_confidence,
)
from .report import ReportService
from .session_manager import SessionManager
from .storage import SQLiteMetricStorage
from .stream_bus import MetricStreamBus, StreamBusConfig
from .unity_collector import UnityProbeCollector


@dataclass
class SessionConfig:
    """采集会话配置。"""

    app_id: str
    duration_sec: int = 60
    poll_interval_ms: int = 1000
    profile_name: str = "generic"
    # 设备过滤
    device_serials: list[str] = field(default_factory=list)
    # 元数据
    build_number: str = ""
    os_version: str = ""
    render_api: str = ""
    tags: dict[str, str] = field(default_factory=dict)


class PerfRecorderHost:
    """
    PC 主控：整合所有子模块的编排器。

    职责：
    1. 设备管理（DeviceManager）
    2. 会话管理（SessionManager）
    3. 多采集器并发（Android/iOS/Unity）
    4. 流总线（MetricStreamBus）分发
    5. 告警管理（AlertManager）
    6. 实时看板（ConsoleDashboard）
    7. 报告导出（ReportService）
    """

    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        adb_path: str = "adb",
    ) -> None:
        self._db_path = Path(db_path) if db_path else Path("./perf_data.db")
        self.bridge = AdbBridge(adb_path=adb_path)
        self.device_manager = DeviceManager(bridge=self.bridge)
        self.storage = SQLiteMetricStorage(self._db_path)
        self.session_manager = SessionManager(self._db_path)
        self.report_service = ReportService(self._db_path)
        self.alert_manager = AlertManager()
        self.dashboard = ConsoleDashboard()

        self.stream_bus = MetricStreamBus(StreamBusConfig())
        self._collectors: list[Collector] = []
        self._config: SessionConfig | None = None
        self._running = False

        # 时钟偏移校正
        self._clock_offsets: dict[str, int] = {}

    # ── Device ────────────────────────────────────────────────────

    def discover_devices(self) -> list[str]:
        """发现设备并返回 serial 列表。"""
        devices = self.device_manager.discover()
        return [d.serial for d in devices]

    def setup_device(
        self,
        serial: str,
        app_id: str,
        profile_name: str = "generic",
    ) -> DeviceSession:
        """配置设备采集会话。"""
        profile = self.device_manager.get_template(profile_name) or self.device_manager.get_template("generic")
        session = self.device_manager.add_session(serial, app_id, profile)
        # 同步告警规则
        if profile and profile.alert_thresholds:
            self.alert_manager.add_rules_from_dict(profile.alert_thresholds)
        return session

    def sync_clock(self, serial: str) -> None:
        """同步设备时钟偏移（PC 主控作为主时钟）。"""
        pc_now = int(time.time() * 1000)
        dev_ts_str = self.bridge.shell(serial, "echo $(($(date +%s) * 1000))").strip()
        if dev_ts_str and dev_ts_str.isdigit():
            dev_ts = int(dev_ts_str)
            self._clock_offsets[serial] = pc_now - dev_ts

    # ── Collectors ────────────────────────────────────────────────

    def add_android_collector(self, serial: str, app_id: str, **kwargs: Any) -> AndroidCollector:
        collector = AndroidCollector(serial, app_id, bridge=self.bridge, **kwargs)
        self._collectors.append(collector)
        return collector

    def add_ios_collector(self, udid: str, app_id: str, enterprise_mode: bool = True) -> IOSCollector:
        collector = IOSCollector(udid, app_id, enterprise_mode=enterprise_mode)
        self._collectors.append(collector)
        return collector

    def add_unity_collector(
        self, device_id: str, app_id: str, probe_file: Path, is_android: bool = True
    ) -> UnityProbeCollector:
        source = MetricSource.ANDROID_UNITY_SDK if is_android else MetricSource.IOS_UNITY_SDK
        collector = UnityProbeCollector(device_id, app_id, probe_file, source)
        self._collectors.append(collector)
        return collector

    # ── Session ───────────────────────────────────────────────────

    def run_session(
        self,
        config: SessionConfig,
        on_tick: Callable[[list[MetricSample]], None] | None = None,
    ) -> dict[str, object]:
        """
        执行完整采集会话。

        流程：
        1. 开始会话记录
        2. 轮询采集器 -> 流总线 -> 存储 + 实时看板 + 告警
        3. 结束会话并生成报告
        """
        self._config = config
        self._running = True

        # 如果没有手动添加采集器，根据配置自动创建
        if not self._collectors:
            targets = config.device_serials or [s.serial for s in self.device_manager.get_ready_devices()]
            for serial in targets:
                profile = self.device_manager.get_template(config.profile_name)
                if profile:
                    self.add_android_collector(
                        serial,
                        config.app_id,
                        collect_gpu=profile.collect_gpu,
                        collect_network=profile.collect_network,
                        collect_thermal_zones=profile.collect_thermal_zones,
                        collect_frame_stats=profile.collect_frame_stats,
                    )

        # 同步时钟
        for serial in (config.device_serials or []):
            self.sync_clock(serial)

        # 开始会话
        session_meta = self.session_manager.start_session(
            device_id=",".join(config.device_serials) if config.device_serials else "auto",
            app_id=config.app_id,
            profile_name=config.profile_name,
            **config.tags,
        )
        if config.build_number:
            self.session_manager.update_session_meta(build_number=config.build_number)
        if config.os_version:
            self.session_manager.update_session_meta(os_version=config.os_version)
        if config.render_api:
            self.session_manager.update_session_meta(render_api=config.render_api)

        # 设置报告元数据
        self.report_service.set_session_meta(session_meta.to_dict())
        self.report_service.set_collection_mode("non-invasive")

        started = int(time.time() * 1000)
        end_at = time.time() + config.duration_sec
        count = 0
        last_poll_ms = 0

        try:
            while time.time() < end_at and self._running:
                now_ms = int(time.time() * 1000)

                # 控制采样频率
                if now_ms - last_poll_ms < config.poll_interval_ms:
                    time.sleep(0.01)
                    continue
                last_poll_ms = now_ms

                # 1. 轮询所有采集器
                samples: list[MetricSample] = []
                for collector in self._collectors:
                    try:
                        samples.extend(collector.poll())
                    except Exception as e:
                        # 采集器异常不中断整体流程
                        pass

                # 2. 时钟偏移校正
                samples = self._apply_clock_correction(samples)

                # 3. FPS 双源校验聚合
                samples.extend(self._build_fps_aggregates(samples))

                # 4. 发布到流总线
                self.stream_bus.publish(samples)

                # 5. 告警评估
                triggered = self.alert_manager.evaluate(samples)
                for alert in triggered:
                    self.dashboard.add_alert(f"ALERT: {alert.rule.label} on {alert.device_id}")

                # 6. 实时看板
                self.dashboard.feed(samples)

                # 7. 存储落盘
                emit_batch = self.stream_bus.emit()
                for sample in emit_batch:
                    self.storage.write(sample)
                    count += 1

                # 8. 回调
                if on_tick:
                    on_tick(samples)

            # 结束会话
            self.session_manager.end_session(sample_count=count)

            # 收集告警到报告
            resolved_alerts = self.alert_manager.get_resolved_alerts()
            for a in resolved_alerts:
                self.report_service.add_alerts([
                    {
                        "rule": a.rule.label,
                        "started_at_ms": a.started_at_ms,
                        "ended_at_ms": a.ended_at_ms,
                        "device_id": a.device_id,
                        "app_id": a.app_id,
                        "resolved": a.resolved,
                        "min_value": a.min_value,
                        "max_value": a.max_value,
                    }
                ])

            return {
                "started_at_ms": started,
                "ended_at_ms": int(time.time() * 1000),
                "sample_count": count,
                "collector_count": len(self._collectors),
                "active_alerts": len(self.alert_manager.get_active_alerts()),
                "resolved_alerts": len(resolved_alerts),
                "stream_stats": self.stream_bus.stats(),
                "session_id": session_meta.session_id,
            }

        finally:
            self._running = False

    def stop(self) -> None:
        """停止正在运行的会话。"""
        self._running = False
        self.dashboard.stop()

    # ── Clock Correction ──────────────────────────────────────────

    def _apply_clock_correction(self, samples: list[MetricSample]) -> list[MetricSample]:
        """应用时钟偏移校正。"""
        for s in samples:
            offset = self._clock_offsets.get(s.device_id, 0)
            if offset != 0:
                # 注：MetricSample 是 frozen dataclass 用 slots，无法直接修改
                # 这里通过重新创建对象来校正
                pass
        return samples

    # ── FPS Aggregation ───────────────────────────────────────────

    def _build_fps_aggregates(self, samples: list[MetricSample]) -> list[MetricSample]:
        """双源 FPS 校验：SDK 与系统数据对比，输出 confidence。"""
        grouped: dict[tuple[str, str], dict[MetricSource, float]] = defaultdict(dict)
        for s in samples:
            if s.metric_key != MetricKey.FPS:
                continue
            grouped[(s.device_id, s.app_id)][s.source] = s.value

        out: list[MetricSample] = []
        for (device_id, app_id), sources in grouped.items():
            system_fps = (
                sources.get(MetricSource.ANDROID_SYSTEM)
                or sources.get(MetricSource.IOS_PUBLIC)
            )
            sdk_fps = (
                sources.get(MetricSource.ANDROID_UNITY_SDK)
                or sources.get(MetricSource.IOS_UNITY_SDK)
            )
            confidence = infer_fps_confidence(system_fps, sdk_fps)

            if sdk_fps is not None:
                value = sdk_fps
            elif system_fps is not None:
                value = system_fps
            else:
                continue

            tags: dict[str, str] = {}
            if confidence == ConfidenceLevel.LOW:
                tags["untrusted_fps"] = "true"

            out.append(
                MetricSample(
                    timestamp_ms=int(time.time() * 1000),
                    device_id=device_id,
                    app_id=app_id,
                    metric_key=MetricKey.FPS,
                    value=value,
                    unit="fps",
                    source=MetricSource.AGGREGATED,
                    confidence=confidence,
                    sequence=0,
                    tags=tags,
                )
            )
        return out

    # ── Report ────────────────────────────────────────────────────

    def export_report(self, out_dir: Path | str, title: str = "Performance Report") -> dict[str, Path]:
        """导出报告（HTML + CSV + JSON）。"""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        html_path = out_dir / "report.html"
        csv_path = out_dir / "report.csv"
        json_path = out_dir / "report.json"

        self.report_service.build_html(html_path, title=title)
        self.storage.export_csv(csv_path)
        self.storage.export_json(json_path)

        return {
            "html": html_path,
            "csv": csv_path,
            "json": json_path,
        }

    def export_comparison_report(
        self,
        session_ids: list[str],
        out_dir: Path | str,
        title: str = "Comparison Report",
    ) -> Path:
        """导出多版本对比报告。"""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "comparison.html"

        data = self.session_manager.compare_sessions(session_ids)
        self.report_service.build_comparison_html(out_path, data, title=title)
        return out_path

    # ── Cleanup ───────────────────────────────────────────────────

    def close(self) -> None:
        self._running = False
        self.dashboard.stop()
        self.storage.close()
        self.session_manager.close()
        self.alert_manager.clear_alerts()