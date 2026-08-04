"""ADB Bridge: device discovery, authorization, port forwarding, process selection."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class AdbDevice:
    serial: str
    state: str  # "device", "offline", "unauthorized"
    model: str = ""
    android_version: str = ""
    sdk_level: int = 0
    manufacturer: str = ""
    abi: str = ""

    @property
    def is_ready(self) -> bool:
        return self.state == "device"


@dataclass(slots=True)
class AndroidProcess:
    pid: int
    name: str
    package: str = ""


def _run_adb(args: list[str], timeout: float = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["adb"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


class AdbBridge:
    """ADB connection layer: device discovery, authorization, port forwarding, process selection."""

    def __init__(self, adb_path: str = "adb") -> None:
        self.adb_path = adb_path

    def _adb(self, *args: str, timeout: float = 10) -> subprocess.CompletedProcess:
        return _run_adb(list(args), timeout=timeout)

    # -- Device Discovery --

    def list_devices(self) -> list[AdbDevice]:
        """List all connected devices with status."""
        proc = self._adb("devices", "-l")
        devices: list[AdbDevice] = []
        for line in proc.stdout.splitlines():
            if not line.strip() or line.startswith("List of"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial = parts[0]
            state = parts[1]
            dev = AdbDevice(serial=serial, state=state)
            for part in parts[2:]:
                if part.startswith("model:"):
                    dev.model = part.split(":", 1)[1]
                elif part.startswith("device:"):
                    dev.model = dev.model or part.split(":", 1)[1]
            devices.append(dev)
        return devices

    def get_device_info(self, serial: str) -> AdbDevice:
        """Get detailed device info."""
        dev = AdbDevice(serial=serial, state="device")
        dev.model = self._shell(serial, "getprop ro.product.model").strip()
        dev.manufacturer = self._shell(serial, "getprop ro.product.manufacturer").strip()
        dev.android_version = self._shell(serial, "getprop ro.build.version.release").strip()
        sdk = self._shell(serial, "getprop ro.build.version.sdk").strip()
        if sdk.isdigit():
            dev.sdk_level = int(sdk)
        dev.abi = self._shell(serial, "getprop ro.product.cpu.abi").strip()
        return dev

    def wait_for_device(self, serial: str, timeout: float = 30) -> bool:
        """Wait for device to be ready."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            proc = self._adb("-s", serial, "shell", "echo ready", timeout=5)
            if proc.returncode == 0 and "ready" in proc.stdout:
                return True
            time.sleep(1)
        return False

    # -- Shell & Command --

    def _shell(self, serial: str, cmd: str) -> str:
        proc = self._adb("-s", serial, "shell", cmd, timeout=15)
        if proc.returncode != 0:
            return ""
        return proc.stdout

    def shell(self, serial: str, cmd: str) -> str:
        return self._shell(serial, cmd)

    # -- Port Forwarding --

    def forward(self, serial: str, local: int, remote: int | str) -> bool:
        proc = self._adb("-s", serial, "forward", f"tcp:{local}", f"tcp:{remote}")
        return proc.returncode == 0

    def remove_forward(self, serial: str, local: int) -> bool:
        proc = self._adb("-s", serial, "forward", "--remove", f"tcp:{local}")
        return proc.returncode == 0

    def list_forwards(self, serial: str) -> list[tuple[int, str]]:
        proc = self._adb("-s", serial, "forward", "--list")
        result: list[tuple[int, str]] = []
        for line in proc.stdout.splitlines():
            if serial not in line:
                continue
            parts = line.split()
            if len(parts) >= 3:
                try:
                    local_port = int(parts[1].replace("tcp:", ""))
                    remote = parts[2].replace("tcp:", "")
                    result.append((local_port, remote))
                except ValueError:
                    continue
        return result

    # -- Process Selection --

    def list_packages(self, serial: str, filter_str: str = "") -> list[str]:
        cmd = "pm list packages"
        if filter_str:
            cmd += f" | grep {filter_str}"
        output = self._shell(serial, cmd)
        return [
            line.split(":", 1)[1].strip()
            for line in output.splitlines()
            if line.startswith("package:")
        ]

    def get_pid(self, serial: str, package: str) -> int | None:
        output = self._shell(serial, f"pidof {package}")
        if output.strip().isdigit():
            return int(output.strip())
        output = self._shell(serial, f"ps -A | grep {package}")
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[1])
                except ValueError:
                    continue
        return None

    def list_processes(self, serial: str, filter_str: str = "") -> list[AndroidProcess]:
        output = self._shell(serial, "ps -A -o PID,NAME")
        procs: list[AndroidProcess] = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            name = parts[1]
            if filter_str and filter_str not in name:
                continue
            pkg = name
            if "." in name:
                pkg = name.rsplit(":", 1)[0] if ":" in name else name
            procs.append(AndroidProcess(pid=pid, name=name, package=pkg))
        return procs

    def is_process_running(self, serial: str, package: str) -> bool:
        return self.get_pid(serial, package) is not None

    # -- File Operations --

    def push(self, serial: str, local: str, remote: str) -> bool:
        proc = self._adb("-s", serial, "push", local, remote)
        return proc.returncode == 0

    def pull(self, serial: str, remote: str, local: str) -> bool:
        proc = self._adb("-s", serial, "pull", remote, local)
        return proc.returncode == 0

    # -- GPU Vendor Detection --

    def detect_gpu_vendor(self, serial: str) -> str:
        gpu_info = self._shell(serial, "cat /proc/cpuinfo 2>/dev/null; dumpsys SurfaceFlinger 2>/dev/null | grep GLES")
        gpu_lower = gpu_info.lower()
        if "adreno" in gpu_lower or "kgsl" in gpu_lower:
            return "qualcomm"
        if "mali" in gpu_lower:
            return "mali"
        if "powervr" in gpu_lower or "rogue" in gpu_lower:
            return "powervr"
        return "unknown"

    def get_gpu_node_path(self, serial: str) -> str | None:
        vendor = self.detect_gpu_vendor(serial)
        paths = {
            "qualcomm": "/sys/class/kgsl/kgsl-3d0/gpubusy",
            "mali": "/sys/class/misc/mali0/device/utilization",
        }
        candidate = paths.get(vendor)
        if candidate:
            check = self._shell(serial, f"test -f {candidate} && echo ok || echo no")
            if "ok" in check:
                return candidate
        for p in [
            "/sys/class/kgsl/kgsl-3d0/gpubusy",
            "/sys/kernel/gpu/gpu_busy",
            "/sys/class/devfreq/*/load",
        ]:
            check = self._shell(serial, f"ls {p} 2>/dev/null")
            if check.strip():
                return p
        return None

    def get_temperature_nodes(self, serial: str) -> list[str]:
        output = self._shell(serial, "ls /sys/class/thermal/thermal_zone*/temp 2>/dev/null")
        return [t.strip() for t in output.splitlines() if t.strip()]

    def get_temperature_types(self, serial: str) -> dict[str, str]:
        result: dict[str, str] = {}
        zones = self._shell(serial, "ls -d /sys/class/thermal/thermal_zone* 2>/dev/null")
        for zone in zones.splitlines():
            zone = zone.strip()
            if not zone:
                continue
            type_str = self._shell(serial, f"cat {zone}/type 2>/dev/null").strip()
            temp = self._shell(serial, f"cat {zone}/temp 2>/dev/null").strip()
            if type_str and temp:
                result[zone] = type_str
        return result