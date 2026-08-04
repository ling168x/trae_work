from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_fps_error(system_fps: list[float], unity_fps: list[float]) -> float:
    n = min(len(system_fps), len(unity_fps))
    if n == 0:
        return 1.0
    total = 0.0
    for i in range(n):
        s = max(system_fps[i], 0.0001)
        total += abs(system_fps[i] - unity_fps[i]) / s
    return total / n


def validate_drop_rate(timestamps_ms: list[int], expected_interval_ms: int) -> float:
    if len(timestamps_ms) < 2:
        return 1.0
    drops = 0
    for i in range(1, len(timestamps_ms)):
        if timestamps_ms[i] - timestamps_ms[i - 1] > expected_interval_ms * 1.8:
            drops += 1
    return drops / max(len(timestamps_ms) - 1, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate FPS accuracy and sample continuity.")
    parser.add_argument("--input", required=True, help="JSON file exported from perf recorder")
    parser.add_argument("--target-fps-error", type=float, default=0.05)
    parser.add_argument("--target-drop-rate", type=float, default=0.005)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    sys_fps = [x["value"] for x in payload if x["metric_key"] == "fps" and x["source"] in {"android.system", "ios.public"}]
    sdk_fps = [x["value"] for x in payload if x["metric_key"] == "fps" and x["source"] in {"android.unity_sdk", "ios.unity_sdk"}]
    ts = [x["timestamp_ms"] for x in payload if x["metric_key"] == "fps"]
    ts.sort()

    fps_error = validate_fps_error(sys_fps, sdk_fps)
    drop_rate = validate_drop_rate(ts, expected_interval_ms=100)

    passed = fps_error <= args.target_fps_error and drop_rate <= args.target_drop_rate
    print(f"fps_error={fps_error:.4f} target<={args.target_fps_error:.4f}")
    print(f"drop_rate={drop_rate:.4f} target<={args.target_drop_rate:.4f}")
    print("result=PASS" if passed else "result=FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
