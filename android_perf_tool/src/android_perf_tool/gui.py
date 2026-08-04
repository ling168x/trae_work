import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import os
from datetime import datetime
from .adb import ADB
from .collector import PerformanceCollector
from .excel_report import ExcelReport
from .html_report import HTMLReport

class PerfToolGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Android性能测试工具")
        self.root.geometry("900x700")
        
        self.adb = ADB()
        self.collector = None
        self.is_collecting = False
        self.collect_thread = None
        self.data = []
        
        self.setup_ui()
        self.refresh_devices()
    
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(main_frame, width=250)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        ttk.Label(left_frame, text="设备选择", font=('Arial', 12, 'bold')).pack(pady=5)
        self.device_list = tk.Listbox(left_frame, height=5)
        self.device_list.pack(fill=tk.X, padx=5)
        ttk.Button(left_frame, text="刷新设备", command=self.refresh_devices).pack(pady=5, fill=tk.X)
        
        ttk.Label(left_frame, text="应用选择", font=('Arial', 12, 'bold')).pack(pady=5)
        self.app_list = tk.Listbox(left_frame, height=8)
        self.app_list.pack(fill=tk.X, padx=5)
        ttk.Button(left_frame, text="刷新应用", command=self.refresh_apps).pack(pady=5, fill=tk.X)
        
        self.start_btn = ttk.Button(left_frame, text="开始记录", command=self.start_collect, state=tk.DISABLED)
        self.start_btn.pack(pady=5, fill=tk.X)
        self.stop_btn = ttk.Button(left_frame, text="停止记录", command=self.stop_collect, state=tk.DISABLED)
        self.stop_btn.pack(pady=5, fill=tk.X)
        
        self.export_btn = ttk.Button(left_frame, text="导出报告", command=self.export_reports, state=tk.DISABLED)
        self.export_btn.pack(pady=5, fill=tk.X)
        
        self.clear_btn = ttk.Button(left_frame, text="清除数据", command=self.clear_data)
        self.clear_btn.pack(pady=5, fill=tk.X)
        
        self.stats_frame = ttk.Frame(right_frame)
        self.stats_frame.pack(fill=tk.X, pady=5)
        
        self.fps_label = ttk.Label(self.stats_frame, text="FPS: --", font=('Arial', 16, 'bold'), foreground='green')
        self.fps_label.pack(side=tk.LEFT, padx=15)
        
        self.cpu_label = ttk.Label(self.stats_frame, text="CPU: --%", font=('Arial', 16, 'bold'), foreground='orange')
        self.cpu_label.pack(side=tk.LEFT, padx=15)
        
        self.mem_label = ttk.Label(self.stats_frame, text="内存: -- MB", font=('Arial', 16, 'bold'), foreground='blue')
        self.mem_label.pack(side=tk.LEFT, padx=15)
        
        self.bat_label = ttk.Label(self.stats_frame, text="电池: --%", font=('Arial', 16, 'bold'), foreground='purple')
        self.bat_label.pack(side=tk.LEFT, padx=15)
        
        self.status_label = ttk.Label(self.stats_frame, text="状态: 就绪", font=('Arial', 12), foreground='gray')
        self.status_label.pack(side=tk.RIGHT, padx=15)
        
        ttk.Label(right_frame, text="实时数据", font=('Arial', 12, 'bold')).pack(pady=5)
        
        self.data_tree = ttk.Treeview(right_frame, columns=('time', 'fps', 'cpu', 'mem', 'bat'), show='headings')
        self.data_tree.heading('time', text='时间')
        self.data_tree.heading('fps', text='FPS')
        self.data_tree.heading('cpu', text='CPU(%)')
        self.data_tree.heading('mem', text='内存(MB)')
        self.data_tree.heading('bat', text='电池(%)')
        
        self.data_tree.column('time', width=150)
        self.data_tree.column('fps', width=80, anchor=tk.CENTER)
        self.data_tree.column('cpu', width=80, anchor=tk.CENTER)
        self.data_tree.column('mem', width=100, anchor=tk.CENTER)
        self.data_tree.column('bat', width=80, anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.data_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.data_tree.configure(yscroll=scrollbar.set)
        self.data_tree.pack(fill=tk.BOTH, expand=True)
        
        self.count_label = ttk.Label(right_frame, text="记录数: 0")
        self.count_label.pack(side=tk.BOTTOM, pady=5)
    
    def refresh_devices(self):
        try:
            devices = self.adb.get_devices()
            self.device_list.delete(0, tk.END)
            for device in devices:
                self.device_list.insert(tk.END, device)
            if devices:
                self.device_list.select_set(0)
                self.refresh_apps()
        except Exception as e:
            messagebox.showerror("错误", f"获取设备列表失败: {str(e)}")
    
    def refresh_apps(self):
        try:
            selected = self.device_list.curselection()
            if not selected:
                return
            
            apps = self.adb.run_command(["shell", "pm", "list", "packages", "-3"]).strip()
            self.app_list.delete(0, tk.END)
            for line in apps.split("\n"):
                if line.startswith("package:"):
                    pkg = line.replace("package:", "").strip()
                    self.app_list.insert(tk.END, pkg)
            
            if self.app_list.size() > 0:
                self.start_btn.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("错误", f"获取应用列表失败: {str(e)}")
    
    def start_collect(self):
        try:
            device_selected = self.device_list.curselection()
            app_selected = self.app_list.curselection()
            
            if not device_selected or not app_selected:
                messagebox.showwarning("警告", "请选择设备和应用")
                return
            
            package_name = self.app_list.get(app_selected[0])
            
            if not self.adb.is_app_running(package_name):
                if not messagebox.askyesno("提示", f"应用 {package_name} 未运行，是否继续?"):
                    return
            
            self.collector = PerformanceCollector(package_name)
            self.data = []
            self.is_collecting = True
            
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.export_btn.config(state=tk.DISABLED)
            self.status_label.config(text="状态: 记录中", foreground='red')
            
            self.collect_thread = threading.Thread(target=self.collect_loop)
            self.collect_thread.daemon = True
            self.collect_thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"启动失败: {str(e)}")
    
    def collect_loop(self):
        while self.is_collecting:
            try:
                sample = {}
                sample['timestamp'] = datetime.now().strftime('%H:%M:%S')
                sample['fps'] = round(self.adb.get_fps(self.collector.package_name), 1)
                
                pid = self.adb.get_pid(self.collector.package_name)
                if pid:
                    sample['cpu'] = round(self.adb.get_cpu_usage(pid), 1)
                    mem = self.adb.get_memory_usage(pid)
                    sample['mem'] = round(mem.get('rss', 0) / (1024 * 1024), 1)
                else:
                    sample['cpu'] = 0
                    sample['mem'] = 0
                
                sample['bat'] = self.adb.get_battery_level()
                
                self.data.append(sample)
                
                self.root.after(0, self.update_ui, sample)
                
                time.sleep(1)
            except Exception as e:
                print(f"采集错误: {e}")
                time.sleep(1)
    
    def update_ui(self, sample):
        self.fps_label.config(text=f"FPS: {sample['fps']}")
        self.cpu_label.config(text=f"CPU: {sample['cpu']}%")
        self.mem_label.config(text=f"内存: {sample['mem']} MB")
        self.bat_label.config(text=f"电池: {sample['bat']}%")
        
        self.data_tree.insert('', 0, values=(
            sample['timestamp'],
            sample['fps'],
            sample['cpu'],
            sample['mem'],
            sample['bat']
        ))
        
        if len(self.data) > 100:
            self.data_tree.delete(self.data_tree.get_children()[-1])
        
        self.count_label.config(text=f"记录数: {len(self.data)}")
    
    def stop_collect(self):
        self.is_collecting = False
        if self.collect_thread:
            self.collect_thread.join(timeout=2)
        
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="状态: 已停止", foreground='green')
        
        if len(self.data) > 0:
            self.export_btn.config(state=tk.NORMAL)
    
    def export_reports(self):
        if not self.data:
            messagebox.showwarning("警告", "没有数据可导出")
            return
        
        output_dir = filedialog.askdirectory(title="选择输出目录")
        if not output_dir:
            return
        
        summary = self.generate_summary()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            excel_path = ExcelReport.generate(self.data, summary, os.path.join(output_dir, f"perf_report_{timestamp}.xlsx"))
            html_path = HTMLReport.generate(self.data, summary, os.path.join(output_dir, f"perf_report_{timestamp}.html"))
            
            messagebox.showinfo("成功", f"报告已导出:\n{excel_path}\n{html_path}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")
    
    def generate_summary(self):
        if not self.data:
            return {}
        
        fps_values = [d['fps'] for d in self.data]
        cpu_values = [d['cpu'] for d in self.data]
        mem_values = [d['mem'] for d in self.data]
        
        return {
            "total_samples": len(self.data),
            "duration": len(self.data),
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
                "min": min(mem_values),
                "max": max(mem_values),
                "avg": sum(mem_values) / len(mem_values)
            }
        }
    
    def clear_data(self):
        if messagebox.askyesno("确认", "确定要清除所有数据吗?"):
            self.data = []
            for item in self.data_tree.get_children():
                self.data_tree.delete(item)
            self.count_label.config(text="记录数: 0")
            self.export_btn.config(state=tk.DISABLED)
            self.fps_label.config(text="FPS: --")
            self.cpu_label.config(text="CPU: --%")
            self.mem_label.config(text="内存: -- MB")
            self.bat_label.config(text="电池: --%")

def main():
    root = tk.Tk()
    app = PerfToolGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()