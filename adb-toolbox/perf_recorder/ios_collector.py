from __future__ import annotations

import re
import subprocess
import time

from .collector_base import Collector
from .models import ConfidenceLevel, MetricKey, MetricSample, MetricSource


class IOSCollector(Collector):
    """
    Enterprise distribution path: best-effort pull via ideviceinfo/instruments-like tools.
    Falls back to thermal level only when granular metrics are unavailable.
    """

    def __init__(self, udid: str, app_id: str, enterprise_mode: bool = True) -> None:
        self.udid = udid
        self.app_id = app_id
        self.enterprise_mode = enterprise_mode
        self.seq = 0

    def _next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def _run_ideviceinfo(self) -> str:
        proc = subprocess.run(
            ["ideviceinfo", "-u", self.udid],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout if proc.returncode == 0 else ""

    def poll(self) -> list[MetricSample]:
        now = int(time.time() * 1000)
        info = self._run_ideviceinfo()
        out: list[MetricSample] = []

        thermal_state = re.search(r"ThermalState:\s*(\w+)", info)
        if thermal_state:
            out.append(
                MetricSample(
                    timestamp_ms=now,
                    device_id=self.udid,
                    app_id=self.app_id,
                    metric_key=MetricKey.THERMAL_LEVEL,
                    value=float({"Nominal": 0, "Fair": 1, "Serious": 2, "Critical": 3}.get(thermal_state.group(1), -1)),
                    unit="level",
                    source=MetricSource.IOS_PUBLIC,
                    confidence=ConfidenceLevel.MEDIUM,
                    sequence=self._next_seq(),
                )
            )

        if self.enterprise_mode:
            # Placeholder for enterprise-injected metrics channel.
            # Collector still emits source and confidence so the pipeline can classify capability level.
            out.append(
                MetricSample(
                    timestamp_ms=now,
                    device_id=self.udid,
                    app_id=self.app_id,
                    metric_key=MetricKey.CPU_APP_PERCENT,
                    value=-1.0,
                    unit="%",
                    source=MetricSource.IOS_ENTERPRISE,
                    confidence=ConfidenceLevel.UNKNOWN,
                    sequence=self._next_seq(),
                    tags={"capability": "enterprise_placeholder"},
                )
            )
        return out
