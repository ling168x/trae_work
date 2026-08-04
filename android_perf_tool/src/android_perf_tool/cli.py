import argparse
import sys
import os
from datetime import datetime
from .collector import PerformanceCollector
from .excel_report import ExcelReport
from .html_report import HTMLReport
from .adb import ADB

def main():
    parser = argparse.ArgumentParser(description="Android性能数据记录工具 - 类似PerfDog")
    parser.add_argument("-p", "--package", required=True, help="应用包名或应用名称")
    parser.add_argument("-d", "--duration", type=int, default=60, help="测试时长(秒)，默认60秒")
    parser.add_argument("-o", "--output", default="./reports", help="报告输出目录")
    parser.add_argument("--adb-path", default="adb", help="ADB路径")
    parser.add_argument("--no-excel", action="store_true", help="不生成Excel报告")
    parser.add_argument("--no-html", action="store_true", help="不生成HTML报告")
    
    args = parser.parse_args()
    
    adb = ADB(args.adb_path)
    
    package_name = args.package
    if not package_name.startswith("com."):
        found_package = adb.get_package_name(package_name)
        if found_package:
            package_name = found_package
            print(f"找到应用包名: {package_name}")
        else:
            print(f"无法找到应用: {args.package}")
            sys.exit(1)
    
    if not adb.is_app_running(package_name):
        print(f"应用 {package_name} 未运行，请先启动应用")
        sys.exit(1)
    
    print(f"开始采集性能数据，时长: {args.duration}秒")
    
    collector = PerformanceCollector(package_name, args.adb_path)
    collector.start(args.duration)
    
    try:
        while collector.is_running:
            print(f"\r已采集 {len(collector.data)} 个样本...", end="")
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n用户中断，停止采集")
        collector.stop()
    
    collector.stop()
    
    data = collector.get_data()
    summary = collector.get_summary()
    
    print(f"\n采集完成，共 {len(data)} 个样本")
    print(f"平均FPS: {summary.get('fps', {}).get('avg', 0):.1f}")
    print(f"平均CPU: {summary.get('cpu', {}).get('avg', 0):.1f}%")
    print(f"平均内存: {summary.get('memory', {}).get('avg', 0):.1f} MB")
    print(f"卡顿率: {summary.get('fps', {}).get('janky_rate', 0):.1f}%")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)
    
    if not args.no_excel:
        excel_path = os.path.join(output_dir, f"perf_report_{timestamp}.xlsx")
        ExcelReport.generate(data, summary, excel_path)
        print(f"Excel报告已生成: {excel_path}")
    
    if not args.no_html:
        html_path = os.path.join(output_dir, f"perf_report_{timestamp}.html")
        HTMLReport.generate(data, summary, html_path)
        print(f"HTML报告已生成: {html_path}")

if __name__ == "__main__":
    main()