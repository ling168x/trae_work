"""MetricStreamBus: 内存总线 + 背压控制 + 环形缓冲降采样."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable

from .models import ConfidenceLevel, MetricKey, MetricSample, MetricSource


@dataclass
class RingBuffer:
    """环形缓冲，用于高频数据降采样入库。"""

    key: MetricKey
    capacity: int = 300  # 默认保留最近 300 个采样点

    def __post_init__(self) -> None:
        self._buffer: deque[tuple[int, float]] = deque(maxlen=self.capacity)

    def push(self, timestamp_ms: int, value: float) -> None:
        self._buffer.append((timestamp_ms, value))

    def drain(self) -> list[tuple[int, float]]:
        """导出当前全部数据并清空缓冲。"""
        items = list(self._buffer)
        self._buffer.clear()
        return items

    def aggregate(self) -> dict[str, float]:
        """对缓冲区内数据计算聚合统计。"""
        if not self._buffer:
            return {}
        values = [v for _, v in self._buffer]
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "avg": sum(values) / n,
            "min": min(values),
            "max": max(values),
            "p50": sorted_vals[int(n * 0.50)] if n > 0 else 0,
            "p95": sorted_vals[int(n * 0.95)] if n > 1 else sorted_vals[0],
            "p99": sorted_vals[int(n * 0.99)] if n > 1 else sorted_vals[0],
        }

    def __len__(self) -> int:
        return len(self._buffer)


@dataclass
class StreamBusConfig:
    """流总线配置。"""

    max_queue_size: int = 2000  # 最大队列长度，超过则触发背压
    ring_buffer_capacity: int = 300  # 环形缓冲默认容量
    high_freq_keys: set[MetricKey] = field(default_factory=lambda: {
        MetricKey.FPS,
        MetricKey.FRAME_TIME_MS,
    })


class MetricStreamBus:
    """
    内存指标总线，负责：
    1. 接收各采集器的 MetricSample
    2. 对高频指标（FPS/FrameTime）写入环形缓冲并降采样
    3. 背压控制：队列超限时丢弃低优先级旧数据
    4. 将数据分发给订阅者（存储、UI、告警）
    """

    def __init__(self, config: StreamBusConfig | None = None) -> None:
        self.config = config or StreamBusConfig()
        self._lock = threading.Lock()
        self._queue: deque[MetricSample] = deque(maxlen=self.config.max_queue_size)
        self._ring_buffers: dict[tuple[str, str, MetricKey], RingBuffer] = {}
        self._subscribers: list[Callable[[list[MetricSample]], None]] = []
        self._drop_count: int = 0
        self._total_count: int = 0

    def publish(self, samples: list[MetricSample]) -> None:
        """发布一批采样数据到总线。"""
        with self._lock:
            for sample in samples:
                self._total_count += 1
                # 高频指标走环形缓冲
                if sample.metric_key in self.config.high_freq_keys:
                    buf_key = (sample.device_id, sample.app_id, sample.metric_key)
                    if buf_key not in self._ring_buffers:
                        self._ring_buffers[buf_key] = RingBuffer(
                            key=sample.metric_key,
                            capacity=self.config.ring_buffer_capacity,
                        )
                    self._ring_buffers[buf_key].push(sample.timestamp_ms, sample.value)
                else:
                    self._queue.append(sample)

            # 背压控制：队列超限时丢弃最旧数据
            while len(self._queue) > self.config.max_queue_size:
                self._queue.popleft()
                self._drop_count += 1

    def drain_ring_buffers(self) -> list[MetricSample]:
        """将环形缓冲中的数据降采样导出为标准 MetricSample。"""
        with self._lock:
            out: list[MetricSample] = []
            now = int(time.time() * 1000)
            for (device_id, app_id, metric_key), buf in self._ring_buffers.items():
                agg = buf.aggregate()
                if not agg:
                    continue
                # 导出聚合后的分位值
                base_source = MetricSource.AGGREGATED
                for stat_key, stat_value in agg.items():
                    derived_key = metric_key
                    unit = "fps" if metric_key == MetricKey.FPS else "ms"
                    if stat_key == "p95":
                        derived_key = MetricKey.FRAME_TIME_P95_MS
                        unit = "ms"
                    elif stat_key == "p99":
                        # P99 作为 tag 标记
                        pass
                    elif stat_key == "p50":
                        # P50 作为帧时间中位数
                        pass
                    out.append(
                        MetricSample(
                            timestamp_ms=now,
                            device_id=device_id,
                            app_id=app_id,
                            metric_key=derived_key if stat_key == "avg" else metric_key,
                            value=stat_value,
                            unit=unit,
                            source=base_source,
                            confidence=ConfidenceLevel.MEDIUM,
                            sequence=0,
                            tags={"stat": stat_key},
                        )
                    )
                # 清空缓冲
                buf.drain()
            return out

    def emit(self) -> list[MetricSample]:
        """
        从队列中取出一批数据（用于存储落盘），同时合并环形缓冲降采样结果。
        """
        with self._lock:
            batch = list(self._queue)
            self._queue.clear()
            batch.extend(self.drain_ring_buffers())
        return batch

    def subscribe(self, callback: Callable[[list[MetricSample]], None]) -> None:
        """注册订阅者（存储/UI 回调）。"""
        self._subscribers.append(callback)

    def notify(self, samples: list[MetricSample]) -> None:
        """通知所有订阅者。"""
        for cb in self._subscribers:
            try:
                cb(samples)
            except Exception:
                pass

    @property
    def drop_count(self) -> int:
        return self._drop_count

    @property
    def total_count(self) -> int:
        return self._total_count

    @property
    def queue_size(self) -> int:
        with self._lock:
            return len(self._queue)

    def stats(self) -> dict[str, object]:
        return {
            "queue_size": self.queue_size,
            "total_count": self._total_count,
            "drop_count": self._drop_count,
            "ring_buffer_count": len(self._ring_buffers),
        }