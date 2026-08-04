import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from android_perf_tool.excel_report import ExcelReport
from android_perf_tool.html_report import HTMLReport

import random
from datetime import datetime, timedelta

def generate_test_data(count=60):
    data = []
    start_time = datetime.now()
    for i in range(count):
        timestamp = (start_time + timedelta(seconds=i)).isoformat()
        data.append({
            "timestamp": timestamp,
            "fps": round(random.uniform(55, 60), 1),
            "cpu": round(random.uniform(20, 60), 1),
            "memory_rss_mb": round(random.uniform(500, 800), 1),
            "memory_total_mb": round(random.uniform(800, 1200), 1),
            "battery": random.randint(70, 100)
        })
    return data

def generate_test_summary(data):
    fps_values = [d["fps"] for d in data]
    cpu_values = [d["cpu"] for d in data]
    memory_values = [d["memory_rss_mb"] for d in data]
    
    return {
        "total_samples": len(data),
        "duration": len(data),
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
            "min": min(memory_values),
            "max": max(memory_values),
            "avg": sum(memory_values) / len(memory_values)
        }
    }

if __name__ == "__main__":
    print("Generating test data...")
    test_data = generate_test_data(60)
    test_summary = generate_test_summary(test_data)
    
    os.makedirs("./test_reports", exist_ok=True)
    
    print("Generating Excel report...")
    excel_path = ExcelReport.generate(test_data, test_summary, "./test_reports/test_report.xlsx")
    print(f"Excel report generated: {excel_path}")
    
    print("Generating HTML report...")
    html_path = HTMLReport.generate(test_data, test_summary, "./test_reports/test_report.html")
    print(f"HTML report generated: {html_path}")
    
    print("\nTest completed successfully!")
    print(f"Sample data count: {len(test_data)}")
    print(f"Average FPS: {test_summary['fps']['avg']:.1f}")
    print(f"Average CPU: {test_summary['cpu']['avg']:.1f}%")
    print(f"Average Memory: {test_summary['memory']['avg']:.1f} MB")