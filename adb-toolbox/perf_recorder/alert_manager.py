"""Alert manager: threshold-based alerting with anomaly interval detection."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .models import MetricKey, MetricSample


class AlertOperator(str, Enum):
    LT = "lt"  # less than
    GT = "gt"  # greater than
    LTE = "lte"
    GTE = "gte"


@dataclass
class AlertRule:
    """告警规则定义。"""

    metric_key: MetricKey
    threshold: float
    operator: AlertOperator = AlertOperator.LT
    duration_ms: int = 3000  # 持续超过阈值多久才触发告警
    cooldown_ms: int = 5000  # 告警冷却时间
    label: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            self.label = f"{self.metric_key.value} {self.operator.value} {self.threshold}"


@dataclass
class AlertEvent:
    """告警事件。"""

    rule: AlertRule
    started_at_ms: int
    ended_at_ms: int = 0
    min_value: float = float("inf")
    max_value: float = float("-inf")
    device_id: str = ""
    app_id: str = ""
    resolved: bool = False

    @property
    def duration_ms(self) -> int:
        end = self.ended_at_ms or int(time.time() * 1000)
        return end - self.started_at_ms


class AlertManager:
    """
    告警管理：阈值检测、异常区间标记、告警回调。
    - 支持 FPS < 45 持续 3s 触发告警等规则
    - 异常区间自动标记起止时间
    """

    def __init__(self) -> None:
        self._rules: list[AlertRule] = []
        self._active_alerts: dict[tuple[str, str, MetricKey], AlertEvent] = {}
        self._resolved_alerts: list[AlertEvent] = []
        self._callbacks: list[Callable[[AlertEvent], None]] = []
        self._anomaly_intervals: list[tuple[int, int, str]] = []  # (start_ms, end_ms, label)

    def add_rule(self, rule: AlertRule) -> None:
        self._rules.append(rule)

    def add_rules_from_dict(self, thresholds: dict[MetricKey, tuple[float, str]]) -> None:
        """从 Profile 模板的阈值字典批量添加规则。"""
        for key, (threshold, op_str) in thresholds.items():
            self.add_rule(
                AlertRule(
                    metric_key=key,
                    threshold=threshold,
                    operator=AlertOperator(op_str),
                    duration_ms=3000,
                )
            )

    def remove_rule(self, metric_key: MetricKey) -> None:
        self._rules = [r for r in self._rules if r.metric_key != metric_key]

    def on_alert(self, callback: Callable[[AlertEvent], None]) -> None:
        """注册告警回调。"""
        self._callbacks.append(callback)

    def evaluate(self, samples: list[MetricSample]) -> list[AlertEvent]:
        """评估一批采样数据，返回新触发的告警事件。"""
        triggered: list[AlertEvent] = []
        now = int(time.time() * 1000)

        for sample in samples:
            for rule in self._rules:
                if rule.metric_key != sample.metric_key:
                    continue

                key = (sample.device_id, sample.app_id, rule.metric_key)
                is_breached = self._check_breach(sample.value, rule)

                if is_breached:
                    if key not in self._active_alerts:
                        # 开始新的告警窗口
                        self._active_alerts[key] = AlertEvent(
                            rule=rule,
                            started_at_ms=sample.timestamp_ms,
                            device_id=sample.device_id,
                            app_id=sample.app_id,
                        )
                    # 更新最值
                    alert = self._active_alerts[key]
                    alert.min_value = min(alert.min_value, sample.value)
                    alert.max_value = max(alert.max_value, sample.value)
                else:
                    if key in self._active_alerts:
                        alert = self._active_alerts.pop(key)
                        alert.ended_at_ms = sample.timestamp_ms
                        # 检查持续时间是否达到阈值
                        if alert.duration_ms >= rule.duration_ms:
                            alert.resolved = True
                            self._resolved_alerts.append(alert)
                            triggered.append(alert)
                            # 标记异常区间
                            self._anomaly_intervals.append(
                                (alert.started_at_ms, alert.ended_at_ms, alert.rule.label)
                            )
                            # 通知回调
                            for cb in self._callbacks:
                                try:
                                    cb(alert)
                                except Exception:
                                    pass

        # 检查超时未解决的告警（强制结束）
        for key, alert in list(self._active_alerts.items()):
            if now - alert.started_at_ms > alert.rule.duration_ms + alert.rule.cooldown_ms:
                alert.ended_at_ms = now
                alert.resolved = True
                self._resolved_alerts.append(alert)
                triggered.append(alert)
                self._anomaly_intervals.append(
                    (alert.started_at_ms, alert.ended_at_ms, alert.rule.label)
                )
                del self._active_alerts[key]

        return triggered

    def _check_breach(self, value: float, rule: AlertRule) -> bool:
        if rule.operator == AlertOperator.LT:
            return value < rule.threshold
        elif rule.operator == AlertOperator.GT:
            return value > rule.threshold
        elif rule.operator == AlertOperator.LTE:
            return value <= rule.threshold
        elif rule.operator == AlertOperator.GTE:
            return value >= rule.threshold
        return False

    # ── Anomaly Intervals ─────────────────────────────────────────

    def get_anomaly_intervals(self) -> list[tuple[int, int, str]]:
        """获取异常区间列表：(start_ms, end_ms, label)。"""
        return list(self._anomaly_intervals)

    def get_active_alerts(self) -> list[AlertEvent]:
        """获取当前活跃的告警（未解决）。"""
        return list(self._active_alerts.values())

    def get_resolved_alerts(self) -> list[AlertEvent]:
        """获取已解决的告警历史。"""
        return list(self._resolved_alerts)

    def clear_alerts(self) -> None:
        """清除所有告警记录。"""
        self._active_alerts.clear()
        self._resolved_alerts.clear()
        self._anomaly_intervals.clear()

    def stats(self) -> dict[str, object]:
        return {
            "active_alerts": len(self._active_alerts),
            "resolved_alerts": len(self._resolved_alerts),
            "anomaly_intervals": len(self._anomaly_intervals),
            "rules": [r.label for r in self._rules],
        }