import subprocess
import re
from typing import Optional, List, Dict, Any

class ADB:
    def __init__(self, adb_path: str = "adb"):
        self.adb_path = adb_path
    
    def run_command(self, command: List[str]) -> str:
        full_command = [self.adb_path] + command
        try:
            result = subprocess.run(full_command, capture_output=True, text=True, timeout=30)
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""
        except FileNotFoundError:
            raise RuntimeError("ADB not found. Please install Android SDK and add ADB to PATH.")
    
    def get_devices(self) -> List[str]:
        output = self.run_command(["devices"])
        lines = output.strip().split("\n")[1:]
        return [line.split("\t")[0] for line in lines if "\tdevice" in line]
    
    def get_package_name(self, app_name: str) -> Optional[str]:
        output = self.run_command(["shell", "pm", "list", "packages"])
        for line in output.split("\n"):
            if app_name.lower() in line.lower():
                return line.replace("package:", "").strip()
        return None
    
    def get_pid(self, package_name: str) -> Optional[int]:
        output = self.run_command(["shell", "ps", "-A"])
        for line in output.split("\n"):
            if package_name in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        return int(parts[1])
                    except ValueError:
                        pass
        return None
    
    def get_fps(self, package_name: str) -> float:
        output = self.run_command(["shell", "dumpsys", "gfxinfo", package_name, "framestats"])
        frames = []
        in_frames = False
        
        for line in output.split("\n"):
            if "Flags" in line and "IntendedVsync" in line:
                in_frames = True
                continue
            if in_frames and line.strip():
                parts = line.strip().split(",")
                if len(parts) >= 11:
                    try:
                        frame_time = float(parts[10]) / 1e6
                        frames.append(frame_time)
                    except (ValueError, IndexError):
                        pass
        
        if not frames:
            return 0.0
        
        total_time = sum(frames)
        if total_time == 0:
            return 0.0
        return len(frames) / total_time
    
    def get_cpu_usage(self, pid: int) -> float:
        output = self.run_command(["shell", "top", "-n", "1", "-b", "-p", str(pid)])
        lines = output.split("\n")
        for line in lines:
            if str(pid) in line:
                parts = line.split()
                if len(parts) >= 9:
                    try:
                        return float(parts[8].replace("%", ""))
                    except ValueError:
                        pass
        return 0.0
    
    def get_memory_usage(self, pid: int) -> Dict[str, int]:
        output = self.run_command(["shell", "cat", f"/proc/{pid}/status"])
        memory = {}
        for line in output.split("\n"):
            if line.startswith("VmSize:"):
                memory["total"] = int(line.split()[1]) * 1024
            elif line.startswith("VmRSS:"):
                memory["rss"] = int(line.split()[1]) * 1024
            elif line.startswith("VmHWM:"):
                memory["peak"] = int(line.split()[1]) * 1024
        return memory
    
    def get_battery_level(self) -> int:
        output = self.run_command(["shell", "dumpsys", "battery"])
        match = re.search(r"level:\s*(\d+)", output)
        if match:
            return int(match.group(1))
        return 0
    
    def get_gpu_info(self, package_name: str) -> Dict[str, Any]:
        output = self.run_command(["shell", "dumpsys", "gfxinfo", package_name])
        info = {}
        
        match = re.search(r"Total frames rendered:\s*(\d+)", output)
        if match:
            info["total_frames"] = int(match.group(1))
        
        match = re.search(r"Janky frames:\s*(\d+)", output)
        if match:
            info["janky_frames"] = int(match.group(1))
        
        match = re.search(r"50th percentile:\s*([\d.]+)", output)
        if match:
            info["fps_50th"] = float(match.group(1))
        
        match = re.search(r"90th percentile:\s*([\d.]+)", output)
        if match:
            info["fps_90th"] = float(match.group(1))
        
        match = re.search(r"95th percentile:\s*([\d.]+)", output)
        if match:
            info["fps_95th"] = float(match.group(1))
        
        match = re.search(r"99th percentile:\s*([\d.]+)", output)
        if match:
            info["fps_99th"] = float(match.group(1))
        
        return info
    
    def is_app_running(self, package_name: str) -> bool:
        output = self.run_command(["shell", "ps", "-A"])
        return package_name in output