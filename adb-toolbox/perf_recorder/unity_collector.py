from __future__ import annotations

import json
import time
from pathlib import Path

from .collector_base import Collector
from .models import ConfidenceLevel, MetricKey, MetricSample, MetricSource


class UnityProbeCollector(Collector):
    """
    Reads newline-delimited JSON events exported by Unity probe SDK.
    """

    def __init__(self, device_id: str, app_id: str, probe_file: Path, source: MetricSource) -> None:
        self.device_id = device_id
        self.app_id = app_id
        self.probe_file = probe_file
        self.source = source
        self.offset = 0
        self.seq = 0

    def _next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def poll(self) -> list[MetricSample]:
        if not self.probe_file.exists():
            return []
        data = self.probe_file.read_text(encoding="utf-8")
        if self.offset >= len(data):
            return []
        chunk = data[self.offset :]
        self.offset = len(data)

        out: list[MetricSample] = []
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            now = int(obj.get("timestamp_ms", int(time.time() * 1000)))
            fps = float(obj.get("fps", 0.0))
            frame_ms = float(obj.get("frame_time_ms", 0.0))
            if fps > 0:
                out.append(
                    MetricSample(
                        timestamp_ms=now,
                        device_id=self.device_id,
                        app_id=self.app_id,
                        metric_key=MetricKey.FPS,
                        value=fps,
                        unit="fps",
                        source=self.source,
                        confidence=ConfidenceLevel.HIGH,
                        sequence=self._next_seq(),
                        tags={"kind": "unity_probe"},
                    )
                )
            if frame_ms > 0:
                out.append(
                    MetricSample(
                        timestamp_ms=now,
                        device_id=self.device_id,
                        app_id=self.app_id,
                        metric_key=MetricKey.FRAME_TIME_MS,
                        value=frame_ms,
                        unit="ms",
                        source=self.source,
                        confidence=ConfidenceLevel.HIGH,
                        sequence=self._next_seq(),
                        tags={"kind": "unity_probe"},
                    )
                )
        return out
