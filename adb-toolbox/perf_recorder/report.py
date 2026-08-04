"""Enhanced report service: HTML charts, alert sections, comparison reports."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


class ReportService:
    """增强报告服务：HTML 图表、告警段、对比报告。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._alerts: list[dict[str, Any]] = []
        self._session_meta: dict[str, Any] = {}
        self._collection_mode: str = "non-invasive"

    def set_session_meta(self, meta: dict[str, Any]) -> None:
        self._session_meta = meta

    def set_collection_mode(self, mode: str) -> None:
        self._collection_mode = mode

    def add_alerts(self, alerts: list[dict[str, Any]]) -> None:
        self._alerts.extend(alerts)

    # ── HTML Report ───────────────────────────────────────────────

    def build_html(self, out_path: Path, title: str = "Performance Report") -> None:
        conn = sqlite3.connect(str(self.db_path))

        # 聚合统计
        agg_rows = conn.execute(
            """
            SELECT metric_key, ROUND(AVG(value), 2), ROUND(MIN(value), 2),
                   ROUND(MAX(value), 2), COUNT(*), device_id, app_id
            FROM metric_samples
            GROUP BY metric_key, device_id, app_id
            ORDER BY metric_key
            """
        ).fetchall()

        # FPS 时序数据（用于图表）
        fps_rows = conn.execute(
            """
            SELECT timestamp_ms, value FROM metric_samples
            WHERE metric_key = 'fps'
            ORDER BY timestamp_ms ASC
            """
        ).fetchall()

        # CPU 时序数据
        cpu_rows = conn.execute(
            """
            SELECT timestamp_ms, value FROM metric_samples
            WHERE metric_key = 'cpu_app_percent'
            ORDER BY timestamp_ms ASC
            """
        ).fetchall()

        # 温度时序数据
        temp_rows = conn.execute(
            """
            SELECT timestamp_ms, value FROM metric_samples
            WHERE metric_key = 'temperature_c'
            ORDER BY timestamp_ms ASC
            """
        ).fetchall()

        conn.close()

        # 构建聚合表格
        tr_rows = []
        for metric_key, avg_v, min_v, max_v, cnt, dev_id, app_id in agg_rows:
            tr_rows.append(
                f"<tr><td>{metric_key}</td><td>{avg_v}</td><td>{min_v}</td>"
                f"<td>{max_v}</td><td>{cnt}</td><td>{dev_id}</td><td>{app_id}</td></tr>"
            )
        table = "\n".join(tr_rows) if tr_rows else "<tr><td colspan='7'>No data</td></tr>"

        # FPS 图表数据 (JSON)
        fps_data = json.dumps([{"t": r[0], "v": r[1]} for r in fps_rows])
        cpu_data = json.dumps([{"t": r[0], "v": r[1]} for r in cpu_rows])
        temp_data = json.dumps([{"t": r[0], "v": r[1]} for r in temp_rows])

        # 告警段
        alert_html = self._build_alert_section()

        # 会话信息
        session_html = self._build_session_info()

        # 合规提示
        compliance_note = ""
        if "enterprise" in self._collection_mode:
            compliance_note = (
                '<div class="compliance-note" style="background:#fff3cd;padding:10px;margin:10px 0;border-left:4px solid #ffc107;">'
                f"<strong>Compliance Note:</strong> This report was generated with <code>collection_mode={self._collection_mode}</code>. "
                "Enterprise-level metrics may include privately-injected data sources. "
                "Not guaranteed for App Store compliance."
                "</div>"
            )

        # 构建 HTML
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
    h1, h2, h3 {{ color: #e94560; margin: 16px 0 8px; }}
    .card {{ background: #16213e; border-radius: 8px; padding: 16px; margin: 12px 0; box-shadow: 0 2px 8px rgba(0,0,0,0.3); }}
    table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
    th, td {{ border: 1px solid #0f3460; padding: 8px 12px; text-align: left; }}
    th {{ background: #0f3460; color: #e94560; }}
    tr:nth-child(even) {{ background: #1a1a3e; }}
    .chart-container {{ width: 100%; height: 300px; position: relative; margin: 10px 0; background: #0f3460; border-radius: 4px; overflow: hidden; }}
    .alert-item {{ background: #2d1b2e; border-left: 4px solid #e94560; padding: 8px 12px; margin: 6px 0; border-radius: 0 4px 4px 0; }}
    .alert-item.resolved {{ border-left-color: #4ecca3; }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }}
    .meta-item {{ padding: 8px; background: #0f3460; border-radius: 4px; }}
    .meta-item label {{ font-size: 0.8em; color: #aaa; display: block; }}
    .meta-item span {{ font-size: 1.1em; font-weight: bold; }}
    .summary-badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 0.85em; margin: 4px; }}
    .badge-ok {{ background: #4ecca3; color: #1a1a2e; }}
    .badge-warn {{ background: #ffc107; color: #1a1a2e; }}
    .badge-error {{ background: #e94560; color: #fff; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  {compliance_note}
  {session_html}

  <div class="card">
    <h2>FPS Over Time</h2>
    <div class="chart-container" id="fpsChart">
      <canvas id="fpsCanvas" style="width:100%;height:100%"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>CPU Usage Over Time</h2>
    <div class="chart-container" id="cpuChart">
      <canvas id="cpuCanvas" style="width:100%;height:100%"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>Temperature Over Time</h2>
    <div class="chart-container" id="tempChart">
      <canvas id="tempCanvas" style="width:100%;height:100%"></canvas>
    </div>
  </div>

  {alert_html}

  <div class="card">
    <h2>Metrics Summary</h2>
    <table>
      <thead>
        <tr><th>Metric</th><th>Avg</th><th>Min</th><th>Max</th><th>Samples</th><th>Device</th><th>App</th></tr>
      </thead>
      <tbody>{table}</tbody>
    </table>
  </div>

  <script>
    // Simple canvas-based chart renderer
    function drawChart(canvasId, data, label, color) {{
      var canvas = document.getElementById(canvasId);
      if (!canvas) return;
      var ctx = canvas.getContext('2d');
      var container = canvas.parentElement;
      canvas.width = container.clientWidth;
      canvas.height = container.clientHeight;
      var W = canvas.width;
      var H = canvas.height;
      var padding = {{ top: 20, right: 20, bottom: 30, left: 60 }};
      var plotW = W - padding.left - padding.right;
      var plotH = H - padding.top - padding.bottom;

      if (!data || data.length < 2) {{
        ctx.fillStyle = '#888';
        ctx.font = '14px sans-serif';
        ctx.fillText('No data available', W/2 - 60, H/2);
        return;
      }}

      // Find min/max
      var values = data.map(function(d) {{ return d.v; }});
      var minV = Math.min.apply(null, values);
      var maxV = Math.max.apply(null, values);
      var range = maxV - minV || 1;
      var tMin = data[0].t;
      var tMax = data[data.length - 1].t;
      var tRange = tMax - tMin || 1;

      // Background
      ctx.fillStyle = '#0f3460';
      ctx.fillRect(0, 0, W, H);

      // Grid lines
      ctx.strokeStyle = '#1a1a4e';
      ctx.lineWidth = 0.5;
      for (var i = 0; i <= 4; i++) {{
        var y = padding.top + (plotH * i / 4);
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(W - padding.right, y);
        ctx.stroke();
        var val = maxV - (range * i / 4);
        ctx.fillStyle = '#888';
        ctx.font = '10px sans-serif';
        ctx.fillText(val.toFixed(1), 5, y + 4);
      }}

      // Line
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      var first = true;
      for (var i = 0; i < data.length; i++) {{
        var x = padding.left + ((data[i].t - tMin) / tRange) * plotW;
        var y = padding.top + plotH - ((data[i].v - minV) / range) * plotH;
        if (first) {{ ctx.moveTo(x, y); first = false; }}
        else {{ ctx.lineTo(x, y); }}
      }}
      ctx.stroke();

      // Label
      ctx.fillStyle = color;
      ctx.font = '12px sans-serif';
      ctx.fillText(label, padding.left + 10, padding.top - 4);
    }}

    drawChart('fpsCanvas', {fps_data}, 'FPS', '#e94560');
    drawChart('cpuCanvas', {cpu_data}, 'CPU %', '#4ecca3');
    drawChart('tempCanvas', {temp_data}, 'Temp °C', '#ffc107');
  </script>
</body>
</html>"""
        out_path.write_text(html, encoding="utf-8")

    def _build_alert_section(self) -> str:
        if not self._alerts:
            return ""

        items = []
        for a in self._alerts:
            rule = a.get("rule", "Unknown")
            start = a.get("started_at_ms", 0)
            end = a.get("ended_at_ms", 0)
            duration = (end - start) / 1000.0 if end > start else 0
            resolved = a.get("resolved", False)
            cls = "resolved" if resolved else ""
            items.append(
                f'<div class="alert-item {cls}">'
                f"<strong>{rule}</strong> | "
                f"Duration: {duration:.1f}s | "
                f"Start: {datetime.fromtimestamp(start/1000.0).strftime('%H:%M:%S')} | "
                f"Device: {a.get('device_id', 'N/A')}"
                f"</div>"
            )

        return f"""
  <div class="card">
    <h2>Alerts & Anomalies</h2>
    {"".join(items)}
  </div>"""

    def _build_session_info(self) -> str:
        if not self._session_meta:
            return ""

        items = []
        for key, value in self._session_meta.items():
            items.append(
                f'<div class="meta-item"><label>{key}</label><span>{value}</span></div>'
            )

        return f"""
  <div class="card">
    <h2>Session Info</h2>
    <div class="meta-grid">
      {"".join(items)}
    </div>
  </div>"""

    # ── Comparison Report ─────────────────────────────────────────

    def build_comparison_html(
        self,
        out_path: Path,
        sessions_data: dict[str, Any],
        title: str = "Performance Comparison Report",
    ) -> None:
        """生成多版本/多会话对比报告。"""
        metrics = sessions_data.get("metrics", {})
        sessions = sessions_data.get("sessions", {})

        # 构建对比表格
        all_metric_keys: set[str] = set()
        for sid, s_metrics in metrics.items():
            all_metric_keys.update(s_metrics.keys())

        header_cols = "".join(f"<th>{s.get('build_number', sid[:8])} ({s.get('device_id', 'N/A')[:8]})</th>" for sid, s in sessions.items())
        tr_rows = []
        for key in sorted(all_metric_keys):
            cells = f"<td>{key}</td>"
            for sid in sessions:
                m = metrics.get(sid, {}).get(key, {})
                avg = m.get("avg", "-")
                cells += f"<td>{avg}</td>"
            tr_rows.append(f"<tr>{cells}</tr>")

        table = "\n".join(tr_rows) if tr_rows else "<tr><td colspan='99'>No data</td></tr>"

        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }}
    h1 {{ color: #e94560; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid #0f3460; padding: 8px 12px; text-align: left; }}
    th {{ background: #0f3460; color: #e94560; }}
    tr:nth-child(even) {{ background: #1a1a3e; }}
    .card {{ background: #16213e; border-radius: 8px; padding: 16px; margin: 12px 0; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="card">
    <table>
      <thead>
        <tr><th>Metric</th>{header_cols}</tr>
      </thead>
      <tbody>{table}</tbody>
    </table>
  </div>
</body>
</html>"""
        out_path.write_text(html, encoding="utf-8")