from __future__ import annotations

import subprocess


def list_ios_devices() -> list[str]:
    """
    Requires libimobiledevice tooling (`idevice_id -l`).
    """
    proc = subprocess.run(["idevice_id", "-l"], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def validate_enterprise_channel(udid: str) -> bool:
    """
    Best-effort check to validate that the enterprise distribution path is alive.
    """
    proc = subprocess.run(["ideviceinfo", "-u", udid], capture_output=True, text=True, check=False)
    return proc.returncode == 0 and "UniqueDeviceID" in proc.stdout
