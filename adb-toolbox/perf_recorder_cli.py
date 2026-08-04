from __future__ import annotations

import argparse
from pathlib import Path

from perf_recorder.android_collector import AndroidCollector
from perf_recorder.host import PerfRecorderHost, SessionConfig
from perf_recorder.ios_collector import IOSCollector
from perf_recorder.models import MetricSource
from perf_recorder.report import ReportService
from perf_recorder.storage import SQLiteMetricStorage
from perf_recorder.unity_collector import UnityProbeCollector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="perf-recorder", description="Android/iOS performance recorder host")
    sub = parser.add_subparsers(dest="command", required=True)

    monitor = sub.add_parser("monitor", help="Run a recording session")
    monitor.add_argument("--platform", choices=["android", "ios"], required=True)
    monitor.add_argument("--device-id", required=True, help="Android serial or iOS UDID")
    monitor.add_argument("--app-id", required=True)
    monitor.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    monitor.add_argument("--db", default="sessions/perf_metrics.db")
    monitor.add_argument("--unity-probe-file", help="Optional newline-delimited JSON from Unity probe")
    monitor.add_argument("--live", action="store_true", help="Print simple realtime dashboard in terminal")
    monitor.set_defaults(func=cmd_monitor)

    export = sub.add_parser("export", help="Export session database")
    export.add_argument("--db", default="sessions/perf_metrics.db")
    export.add_argument("--format", choices=["csv", "json"], required=True)
    export.add_argument("--out", required=True)
    export.set_defaults(func=cmd_export)

    report = sub.add_parser("report", help="Build HTML report")
    report.add_argument("--db", default="sessions/perf_metrics.db")
    report.add_argument("--out", default="sessions/report.html")
    report.set_defaults(func=cmd_report)
    return parser


def cmd_monitor(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    storage = SQLiteMetricStorage(db_path)
    host = PerfRecorderHost(storage)

    if args.platform == "android":
        host.register_collector(AndroidCollector(serial=args.device_id, app_id=args.app_id))
        unity_source = MetricSource.ANDROID_UNITY_SDK
    else:
        host.register_collector(IOSCollector(udid=args.device_id, app_id=args.app_id, enterprise_mode=True))
        unity_source = MetricSource.IOS_UNITY_SDK

    if args.unity_probe_file:
        host.register_collector(
            UnityProbeCollector(
                device_id=args.device_id,
                app_id=args.app_id,
                probe_file=Path(args.unity_probe_file),
                source=unity_source,
            )
        )

    def on_tick(samples):
        if not args.live or not samples:
            return
        key_metrics = [s for s in samples if s.metric_key.value in {"fps", "frame_time_ms", "cpu_total_percent", "temperature_c"}]
        if key_metrics:
            line = " | ".join(f"{s.metric_key.value}={s.value:.2f}{s.unit}" for s in key_metrics[:4])
            print(f"[tick] {line}")

    summary = host.run_session(SessionConfig(app_id=args.app_id, duration_sec=args.duration), on_tick=on_tick)
    storage.close()
    print(f"Session finished: {summary}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    storage = SQLiteMetricStorage(Path(args.db))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "csv":
        storage.export_csv(out)
    else:
        storage.export_json(out)
    storage.close()
    print(f"Exported {args.format} to {out}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    db = Path(args.db)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ReportService(db).build_html(out)
    print(f"Report written: {out}")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
