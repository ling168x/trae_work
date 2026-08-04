from __future__ import annotations

from abc import ABC, abstractmethod

from .models import MetricSample


class Collector(ABC):
    @abstractmethod
    def poll(self) -> list[MetricSample]:
        raise NotImplementedError
