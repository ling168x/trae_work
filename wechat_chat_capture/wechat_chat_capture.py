"""
微信聊天自动翻页截图工具
- 自动检测微信主窗口
- 仅截取聊天记录框内区域（不含侧边栏/输入框）
- 每次翻一页截图，可连续翻页或指定页数
- 支持自动检测 + 手动校准聊天区域
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

import win32gui
import win32con
import win32api
from PIL import Image, ImageGrab, ImageTk
import pyautogui

try:
    import uiautomation as auto
    HAS_UIA = True
except ImportError:
    HAS_UIA = False


# ==================== 配置 ====================
DEFAULT_OUTPUT_DIR = "captures"
SCROLL_DELAY = 0.35
PAGE_DOWN_KEY = "pagedown"

WECHAT_CLASS = "WeChatMainWndForPC"

# 启发式估算：微信窗口内各边距（像素）
MARGIN_SIDEBAR = 65
MARGIN_TOPBAR = 70
MARGIN_INPUTBAR = 110
MARGIN_RIGHT = 8


# ==================== 区域校准遮罩 ====================
class CalibrationOverlay:
    """全屏半透明遮罩，让用户框选聊天记录区域"""

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
        self.top.attributes("-alpha", 0.4)

        self.canvas = tk.Canvas(
            self.top, cursor="cross",
            width=self.top.winfo_screenwidth(),
            height=self.top.winfo_screenheight(),
            highlightthickness=0, bg="black",
        )
        self.canvas.pack()

        self.sw = self.top.winfo_screenwidth()
        self.sh = self.top.winfo_screenheight()

        self.canvas.create_text(
            self.sw // 2, 30,
            text="拖动鼠标框选微信聊天记录区域（消息列表框内）    ESC 取消",
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


# ==================== 主应用 ====================
class WeChatChatCaptureApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("微信聊天自动翻页截图工具")
        self.root.geometry("560x640")
        self.root.minsize(500, 580)
        self.root.configure(bg="#f5f5f5")

        self.hwnd = None
        self.chat_area = None
        self.is_capturing = False
        self.stop_flag = False
        self.capture_thread = None

        self._setup_ui()
        self._refresh_window()

    # ---------- UI ----------
    def _setup_ui(self):
        header = tk.Frame(self.root, bg="#1AAD19", height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="微信聊天自动翻页截图",
            font=("微软雅黑", 15, "bold"), fg="white", bg="#1AAD19",
        ).pack(expand=True)

        # 窗口检测区
        win_frame = tk.LabelFrame(
            self.root, text="微信窗口", bg="#f5f5f5", font=("微软雅黑", 10, "bold"),
        )
        win_frame.pack(fill=tk.X, padx=15, pady=(12, 5))

        self.window_info_var = tk.StringVar(value="未检测到微信窗口")
        tk.Label(
            win_frame, textvariable=self.window_info_var,
            font=("微软雅黑", 9), fg="#7f8c8d", bg="#f5f5f5", anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(8, 5))

        btn_row = tk.Frame(win_frame, bg="#f5f5f5")
        btn_row.pack(fill=tk.X, padx=10, pady=(0, 8))

        tk.Button(
            btn_row, text="🔍 刷新检测", command=self._refresh_window,
            font=("微软雅黑", 9), bg="#3498db", fg="white",
            border=0, cursor="hand2", padx=10, pady=4,
        ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(
            btn_row, text="📋 自动识别聊天区域", command=self._auto_detect_area,
            font=("微软雅黑", 9), bg="#9b59b6", fg="white",
            border=0, cursor="hand2", padx=10, pady=4,
        ).pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(
            btn_row, text="✏️ 手动校准区域", command=self._manual_calibrate,
            font=("微软雅黑", 9), bg="#e67e22", fg="white",
            border=0, cursor="hand2", padx=10, pady=4,
        ).pack(side=tk.LEFT)

        # 聊天区域显示
        area_frame = tk.LabelFrame(
            self.root, text="聊天记录区域 (left, top, right, bottom)",
            bg="#f5f5f5", font=("微软雅黑", 10, "bold"),
        )
        area_frame.pack(fill=tk.X, padx=15, pady=(5, 5))

        self.area_var = tk.StringVar(value="(未设置)")
        tk.Label(
            area_frame, textvariable=self.area_var,
            font=("Consolas", 10), fg="#2c3e50", bg="#f5f5f5", anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(8, 8))

        # 设置区
        settings_frame = tk.LabelFrame(
            self.root, text="截图设置", bg="#f5f5f5", font=("微软雅黑", 10, "bold"),
        )
        settings_frame.pack(fill=tk.X, padx=15, pady=(5, 5))

        row1 = tk.Frame(settings_frame, bg="#f5f5f5")
        row1.pack(fill=tk.X, padx=10, pady=(8, 4))

        tk.Label(
            row1, text="输出目录:", font=("微软雅黑", 9),
            bg="#f5f5f5",
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
            row2, text="翻页方式:", font=("微软雅黑", 9),
            bg="#f5f5f5",
        ).pack(side=tk.LEFT)

        self.scroll_mode_var = tk.StringVar(value="pagedown")
        ttk.Combobox(
            row2, textvariable=self.scroll_mode_var,
            values=["pagedown", "wheel_down", "wheel_up"],
            state="readonly", width=12, font=("微软雅黑", 9),
        ).pack(side=tk.LEFT, padx=5)

        tk.Label(
            row2, text="翻页延迟(秒):", font=("微软雅黑", 9),
            bg="#f5f5f5",
        ).pack(side=tk.LEFT, padx=(15, 0))

        self.delay_var = tk.DoubleVar(value=SCROLL_DELAY)
        tk.Spinbox(
            row2, from_=0.1, to=2.0, increment=0.05,
            textvariable=self.delay_var, width=5, font=("微软雅黑", 9),
        ).pack(side=tk.LEFT, padx=5)

        row3 = tk.Frame(settings_frame, bg="#f5f5f5")
        row3.pack(fill=tk.X, padx=10, pady=(4, 8))

        tk.Label(
            row3, text="截图模式:", font=("微软雅黑", 9),
            bg="#f5f5f5",
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
        ).pack(side=tk.LEFT, padx=(15, 0))

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
        self.status_var = tk.StringVar(value="就绪")
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

    # ---------- 窗口检测 ----------
    def _refresh_window(self):
        hwnd = win32gui.FindWindow(WECHAT_CLASS, None)
        if hwnd:
            title = win32gui.GetWindowText(hwnd) or "(无标题)"
            rect = win32gui.GetWindowRect(hwnd)
            self.hwnd = hwnd
            self.window_info_var.set(
                f"✅ 已检测到: {title}  |  句柄: {hwnd}  |  "
                f"位置: ({rect[0]}, {rect[1]})  大小: {rect[2] - rect[0]} x {rect[3] - rect[1]}"
            )
            self._log(f"检测到微信窗口: {title}")
        else:
            self.hwnd = None
            self.window_info_var.set("❌ 未检测到微信窗口，请先打开微信")
            self._log("未检测到微信主窗口 (WeChatMainWndForPC)")

    def _bring_to_front(self):
        if not self.hwnd:
            return
        try:
            if win32gui.IsIconic(self.hwnd):
                win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.hwnd)
            time.sleep(0.3)
        except Exception:
            pass

    # ---------- 聊天区域检测 ----------
    def _auto_detect_area(self):
        if not self.hwnd:
            messagebox.showwarning("提示", "请先检测到微信窗口")
            return

        self._bring_to_front()

        area = None

        # 策略 1: UI Automation
        if HAS_UIA:
            self._log("尝试 UI Automation 识别聊天区域...")
            area = self._detect_area_via_uia()
            if area:
                self._log(f"✅ UI Automation 识别成功: {area}")
                self.chat_area = area
                self._update_area_display()
                return

        # 策略 2: 启发式估算
        self._log("使用启发式估算聊天区域...")
        area = self._detect_area_heuristic()
        if area:
            self._log(f"✅ 启发式估算: {area}")
            self._log("提示: 如需精确，请点击 '手动校准区域'")
            self.chat_area = area
            self._update_area_display()
        else:
            messagebox.showerror("错误", "无法确定聊天区域，请使用手动校准")

    def _detect_area_via_uia(self):
        try:
            win = auto.WindowControl(searchDepth=1, ClassName=WECHAT_CLASS)
            if not win.Exists(3, 0.5):
                self._log("UIA: 找不到微信窗口")
                return None

            win.SetActive()
            win.SetTopmost(True)
            time.sleep(0.3)

            # 查找聊天消息列表
            chat_list = None
            candidates = [
                auto.ListControl(Name="消息", searchDepth=5),
                auto.ListControl(AutomationId="ChatContent", searchDepth=5),
                auto.ListControl(Name="聊天内容", searchDepth=5),
                auto.ListControl(searchDepth=5),
            ]
            for candidate in candidates:
                try:
                    if candidate.Exists(1, 0.3):
                        rect = candidate.BoundingRectangle
                        if rect.width() > 100 and rect.height() > 100:
                            chat_list = candidate
                            self._log(
                                f"UIA 找到列表控件: Name='{candidate.Name}' "
                                f"Rect=({rect.left},{rect.top},{rect.right},{rect.bottom})"
                            )
                            break
                except Exception:
                    continue

            if chat_list is None:
                # 兜底：找所有 ListControl，取最大的
                self._log("UIA: 尝试枚举所有列表控件...")
                try:
                    lists = win.GetChildren()
                    best = None
                    best_area = 0
                    for child in lists:
                        try:
                            if child.ControlTypeName == "ListControl":
                                r = child.BoundingRectangle
                                a = r.width() * r.height()
                                if a > best_area and r.width() > 100:
                                    best = child
                                    best_area = a
                        except Exception:
                            continue
                    if best:
                        rect = best.BoundingRectangle
                        self._log(
                            f"UIA 兜底: 取最大列表控件 "
                            f"({rect.width()}x{rect.height()})"
                        )
                        return (rect.left, rect.top, rect.right, rect.bottom)
                except Exception:
                    pass

                self._log("UIA: 未找到列表控件")
                return None

            rect = chat_list.BoundingRectangle
            return (rect.left, rect.top, rect.right, rect.bottom)

        except Exception as e:
            self._log(f"UIA 异常: {e}")
            return None

    def _detect_area_heuristic(self):
        if not self.hwnd:
            return None
        rect = win32gui.GetWindowRect(self.hwnd)
        left, top, right, bottom = rect

        width = right - left
        height = bottom - top

        # 微信窗口必须有最小尺寸
        if width < 300 or height < 200:
            self._log(f"窗口太小 ({width}x{height})，可能未最大化")
            return None

        area_left = left + MARGIN_SIDEBAR
        area_top = top + MARGIN_TOPBAR
        area_right = right - MARGIN_RIGHT
        area_bottom = bottom - MARGIN_INPUTBAR

        if area_right - area_left < 100 or area_bottom - area_top < 100:
            return None

        return (area_left, area_top, area_right, area_bottom)

    def _manual_calibrate(self):
        if self.hwnd:
            self._bring_to_front()
            time.sleep(0.2)

        self.root.withdraw()
        CalibrationOverlay(on_complete=self._on_calibration_done)

    def _on_calibration_done(self, result):
        self.root.deiconify()
        if result:
            self.chat_area = result
            self._update_area_display()
            self._log(f"✅ 手动校准区域: {result}")
        else:
            self._log("取消校准")

    def _update_area_display(self):
        if self.chat_area:
            x1, y1, x2, y2 = self.chat_area
            w, h = x2 - x1, y2 - y1
            self.area_var.set(
                f"({x1}, {y1}, {x2}, {y2})  "
                f"尺寸: {w} x {h}  px"
            )
        else:
            self.area_var.set("(未设置)")

    # ---------- 截图流程 ----------
    def _start_capture(self):
        if not self.hwnd:
            messagebox.showerror("错误", "请先检测到微信窗口")
            return
        if not self.chat_area:
            messagebox.showerror("错误", "请先设置聊天区域（自动识别或手动校准）")
            return

        output_dir = self.output_dir_var.get().strip()
        if not output_dir:
            messagebox.showerror("错误", "请设置输出目录")
            return

        self.is_capturing = True
        self.stop_flag = False
        self.start_btn.config(state=tk.DISABLED, text="截图中...")
        self.stop_btn.config(state=tk.NORMAL)

        self.capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True,
        )
        self.capture_thread.start()

    def _stop_capture(self):
        if self.is_capturing:
            self.stop_flag = True
            self._log("收到停止信号，正在停止...")

    def _capture_loop(self):
        output_dir = self.output_dir_var.get().strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join(output_dir, timestamp)
        os.makedirs(session_dir, exist_ok=True)

        mode = self.mode_var.get()
        max_pages = self.max_pages_var.get()
        delay = self.delay_var.get()
        scroll_mode = self.scroll_mode_var.get()

        self._log(f"输出目录: {session_dir}")
        self._log(f"模式: {'连续' if mode == 'continuous' else f'固定 {max_pages} 页'}")
        self._log(f"翻页延迟: {delay}s  翻页方式: {scroll_mode}")

        self._bring_to_front()
        time.sleep(0.2)

        page = 0
        last_img = None

        try:
            while not self.stop_flag:
                if mode == "fixed" and page >= max_pages:
                    self._log(f"已达到固定页数 {max_pages}，停止")
                    break

                # 1. 截图
                try:
                    img = ImageGrab.grab(bbox=self.chat_area)
                except Exception as e:
                    self._log(f"截图失败: {e}")
                    break

                # 检测是否和上一页完全相同（可能已到底部）
                if last_img is not None:
                    if self._images_identical(img, last_img):
                        self._log("⚠️ 截图与上一页完全相同，可能已到聊天底部，自动停止")
                        break

                # 2. 保存
                page += 1
                filename = f"page_{page:04d}.png"
                filepath = os.path.join(session_dir, filename)
                img.save(filepath, "PNG")
                last_img = img

                self._log(f"📸 第 {page} 页: {filename}  ({img.size[0]}x{img.size[1]})")
                self._update_status(f"已截图 {page} 页")

                # 3. 翻页
                if not self.stop_flag:
                    self._scroll_page(scroll_mode)
                    time.sleep(delay)

        except Exception as e:
            self._log(f"出错: {e}")

        finally:
            self.is_capturing = False
            self.root.after(0, lambda: self.start_btn.config(
                state=tk.NORMAL, text="▶ 开始截图",
            ))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            self._log(f"完成！共截图 {page} 页，保存至: {session_dir}")
            self._update_status(f"完成，共 {page} 页")

    def _scroll_page(self, mode):
        if not self.chat_area:
            return
        x1, y1, x2, y2 = self.chat_area
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2

        if mode == "pagedown":
            pyautogui.click(cx, cy)
            time.sleep(0.1)
            pyautogui.press("pagedown")
        elif mode == "wheel_down":
            pyautogui.moveTo(cx, cy)
            pyautogui.scroll(-3)
        elif mode == "wheel_up":
            pyautogui.moveTo(cx, cy)
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


# ==================== 入口 ====================
if __name__ == "__main__":
    app = WeChatChatCaptureApp()
    app.run()
