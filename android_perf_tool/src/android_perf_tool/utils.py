from typing import List

def format_size(bytes_size: int) -> str:
    if bytes_size < 1024:
        return f"{bytes_size} B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    else:
        return f"{bytes_size / (1024 * 1024):.1f} MB"

def format_percent(value: float) -> str:
    return f"{value:.1f}%"

def validate_package_name(package_name: str) -> bool:
    return package_name.startswith("com.") and len(package_name) > 4

def get_device_info(adb) -> dict:
    info = {}
    info["model"] = adb.run_command(["shell", "getprop", "ro.product.model"]).strip()
    info["brand"] = adb.run_command(["shell", "getprop", "ro.product.brand"]).strip()
    info["android_version"] = adb.run_command(["shell", "getprop", "ro.build.version.release"]).strip()
    return info

def list_installed_apps(adb) -> List[str]:
    output = adb.run_command(["shell", "pm", "list", "packages", "-3"])
    packages = []
    for line in output.split("\n"):
        if line.startswith("package:"):
            packages.append(line.replace("package:", "").strip())
    return packages