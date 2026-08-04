import argparse
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Device:
    serial: str
    state: str
    details: str


def run_adb_command(args: List[str], capture_output: bool = False) -> subprocess.CompletedProcess:
    cmd = ["adb", *args]
    return subprocess.run(
        cmd,
        text=True,
        capture_output=capture_output,
        check=False,
    )


def list_devices() -> List[Device]:
    result = run_adb_command(["devices", "-l"], capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else "Unknown adb error"
        raise RuntimeError(f"Failed to run adb devices: {stderr}")

    devices: List[Device] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        state = parts[1]
        details = " ".join(parts[2:]) if len(parts) > 2 else ""
        devices.append(Device(serial=serial, state=state, details=details))
    return devices


def pick_device(devices: List[Device]) -> Device:
    if not devices:
        raise RuntimeError("No adb devices found. Please connect device and enable USB debugging.")
    if len(devices) == 1:
        return devices[0]

    print("Detected devices:")
    for idx, d in enumerate(devices, start=1):
        details = f" ({d.details})" if d.details else ""
        print(f"  {idx}. {d.serial} [{d.state}]{details}")

    while True:
        choice = input("Select device index: ").strip()
        if not choice.isdigit():
            print("Please enter a number.")
            continue
        index = int(choice)
        if 1 <= index <= len(devices):
            return devices[index - 1]
        print("Out of range, try again.")


def resolve_device_serial(explicit_serial: Optional[str]) -> str:
    devices = list_devices()
    if explicit_serial:
        for d in devices:
            if d.serial == explicit_serial:
                return explicit_serial
        available = ", ".join(d.serial for d in devices) or "(none)"
        raise RuntimeError(f"Device '{explicit_serial}' not found. Available: {available}")
    return pick_device(devices).serial


def print_devices() -> int:
    devices = list_devices()
    if not devices:
        print("No devices found.")
        return 0
    for d in devices:
        details = f" {d.details}" if d.details else ""
        print(f"{d.serial}\t{d.state}{details}")
    return 0


def run_with_device(serial: str, raw_args: List[str]) -> int:
    cmd = ["adb", "-s", serial, *raw_args]
    print("Running:", shlex.join(cmd))
    result = subprocess.run(cmd, check=False)
    return result.returncode


def cmd_install(args: argparse.Namespace) -> int:
    serial = resolve_device_serial(args.device)
    return run_with_device(serial, ["install", *args.install_flags, args.apk_path])


def cmd_logcat(args: argparse.Namespace) -> int:
    serial = resolve_device_serial(args.device)
    raw = ["logcat", *args.logcat_args]
    return run_with_device(serial, raw)


def cmd_exec(args: argparse.Namespace) -> int:
    serial = resolve_device_serial(args.device)
    return run_with_device(serial, args.adb_args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adb-toolbox",
        description="ADB helper: select device and auto inject -s <serial>.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    devices_parser = subparsers.add_parser("devices", help="List adb devices")
    devices_parser.set_defaults(func=lambda _: print_devices())

    install_parser = subparsers.add_parser("install", help="Install APK to selected device")
    install_parser.add_argument("apk_path", help="Path to APK file")
    install_parser.add_argument("-d", "--device", help="Target device serial")
    install_parser.add_argument(
        "--install-flag",
        dest="install_flags",
        action="append",
        default=[],
        help="Additional flag for adb install, can repeat (example: --install-flag -r)",
    )
    install_parser.set_defaults(func=cmd_install)

    logcat_parser = subparsers.add_parser("logcat", help="Show logcat from selected device")
    logcat_parser.add_argument("-d", "--device", help="Target device serial")
    logcat_parser.add_argument(
        "logcat_args",
        nargs=argparse.REMAINDER,
        help="Extra args passed to adb logcat",
    )
    logcat_parser.set_defaults(func=cmd_logcat)

    exec_parser = subparsers.add_parser("exec", help="Execute custom adb command on selected device")
    exec_parser.add_argument("-d", "--device", help="Target device serial")
    exec_parser.add_argument(
        "adb_args",
        nargs=argparse.REMAINDER,
        help="Raw args after adb -s <serial>",
    )
    exec_parser.set_defaults(func=cmd_exec)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except RuntimeError as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
