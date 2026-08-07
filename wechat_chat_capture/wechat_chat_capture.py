"""
自动翻页截图工具
- 手动框定截图区域（同时也是滚动区域）
- 每次在区域内滚动一屏，截图保存
- 适用于任何可滚动的界面（微信聊天、网页、文档等）
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

from PIL import Image, ImageGrab, ImageTk
import pyautogui


DEFAULT_OUTPUT_DIR = "captures"
SCROLL_DELAY = 0.35


# ==================== 区域框选遮罩 ====================
class RegionSelector:
    """全屏半透明遮罩，让用户框选截图/滚动区域"""

    def __init__(self, on_complete):
        self.on_complete = on_complete
        self.start_x = None
        self.start_y = None
        self.selection_rect = None
        self.result = None

        self.top = tk.Toplevel()
        self.top.attributes("-fullscreen", True)
        self.top.attributes("-topmost", True)
        self.top.configure(bg="black")
        self.top.attributes("-alpha", 0.3)

        self.sw = self.top.winfo_screenwidth()
        self.sh = self.top.winfo_screenheight()

        self.canvas = tk.Canvas(
            self.top, cursor="cross",
            width=self.sw, height=self.sh,
            highlightthickness=0, bg="black",
        )
        self.canvas.pack()

        self.canvas.create_text(
            self.sw // 2, 30,
            text="拖动鼠标框选截图区域（该区域同时作为滚动区域）    ESC 取消",
            fill="white",
            font=("微软雅黑", 13, "bold"),
            tag="hint",
        )

        self.canvas.bind("<ButtonPress-1>", self._on_down)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_up)
        self.top.bind("<Escape>", self._cancel)

    def _on_down(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.canvas.delete("selection", "hint", "size_label")
        self.selection_rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="#00C853", width=2, tag="selection",
        )

    def _on_drag(self, event):
        if self.selection_rect is None:
            return
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        self.canvas.coords(self.selection_rect, x1, y1, x2, y2)

        self.canvas.delete("size_label")
        w, h = x2 - x1, y2 - y1
        label_x = x1 + 5
        label_y = y1 - 5 if y1 > 25 else y1 + 20
        self.canvas.create_text(
            label_x, label_y,
            text=f"{w} x {h}",
            fill="#00C853", anchor="sw",
            font=("微软雅黑", 9, "bold"),
            tag="size_label",
        )

    def _on_up(self, event):
        if self.start_x is None:
            return
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        self.top.destroy()
        if x2 - x1 >= 20 and y2 - y1 >= 20:
            self.result = (x1, y1, x2, y2)
            self.on_complete(self.result)
        else:
            self.on_complete(None)

    def _cancel(self, event=None):
        self.top.destroy()
        self.on_complete(None)


# ==================== 预览窗口 ====================
class PreviewWindow:
    """显示上一页截图预览"""

    def __init__(self, parent):
        self.win = tk.Toplevel(parent)
        self.win.title("截图预览")
        self.win.geometry("420x320")
        self.win.configure(bg="#2c3e50")
        self.win.attributes("-topmost", True)

        self.label = tk.Label(
            self.win, text="等待截图...",
            font=("微软雅黑", 10), fg="#ecf0f1", bg="#2c3e50",
        )
        self.label.pack(expand=True, fill=tk.BOTH)

    def show_image(self, img):
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        img_resized = img.copy()
        img_resized.thumbnail((w - 20, h - 40), Image.LANCZOS)
        self.tk_img = ImageTk.PhotoImage(img_resized)
        self.label.configure(image=self.tk_img, text="")


# ==================== 主应用 ====================
class AutoScrollCaptureApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("自动翻页截图工具")
        self.root.geometry("520x580")
        self.root.minsize(460, 520)
        self.root.configure(bg="#f5f5f5")

        self.capture_area = None
        self.is_capturing = False
        self.stop_flag = False

        self._setup_ui()

    def _setup_ui(self):
        header = tk.Frame(self.root, bg="#1AAD19", height=52)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="自动翻页截图工具",
            font=("微软雅黑", 14, "bold"), fg="white", bg="#1AAD19",
        ).pack(expand=True)

        # 区域选择
        area_frame = tk.LabelFrame(
            self.root, text="截图区域 (同时作为滚动区域)",
            bg="#f5f5f5", font=("微软雅黑", 10, "bold"),
        )
        area_frame.pack(fill=tk.X, padx=15, pady=(12, 5))

        self.area_var = tk.StringVar(value="(未设置)")
        tk.Label(
            area_frame, textvariable=self.area_var,
            font=("Consolas", 10), fg="#2c3e50", bg="#f5f5f5", anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(8, 5))

        btn_row = tk.Frame(area_frame, bg="#f5f5f5")
        btn_row.pack(fill=tk.X, padx=10, pady=(0, 8))

        tk.Button(
            btn_row, text="✏️ 框选区域", command=self._select_region,
            font=("微软雅黑", 10), bg="#e67e22", fg="white",
            border=0, cursor="hand2", padx=12, pady=4,
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            btn_row, text="🖼 预览区域", command=self._preview_area,
            font=("微软雅黑", 10), bg="#3498db", fg="white",
            border=0, cursor="hand2", padx=12, pady=4,
        ).pack(side=tk.LEFT)

        # 设置区
        settings_frame = tk.LabelFrame(
            self.root, text="截图 & 滚动设置",
            bg="#f5f5f5", font=("微软雅黑", 10, "bold"),
        )
        settings_frame.pack(fill=tk.X, padx=15, pady=(5, 5))

        row1 = tk.Frame(settings_frame, bg="#f5f5f5")
        row1.pack(fill=tk.X, padx=10, pady=(8, 4))

        tk.Label(
            row1, text="输出目录:", font=("微软雅黑", 9),
            bg="#f5f5f5", width=10, anchor="w",
        ).pack(side=tk.LEFT)

        self.output_dir_var = tk.StringVar(
            value=os.path.join(os.path.dirname(os.path.abspath(__file__)), DEFAULT_OUTPUT_DIR)
        )
        tk.Entry(
            row1, textvariable=self.output_dir_var,
            font=("微软雅黑", 9),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        tk.Button(
            row1, text="浏览", command=self._browse_output_dir,
            font=("微软雅黑", 9), width=5, bg="#3498db", fg="white",
            border=0, cursor="hand2",
        ).pack(side=tk.LEFT)

        row2 = tk.Frame(settings_frame, bg="#f5f5f5")
        row2.pack(fill=tk.X, padx=10, pady=(4, 4))

        tk.Label(
            row2, text="滚动方式:", font=("微软雅黑", 9),
            bg="#f5f5f5", width=10, anchor="w",
        ).pack(side=tk.LEFT)

        self.scroll_mode_var = tk.StringVar(value="pagedown")
        ttk.Combobox(
            row2, textvariable=self.scroll_mode_var,
            values=["pagedown", "wheel_down", "wheel_up"],
            state="readonly", width=12, font=("微软雅黑", 9),
        ).pack(side=tk.LEFT, padx=5)

        tk.Label(
            row2, text="延迟(秒):", font=("微软雅黑", 9),
            bg="#f5f5f5",
        ).pack(side=tk.LEFT, padx=(12, 0))

        self.delay_var = tk.DoubleVar(value=SCROLL_DELAY)
        tk.Spinbox(
            row2, from_=0.1, to=3.0, increment=0.05,
            textvariable=self.delay_var, width=5, font=("微软雅黑", 9),
        ).pack(side=tk.LEFT, padx=5)

        row3 = tk.Frame(settings_frame, bg="#f5f5f5")
        row3.pack(fill=tk.X, padx=10, pady=(4, 8))

        tk.Label(
            row3, text="截图模式:", font=("微软雅黑", 9),
            bg="#f5f5f5", width=10, anchor="w",
        ).pack(side=tk.LEFT)

        self.mode_var = tk.StringVar(value="continuous")
        ttk.Combobox(
            row3, textvariable=self.mode_var,
            values=["continuous", "fixed"],
            state="readonly", width=12, font=("微软雅黑", 9),
        ).pack(side=tk.LEFT, padx=5)

        tk.Label(
            row3, text="固定页数:", font=("微软雅黑", 9),
            bg="#f5f5f5",
        ).pack(side=tk.LEFT, padx=(12, 0))

        self.max_pages_var = tk.IntVar(value=10)
        tk.Spinbox(
            row3, from_=1, to=500, textvariable=self.max_pages_var,
            width=6, font=("微软雅黑", 9),
        ).pack(side=tk.LEFT, padx=5)

        # 控制按钮
        ctrl_frame = tk.Frame(self.root, bg="#f5f5f5")
        ctrl_frame.pack(fill=tk.X, padx=15, pady=(5, 5))

        self.start_btn = tk.Button(
            ctrl_frame, text="▶ 开始截图", command=self._start_capture,
            font=("微软雅黑", 12, "bold"),
            width=16, height=2,
            bg="#1AAD19", fg="white",
            activebackground="#158F14", activeforeground="white",
            border=0, cursor="hand2",
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_btn = tk.Button(
            ctrl_frame, text="⏹ 停止", command=self._stop_capture,
            font=("微软雅黑", 12, "bold"),
            width=10, height=2,
            bg="#e74c3c", fg="white",
            activebackground="#c0392b", activeforeground="white",
            border=0, cursor="hand2",
            state=tk.DISABLED,
        )
        self.stop_btn.pack(side=tk.LEFT)

        # 状态 & 日志
        self.status_var = tk.StringVar(value="就绪 — 请先框选截图区域")
        tk.Label(
            self.root, textvariable=self.status_var,
            font=("微软雅黑", 9), fg="#7f8c8d", bg="#f5f5f5", anchor="w",
        ).pack(fill=tk.X, padx=15, pady=(0, 3))

        log_frame = tk.LabelFrame(
            self.root, text="运行日志", bg="#f5f5f5", font=("微软雅黑", 9),
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 12))

        self.log_text = tk.Text(
            log_frame, font=("Consolas", 9), wrap=tk.WORD,
            bg="white", relief=tk.FLAT, border=2, padx=8, pady=6,
            height=8,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    # ---------- 区域选择 ----------
    def _select_region(self):
        self.root.withdraw()
        RegionSelector(on_complete=self._on_region_selected)

    def _on_region_selected(self, result):
        self.root.deiconify()
        if result:
            self.capture_area = result
            self._update_area_display()
            self._log(f"✅ 已设置区域: {result}")
            self._log("提示: 请在截图前将目标窗口置于最前")
        else:
            self._log("取消框选")

    def _preview_area(self):
        if not self.capture_area:
            messagebox.showwarning("提示", "请先框选区域")
            return
        try:
            img = ImageGrab.grab(bbox=self.capture_area)
            preview = PreviewWindow(self.root)
            preview.show_image(img)
            self._log(f"预览区域截图: {img.size[0]}x{img.size[1]}")
        except Exception as e:
            self._log(f"预览失败: {e}")

    def _update_area_display(self):
        if self.capture_area:
            x1, y1, x2, y2 = self.capture_area
            w, h = x2 - x1, y2 - y1
            self.area_var.set(
                f"({x1}, {y1}) - ({x2}, {y2})  "
                f"尺寸: {w} x {h}  px"
            )
            self.status_var.set("就绪 — 区域已设置")
        else:
            self.area_var.set("(未设置)")
            self.status_var.set("就绪 — 请先框选截图区域")

    # ---------- 截图流程 ----------
    def _start_capture(self):
        if not self.capture_area:
            messagebox.showerror("错误", "请先框选截图区域")
            return

        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showerror("错误", "请设置输出目录")
            return

        self.is_capturing = True
        self.stop_flag = False
        self.start_btn.config(state=tk.DISABLED, text="截图中...")
        self.stop_btn.config(state=tk.NORMAL)

        thread = threading.Thread(target=self._capture_loop, daemon=True)
        thread.start()

    def _stop_capture(self):
        if self.is_capturing:
            self.stop_flag = True
            self._log("收到停止信号...")

    def _capture_loop(self):
        output_dir = self.output_dir_var.get().strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join(output_dir, timestamp)
        os.makedirs(session_dir, exist_ok=True)

        mode = self.mode_var.get()
        max_pages = self.max_pages_var.get()
        delay = self.delay_var.get()
        scroll_mode = self.scroll_mode_var.get()

        self._log(f"输出: {session_dir}")
        self._log(f"模式: {'连续' if mode == 'continuous' else f'固定 {max_pages} 页'}  滚动: {scroll_mode}  延迟: {delay}s")

        # 给用户时间切到目标窗口
        self._log("请在 3 秒内切换到目标窗口...")
        for i in range(3, 0, -1):
            if self.stop_flag:
                break
            self._update_status(f"{i}...")
            time.sleep(1)

        page = 0
        last_img = None

        try:
            while not self.stop_flag:
                if mode == "fixed" and page >= max_pages:
                    self._log(f"已达固定页数 {max_pages}，停止")
                    break

                # 1. 截图
                try:
                    img = ImageGrab.grab(bbox=self.capture_area)
                except Exception as e:
                    self._log(f"截图失败: {e}")
                    break

                # 检测是否和上一页相同（到底部）
                if last_img is not None and self._images_identical(img, last_img):
                    self._log("⚠️ 截图与上一页完全相同，可能已到底部，自动停止")
                    break

                # 2. 保存
                page += 1
                filename = f"page_{page:04d}.png"
                filepath = os.path.join(session_dir, filename)
                img.save(filepath, "PNG")
                last_img = img

                self._log(f"📸 第 {page} 页: {filename}  ({img.size[0]}x{img.size[1]})")
                self._update_status(f"已截图 {page} 页")

                # 3. 滚动
                if not self.stop_flag:
                    self._scroll(scroll_mode)
                    time.sleep(delay)

        except Exception as e:
            self._log(f"出错: {e}")

        finally:
            self.is_capturing = False
            self.root.after(0, lambda: self.start_btn.config(
                state=tk.NORMAL, text="▶ 开始截图",
            ))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            self._log(f"✅ 完成！共 {page} 页，保存至: {session_dir}")
            self._update_status(f"完成，共 {page} 页")

    def _scroll(self, mode):
        x1, y1, x2, y2 = self.capture_area
        margin = 8
        rx = x2 - margin
        cy = (y1 + y2) // 2

        if mode == "pagedown":
            pyautogui.click(rx, cy)
            time.sleep(0.08)
            pyautogui.press("pagedown")
        elif mode == "wheel_down":
            pyautogui.moveTo(rx, cy)
            pyautogui.scroll(-3)
        elif mode == "wheel_up":
            pyautogui.moveTo(rx, cy)
            pyautogui.scroll(3)

    @staticmethod
    def _images_identical(img1, img2):
        if img1.size != img2.size:
            return False
        try:
            pixels1 = list(img1.getdata())
            pixels2 = list(img2.getdata())
            if len(pixels1) != len(pixels2):
                return False
            diff = sum(
                abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
                for a, b in zip(pixels1, pixels2)
            )
            max_diff = len(pixels1) * 255 * 3
            return diff < max_diff * 0.001
        except Exception:
            return False

    # ---------- 辅助 ----------
    def _browse_output_dir(self):
        path = filedialog.askdirectory(
            initialdir=self.output_dir_var.get(),
        )
        if path:
            self.output_dir_var.set(path)

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.root.after(0, lambda: self._append_log(line))

    def _append_log(self, line):
        self.log_text.insert(tk.END, line)
        self.log_text.see(tk.END)

    def _update_status(self, msg):
        self.root.after(0, lambda: self.status_var.set(msg))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = AutoScrollCaptureApp()
    app.run()
