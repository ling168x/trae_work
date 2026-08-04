import time
import threading
from typing import List, Dict, Any
from datetime import datetime
from .adb import ADB

class PerformanceData:
    def __init__(self):
        self.timestamp = None
        self.fps = 0.0
        self.cpu = 0.0
        self.memory_rss = 0
        self.memory_total = 0
        self.battery = 0
        self.gpu_info = {}
    
    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "fps": self.fps,
            "cpu": self.cpu,
            "memory_rss_mb": self.memory_rss / (1024 * 1024),
            "memory_total_mb": self.memory_total / (1024 * 1024),
            "battery": self.battery,
            **self.gpu_info
        }

class PerformanceCollector:
    def __init__(self, package_name: str, adb_path: str = "adb"):
        self.adb = ADB(adb_path)
        self.package_name = package_name
        self.pid = None
        self.is_running = False
        self.data: List[PerformanceData] = []
        self.thread = None
        self.interval = 1.0
    
    def start(self, duration: int = 60):
        if not self.adb.is_app_running(self.package_name):
            raise RuntimeError(f"应用 {self.package_name} 未运行")
        
        self.pid = self.adb.get_pid(self.package_name)
        if not self.pid:
            raise RuntimeError(f"无法获取应用 {self.package_name} 的PID")
        
        self.is_running = True
        self.data = []
        
        if duration > 0:
            self.thread = threading.Thread(target=self._collect_for_duration, args=(duration,))
        else:
            self.thread = threading.Thread(target=self._collect_continuous)
        self.thread.start()
    
    def _collect_for_duration(self, duration: int):
        end_time = time.time() + duration
        while self.is_running and time.time() < end_time:
            self._collect_sample()
            time.sleep(self.interval)
    
    def _collect_continuous(self):
        while self.is_running:
            self._collect_sample()
            time.sleep(self.interval)
    
    def _collect_sample(self):
        sample = PerformanceData()
        sample.timestamp = datetime.now().isoformat()
        sample.fps = self.adb.get_fps(self.package_name)
        sample.cpu = self.adb.get_cpu_usage(self.pid)
        
        memory = self.adb.get_memory_usage(self.pid)
        sample.memory_rss = memory.get("rss", 0)
        sample.memory_total = memory.get("total", 0)
        
        sample.battery = self.adb.get_battery_level()
        sample.gpu_info = self.adb.get_gpu_info(self.package_name)
        
        self.data.append(sample)
    
    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join()
    
    def get_data(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self.data]
    
    def get_summary(self) -> Dict[str, Any]:
        if not self.data:
            return {}
        
        fps_values = [d.fps for d in self.data]
        cpu_values = [d.cpu for d in self.data]
        memory_values = [d.memory_rss for d in self.data]
        
        return {
            "total_samples": len(self.data),
            "duration": len(self.data) * self.interval,
            "fps": {
                "min": min(fps_values),
                "max": max(fps_values),
                "avg": sum(fps_values) / len(fps_values),
                "janky_count": sum(1 for f in fps_values if f < 55),
                "janky_rate": sum(1 for f in fps_values if f < 55) / len(fps_values) * 100
            },
            "cpu": {
                "min": min(cpu_values),
                "max": max(cpu_values),
                "avg": sum(cpu_values) / len(cpu_values)
            },
            "memory": {
                "min": min(memory_values) / (1024 * 1024),
                "max": max(memory_values) / (1024 * 1024),
                "avg": sum(memory_values) / len(memory_values) / (1024 * 1024)
            }
        }