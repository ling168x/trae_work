from typing import List, Dict, Any
from datetime import datetime
import os
import json

class HTMLReport:
    @staticmethod
    def generate(data: List[Dict[str, Any]], summary: Dict[str, Any], output_path: str):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Android性能测试报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f7fa; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        .header p {{ opacity: 0.9; }}
        .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
        .card-title {{ color: #666; font-size: 14px; margin-bottom: 8px; }}
        .card-value {{ font-size: 28px; font-weight: bold; color: #333; }}
        .card-value.fps {{ color: #4CAF50; }}
        .card-value.cpu {{ color: #FF9800; }}
        .card-value.memory {{ color: #2196F3; }}
        .card-value.warning {{ color: #F44336; }}
        .section {{ background: white; border-radius: 12px; padding: 25px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 20px; }}
        .section-title {{ font-size: 20px; font-weight: 600; margin-bottom: 20px; color: #333; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; color: #666; }}
        tr:hover {{ background: #f8f9fa; }}
        .chart-container {{ height: 300px; position: relative; }}
        .stats-row {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }}
        .stat-item {{ text-align: center; padding: 15px; background: #f8f9fa; border-radius: 8px; }}
        .stat-label {{ color: #666; font-size: 14px; margin-bottom: 5px; }}
        .stat-value {{ font-size: 22px; font-weight: bold; }}
        .timestamp {{ color: #999; font-size: 12px; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Android性能测试报告</h1>
            <p>测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="summary-cards">
            <div class="card">
                <div class="card-title">平均帧率 (FPS)</div>
                <div class="card-value fps">{summary.get('fps', {}).get('avg', 0):.1f}</div>
            </div>
            <div class="card">
                <div class="card-title">平均CPU占用 (%)</div>
                <div class="card-value cpu">{summary.get('cpu', {}).get('avg', 0):.1f}</div>
            </div>
            <div class="card">
                <div class="card-title">平均内存 (MB)</div>
                <div class="card-value memory">{summary.get('memory', {}).get('avg', 0):.1f}</div>
            </div>
            <div class="card">
                <div class="card-title">卡顿率</div>
                <div class="card-value {'warning' if summary.get('fps', {}).get('janky_rate', 0) > 5 else ''}">{summary.get('fps', {}).get('janky_rate', 0):.1f}%</div>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">📈 帧率趋势</div>
            <div class="chart-container">
                <canvas id="fpsChart"></canvas>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">⚡ CPU使用率趋势</div>
            <div class="chart-container">
                <canvas id="cpuChart"></canvas>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">💾 内存使用趋势</div>
            <div class="chart-container">
                <canvas id="memoryChart"></canvas>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">📊 详细统计</div>
            <div class="stats-row">
                <div class="stat-item">
                    <div class="stat-label">FPS统计</div>
                    <div class="stat-value" style="color: #4CAF50;">{summary.get('fps', {}).get('min', 0):.1f} ~ {summary.get('fps', {}).get('max', 0):.1f}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">CPU统计</div>
                    <div class="stat-value" style="color: #FF9800;">{summary.get('cpu', {}).get('min', 0):.1f}% ~ {summary.get('cpu', {}).get('max', 0):.1f}%</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">内存统计</div>
                    <div class="stat-value" style="color: #2196F3;">{summary.get('memory', {}).get('min', 0):.1f} ~ {summary.get('memory', {}).get('max', 0):.1f} MB</div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <div class="section-title">📋 原始数据</div>
            <table>
                <thead>
                    <tr>
                        <th>时间</th>
                        <th>FPS</th>
                        <th>CPU (%)</th>
                        <th>内存 (MB)</th>
                        <th>电池 (%)</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join([f'<tr><td>{row["timestamp"]}</td><td>{row["fps"]:.1f}</td><td>{row["cpu"]:.1f}</td><td>{row["memory_rss_mb"]:.1f}</td><td>{row["battery"]}</td></tr>' for row in data])}
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        const fpsData = {json.dumps([row['fps'] for row in data])};
        const cpuData = {json.dumps([row['cpu'] for row in data])};
        const memoryData = {json.dumps([row['memory_rss_mb'] for row in data])};
        const labels = {json.dumps([i+1 for i in range(len(data))])};
        
        new Chart(document.getElementById('fpsChart'), {{
            type: 'line',
            data: {{ labels, datasets: [{{
                label: 'FPS',
                data: fpsData,
                borderColor: '#4CAF50',
                backgroundColor: 'rgba(76, 175, 80, 0.1)',
                fill: true,
                tension: 0.4
            }}] }},
            options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }},
                scales: {{ y: {{ min: 0, max: 70, title: {{ display: true, text: 'FPS' }} }} }}
        }});
        
        new Chart(document.getElementById('cpuChart'), {{
            type: 'line',
            data: {{ labels, datasets: [{{
                label: 'CPU',
                data: cpuData,
                borderColor: '#FF9800',
                backgroundColor: 'rgba(255, 152, 0, 0.1)',
                fill: true,
                tension: 0.4
            }}] }},
            options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }},
                scales: {{ y: {{ min: 0, max: 100, title: {{ display: true, text: 'CPU %' }} }} }}
        }});
        
        new Chart(document.getElementById('memoryChart'), {{
            type: 'line',
            data: {{ labels, datasets: [{{
                label: 'Memory',
                data: memoryData,
                borderColor: '#2196F3',
                backgroundColor: 'rgba(33, 150, 243, 0.1)',
                fill: true,
                tension: 0.4
            }}] }},
            options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }},
                scales: {{ y: {{ title: {{ display: true, text: 'MB' }} }} }}
        }});
    <\/script>
</body>
</html>"""
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return output_path