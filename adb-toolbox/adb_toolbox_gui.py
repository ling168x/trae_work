import queue
import re
import shlex
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from time import perf_counter
from tkinter import filedialog, ttk

from adb_toolbox import Device, list_devices

ADB_COMMAND_DOCS: dict[str, dict[str, str]] = {
    "devices": {
        "category": "设备管理",
        "desc": "查看当前连接的设备列表与状态。",
        "usage": "devices [-l]",
        "example": "adb devices -l",
        "tips": "状态为 device 才可正常执行大多数命令。",
    },
    "reboot": {
        "category": "设备管理",
        "desc": "重启设备。",
        "usage": "reboot",
        "example": "adb reboot",
        "tips": "也可配合 reboot bootloader/recovery。",
    },
    "install": {
        "category": "应用管理",
        "desc": "安装 APK 到设备。",
        "usage": "install [-r] [-d] [-t] <apk>",
        "example": "adb install -r app.apk",
        "tips": "-r 表示覆盖安装保留数据。",
    },
    "uninstall": {
        "category": "应用管理",
        "desc": "卸载应用包。",
        "usage": "uninstall [-k] <package>",
        "example": "adb uninstall com.demo.app",
        "tips": "-k 可保留应用数据与缓存目录。",
    },
    "shell": {
        "category": "设备管理",
        "desc": "在设备端执行 shell 命令。",
        "usage": "shell <cmd>",
        "example": "adb shell getprop ro.product.model",
        "tips": "可执行 pm/am/ls/cat/top 等系统命令。",
    },
    "push": {
        "category": "文件传输",
        "desc": "把本地文件推送到设备。",
        "usage": "push <local> <remote>",
        "example": "adb push a.txt /sdcard/a.txt",
        "tips": "目标目录需有写入权限。",
    },
    "pull": {
        "category": "文件传输",
        "desc": "把设备文件拉取到本地。",
        "usage": "pull <remote> [local]",
        "example": "adb pull /sdcard/a.txt .",
        "tips": "用于导出日志、截图、数据库等文件。",
    },
    "sync": {
        "category": "文件传输",
        "desc": "同步分区文件（开发场景常用）。",
        "usage": "sync [partition]",
        "example": "adb sync data",
        "tips": "多用于系统开发，不常用于普通应用调试。",
    },
    "logcat": {
        "category": "调试日志",
        "desc": "查看设备日志输出。",
        "usage": "logcat [filter]",
        "example": "adb logcat MyTag:D *:S",
        "tips": "可通过标签和优先级过滤。",
    },
    "bugreport": {
        "category": "调试日志",
        "desc": "导出系统诊断包。",
        "usage": "bugreport [path]",
        "example": "adb bugreport report.zip",
        "tips": "适合问题上报和系统级排查。",
    },
    "jdwp": {
        "category": "调试日志",
        "desc": "列出可调试进程的 JDWP PID。",
        "usage": "jdwp",
        "example": "adb jdwp",
        "tips": "常用于 Java 调试链路。",
    },
    "forward": {
        "category": "网络调试",
        "desc": "端口转发（主机 -> 设备）。",
        "usage": "forward tcp:<local> tcp:<remote>",
        "example": "adb forward tcp:8700 tcp:8700",
        "tips": "常用于本地工具连接设备服务。",
    },
    "reverse": {
        "category": "网络调试",
        "desc": "端口反向转发（设备 -> 主机）。",
        "usage": "reverse tcp:<remote> tcp:<local>",
        "example": "adb reverse tcp:8081 tcp:8081",
        "tips": "React Native/本地调试服务常用。",
    },
    "tcpip": {
        "category": "网络调试",
        "desc": "切换到 TCP/IP 调试模式。",
        "usage": "tcpip <port>",
        "example": "adb tcpip 5555",
        "tips": "通常先 USB 连接执行，再走 adb connect。",
    },
    "connect": {
        "category": "网络调试",
        "desc": "连接网络设备。",
        "usage": "connect <host:port>",
        "example": "adb connect 192.168.1.8:5555",
        "tips": "确保手机与电脑在同一网络。",
    },
    "disconnect": {
        "category": "网络调试",
        "desc": "断开网络设备连接。",
        "usage": "disconnect [host:port]",
        "example": "adb disconnect 192.168.1.8:5555",
        "tips": "不带参数时断开全部网络连接。",
    },
    "start-server": {
        "category": "设备管理",
        "desc": "启动 adb 后台服务。",
        "usage": "start-server",
        "example": "adb start-server",
        "tips": "一般会自动启动，手动排障时常用。",
    },
    "kill-server": {
        "category": "设备管理",
        "desc": "停止 adb 后台服务。",
        "usage": "kill-server",
        "example": "adb kill-server",
        "tips": "设备识别异常时可先 kill 再 start。",
    },
    "wait-for-device": {
        "category": "设备管理",
        "desc": "阻塞等待设备进入可用状态。",
        "usage": "wait-for-device",
        "example": "adb wait-for-device",
        "tips": "脚本中常用于确保设备就绪后再执行后续命令。",
    },
    "get-state": {
        "category": "设备管理",
        "desc": "获取设备连接状态。",
        "usage": "get-state",
        "example": "adb get-state",
        "tips": "常见返回有 device/offline/unknown。",
    },
    "get-serialno": {
        "category": "设备管理",
        "desc": "获取当前目标设备序列号。",
        "usage": "get-serialno",
        "example": "adb get-serialno",
        "tips": "用于脚本中确认目标设备。",
    },
    "root": {
        "category": "设备管理",
        "desc": "重启 adbd 为 root 模式。",
        "usage": "root",
        "example": "adb root",
        "tips": "多数量产机默认不支持 root adbd。",
    },
    "unroot": {
        "category": "设备管理",
        "desc": "退出 root adbd，恢复普通模式。",
        "usage": "unroot",
        "example": "adb unroot",
        "tips": "与 root 配套使用。",
    },
    "remount": {
        "category": "设备管理",
        "desc": "重新挂载分区为可写。",
        "usage": "remount",
        "example": "adb remount",
        "tips": "常用于系统开发修改分区内容。",
    },
    "am": {
        "category": "应用管理",
        "desc": "Activity Manager 命令入口。",
        "usage": "shell am <subcommand>",
        "example": "adb shell am start -n com.demo/.MainActivity",
        "tips": "可用于启动 Activity、发广播、启动 Service。",
    },
    "pm": {
        "category": "应用管理",
        "desc": "Package Manager 命令入口。",
        "usage": "shell pm <subcommand>",
        "example": "adb shell pm list packages",
        "tips": "可用于列包、禁用启用、clear 数据等。",
    },
    "sideload": {
        "category": "应用管理",
        "desc": "在 Recovery 模式下侧载包文件。",
        "usage": "sideload <file>",
        "example": "adb sideload ota.zip",
        "tips": "常见于 OTA/Recovery 升级流程。",
    },
    "backup": {
        "category": "应用管理",
        "desc": "执行应用数据备份（旧机制）。",
        "usage": "backup [options] <packages>",
        "example": "adb backup -apk com.demo.app",
        "tips": "新系统上能力受限，很多场景已不推荐。",
    },
    "restore": {
        "category": "应用管理",
        "desc": "恢复 adb backup 导出的备份。",
        "usage": "restore <file>",
        "example": "adb restore backup.ab",
        "tips": "依赖目标设备是否支持备份恢复。",
    },
    "exec-out": {
        "category": "调试日志",
        "desc": "执行命令并仅输出 stdout（适合二进制）。",
        "usage": "exec-out <cmd>",
        "example": "adb exec-out screencap -p > shot.png",
        "tips": "截图导出时比 shell 更稳定。",
    },
    "emu": {
        "category": "网络调试",
        "desc": "向模拟器控制台发送命令。",
        "usage": "emu <command>",
        "example": "adb emu avd name",
        "tips": "仅对 Android Emulator 生效。",
    },
}

INSTALL_FLAG_DOCS: dict[str, str] = {
    "-r": "覆盖安装（保留应用数据）。",
    "-d": "允许降级安装（版本号更低时）。",
    "-t": "允许安装测试包（testOnly）。",
    "-g": "安装后自动授予运行时权限。",
    "--instant": "安装为 Instant App（设备支持时）。",
    "--no-streaming": "关闭流式安装，先完整传输再安装。",
    "--streaming": "启用流式安装（设备支持时）。",
    "--abi arm64-v8a": "指定 ABI 安装（示例 arm64-v8a）。",
    "--user 0": "安装到指定用户（示例主用户 0）。",
}

INSTALL_FLAG_GROUPS: dict[str, list[str]] = {
    "通用安装": ["-r", "-d", "-t", "-g"],
    "高级安装": ["--instant", "--streaming", "--no-streaming", "--abi arm64-v8a", "--user 0"],
}

LOGCAT_FLAG_DOCS: dict[str, str] = {
    "-v brief": "简要格式输出。",
    "-v time": "带本地时间戳输出。",
    "-v threadtime": "带进程/线程/时间（常用）。",
    "-v long": "长格式输出，字段更完整。",
    "-b main": "查看 main 缓冲区。",
    "-b system": "查看 system 缓冲区。",
    "-b crash": "查看 crash 缓冲区。",
    "-b all": "查看全部缓冲区。",
    "-d": "导出并退出，不持续跟踪。",
    "-c": "清空日志缓冲区。",
    "-s": "静默模式，需配合 Tag 过滤。",
    "*:V": "显示所有 Verbose 级别及以上日志。",
    "*:D": "显示 Debug 级别及以上日志。",
    "*:I": "显示 Info 级别及以上日志。",
    "*:W": "显示 Warning 级别及以上日志。",
    "*:E": "显示 Error 级别及以上日志。",
    "*:S": "关闭所有日志（常与特定 Tag 组合）。",
    "ActivityManager:I *:S": "仅输出 ActivityManager 的 Info+ 日志。",
}

LOGCAT_FLAG_GROUPS: dict[str, list[str]] = {
    "输出格式": ["-v brief", "-v time", "-v threadtime", "-v long"],
    "缓冲区": ["-b main", "-b system", "-b crash", "-b all"],
    "控制动作": ["-d", "-c", "-s"],
    "全局级别过滤": ["*:V", "*:D", "*:I", "*:W", "*:E", "*:S"],
    "示例过滤": ["ActivityManager:I *:S"],
}


class AdbToolboxGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ADB Toolbox")
        self.root.geometry("920x620")

        self.devices: list[Device] = []
        self.device_var = tk.StringVar()
        self.apk_path_var = tk.StringVar()
        self.install_flags_var = tk.StringVar(value="-r")
        self.install_category_var = tk.StringVar(value="通用安装")
        self.install_option_var = tk.StringVar(value="-r")
        self.install_option_desc_var = tk.StringVar(value="")
        self.custom_cmd_var = tk.StringVar(value="shell getprop ro.product.model")
        self.cmd_filter_var = tk.StringVar()
        self.cmd_category_var = tk.StringVar(value="全部")
        self.selected_cmd_var = tk.StringVar()
        self.selected_cmd_args_var = tk.StringVar()
        self.cmd_doc_var = tk.StringVar(value="请选择左侧命令以查看中文说明。")
        self.selected_cmd_example_var = tk.StringVar(value="")
        self.logcat_filter_var = tk.StringVar(value="*:I")
        self.logcat_category_var = tk.StringVar(value="输出格式")
        self.logcat_option_var = tk.StringVar(value="-v threadtime")
        self.logcat_option_desc_var = tk.StringVar(value="")
        self.package_var = tk.StringVar()
        self.remote_path_var = tk.StringVar(value="/sdcard/Download/")
        self.status_var = tk.StringVar(value="就绪")
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.logcat_process: subprocess.Popen | None = None
        self.logcat_save_fp = None
        self.adb_commands: list[str] = []
        self.filtered_adb_commands: list[str] = []
        self.task_history: list[tuple[str, str, str, str, str]] = []

        self._build_ui()
        self._refresh_install_options()
        self._refresh_logcat_options()
        self._update_install_option_desc()
        self._update_logcat_option_desc()
        self._refresh_devices()
        self._load_adb_commands()
        self._drain_log_queue()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        vertical_pane = ttk.Panedwindow(main, orient=tk.VERTICAL)
        vertical_pane.pack(fill=tk.BOTH, expand=True)

        top_container = ttk.Frame(vertical_pane)
        bottom_container = ttk.Frame(vertical_pane)
        vertical_pane.add(top_container, weight=3)
        vertical_pane.add(bottom_container, weight=2)

        device_row = ttk.Frame(top_container)
        device_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(device_row, text="设备:").pack(side=tk.LEFT)
        self.device_combo = ttk.Combobox(device_row, textvariable=self.device_var, state="readonly", width=55)
        self.device_combo.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)
        ttk.Button(device_row, text="刷新设备", command=self._refresh_devices).pack(side=tk.LEFT)

        install_frame = ttk.LabelFrame(top_container, text="安装 APK", padding=10)
        install_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(install_frame, text="APK 路径:").grid(row=0, column=0, sticky="w")
        ttk.Entry(install_frame, textvariable=self.apk_path_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(install_frame, text="选择文件", command=self._pick_apk).grid(row=0, column=2)
        ttk.Label(install_frame, text="安装参数:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(install_frame, textvariable=self.install_flags_var).grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(install_frame, text="执行安装", command=self._run_install).grid(row=1, column=2, pady=(8, 0))
        ttk.Label(install_frame, text="参数分类:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.install_category_combo = ttk.Combobox(
            install_frame,
            textvariable=self.install_category_var,
            state="readonly",
            values=list(INSTALL_FLAG_GROUPS.keys()),
            width=16,
        )
        self.install_category_combo.grid(row=2, column=1, sticky="w", padx=8, pady=(8, 0))
        self.install_category_combo.bind("<<ComboboxSelected>>", lambda *_: self._refresh_install_options())
        ttk.Label(install_frame, text="参数下拉:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.install_option_combo = ttk.Combobox(
            install_frame,
            textvariable=self.install_option_var,
            state="readonly",
            values=[],
        )
        self.install_option_combo.grid(row=3, column=1, sticky="ew", padx=8, pady=(8, 0))
        self.install_option_combo.bind("<<ComboboxSelected>>", lambda *_: self._update_install_option_desc())
        install_btn_row = ttk.Frame(install_frame)
        install_btn_row.grid(row=3, column=2, sticky="e", pady=(8, 0))
        ttk.Button(install_btn_row, text="追加", command=self._append_install_option).pack(side=tk.LEFT)
        ttk.Button(install_btn_row, text="清空", command=self._clear_install_options).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(install_frame, textvariable=self.install_option_desc_var).grid(
            row=4, column=1, columnspan=2, sticky="w", padx=8, pady=(4, 0)
        )
        install_frame.columnconfigure(1, weight=1)

        custom_frame = ttk.LabelFrame(top_container, text="自定义 ADB 命令", padding=10)
        custom_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(custom_frame, text="命令参数:").grid(row=0, column=0, sticky="w")
        ttk.Entry(custom_frame, textvariable=self.custom_cmd_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(custom_frame, text="执行命令", command=self._run_custom_command).grid(row=0, column=2)
        custom_frame.columnconfigure(1, weight=1)

        all_cmd_frame = ttk.LabelFrame(top_container, text="ADB 命令大全", padding=10)
        all_cmd_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(all_cmd_frame, text="搜索:").grid(row=0, column=0, sticky="w")
        ttk.Entry(all_cmd_frame, textvariable=self.cmd_filter_var).grid(row=0, column=1, sticky="ew", padx=8)
        self.cmd_filter_var.trace_add("write", lambda *_: self._apply_command_filter())
        ttk.Label(all_cmd_frame, text="分类:").grid(row=0, column=2, sticky="e", padx=(8, 4))
        self.cmd_category_combo = ttk.Combobox(
            all_cmd_frame,
            textvariable=self.cmd_category_var,
            state="readonly",
            width=14,
            values=["全部", "设备管理", "应用管理", "文件传输", "调试日志", "网络调试", "其它"],
        )
        self.cmd_category_combo.grid(row=0, column=3, sticky="w")
        self.cmd_category_combo.bind("<<ComboboxSelected>>", lambda *_: self._apply_command_filter())
        ttk.Button(all_cmd_frame, text="刷新命令列表", command=self._load_adb_commands).grid(row=0, column=4, padx=(8, 0))
        cmd_list_row = ttk.Frame(all_cmd_frame)
        cmd_list_row.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(8, 0))
        self.cmd_listbox = tk.Listbox(cmd_list_row, height=6, exportselection=False)
        self.cmd_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.cmd_listbox.bind("<<ListboxSelect>>", self._on_command_selected)
        cmd_scroll = ttk.Scrollbar(cmd_list_row, orient=tk.VERTICAL, command=self.cmd_listbox.yview)
        cmd_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.cmd_listbox.config(yscrollcommand=cmd_scroll.set)
        action_row = ttk.Frame(all_cmd_frame)
        action_row.grid(row=2, column=0, columnspan=5, sticky="ew", pady=(8, 0))
        ttk.Label(action_row, text="已选命令:").pack(side=tk.LEFT)
        ttk.Entry(action_row, textvariable=self.selected_cmd_var, width=26).pack(side=tk.LEFT, padx=(8, 8))
        ttk.Label(action_row, text="参数:").pack(side=tk.LEFT)
        ttk.Entry(action_row, textvariable=self.selected_cmd_args_var).pack(side=tk.LEFT, padx=(8, 8), fill=tk.X, expand=True)
        ttk.Button(action_row, text="执行选中命令", command=self._run_selected_command).pack(side=tk.LEFT)
        doc_frame = ttk.Frame(all_cmd_frame)
        doc_frame.grid(row=3, column=0, columnspan=5, sticky="ew", pady=(8, 0))
        ttk.Label(doc_frame, text="命令说明:").pack(side=tk.LEFT, anchor="n")
        self.cmd_doc_text = tk.Text(doc_frame, height=6, wrap="word")
        self.cmd_doc_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        self.cmd_doc_text.insert("1.0", self.cmd_doc_var.get())
        self.cmd_doc_text.configure(state=tk.DISABLED)
        doc_actions = ttk.Frame(all_cmd_frame)
        doc_actions.grid(row=4, column=0, columnspan=5, sticky="e", pady=(6, 0))
        ttk.Button(doc_actions, text="填充示例到参数", command=self._fill_example_args).pack(side=tk.LEFT)
        ttk.Button(doc_actions, text="填充并执行", command=self._fill_example_and_run).pack(side=tk.LEFT, padx=(8, 0))
        all_cmd_frame.columnconfigure(1, weight=1)

        quick_frame = ttk.LabelFrame(top_container, text="常用命令", padding=10)
        quick_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(quick_frame, text="包名:").grid(row=0, column=0, sticky="w")
        ttk.Entry(quick_frame, textvariable=self.package_var, width=28).grid(row=0, column=1, sticky="w", padx=(8, 12))
        ttk.Button(quick_frame, text="重启设备", command=self._quick_reboot).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(quick_frame, text="清空应用数据", command=self._quick_clear_app_data).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(quick_frame, text="启动应用", command=self._quick_start_app).grid(row=0, column=4)
        ttk.Label(quick_frame, text="远程路径:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(quick_frame, textvariable=self.remote_path_var).grid(row=1, column=1, sticky="ew", padx=(8, 12), pady=(8, 0))
        ttk.Button(quick_frame, text="拉取文件", command=self._quick_pull_file).grid(row=1, column=2, pady=(8, 0), padx=(0, 8))
        ttk.Button(quick_frame, text="截图并保存到本地", command=self._quick_screencap_to_local).grid(row=1, column=3, columnspan=2, pady=(8, 0), sticky="w")
        quick_frame.columnconfigure(1, weight=1)

        logcat_frame = ttk.LabelFrame(bottom_container, text="Logcat / 控制台输出", padding=10)
        logcat_frame.pack(fill=tk.BOTH, expand=True)
        action_row = ttk.Frame(logcat_frame)
        action_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(action_row, text="过滤参数:").grid(row=0, column=0, sticky="w")
        ttk.Entry(action_row, textvariable=self.logcat_filter_var).grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(action_row, text="启动 Logcat", command=self._start_logcat).grid(row=0, column=2)
        ttk.Button(action_row, text="停止 Logcat", command=self._stop_logcat).grid(row=0, column=3, padx=(8, 0))
        ttk.Button(action_row, text="保存输出到文件", command=self._save_output_to_file).grid(row=0, column=4, padx=(8, 0))
        ttk.Button(action_row, text="清空输出", command=self._clear_output).grid(row=0, column=5, padx=(8, 0))
        ttk.Label(action_row, text="参数分类:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.logcat_category_combo = ttk.Combobox(
            action_row,
            textvariable=self.logcat_category_var,
            state="readonly",
            values=list(LOGCAT_FLAG_GROUPS.keys()),
            width=16,
        )
        self.logcat_category_combo.grid(row=1, column=1, sticky="w", padx=8, pady=(6, 0))
        self.logcat_category_combo.bind("<<ComboboxSelected>>", lambda *_: self._refresh_logcat_options())
        ttk.Label(action_row, text="参数下拉:").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.logcat_option_combo = ttk.Combobox(
            action_row,
            textvariable=self.logcat_option_var,
            state="readonly",
            values=[],
        )
        self.logcat_option_combo.grid(row=2, column=1, sticky="ew", padx=8, pady=(6, 0))
        self.logcat_option_combo.bind("<<ComboboxSelected>>", lambda *_: self._update_logcat_option_desc())
        logcat_btn_row = ttk.Frame(action_row)
        logcat_btn_row.grid(row=2, column=2, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(logcat_btn_row, text="追加", command=self._append_logcat_option).pack(side=tk.LEFT)
        ttk.Button(logcat_btn_row, text="清空", command=self._clear_logcat_options).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Label(action_row, textvariable=self.logcat_option_desc_var).grid(
            row=2, column=4, columnspan=2, sticky="w", padx=(8, 0), pady=(6, 0)
        )
        action_row.columnconfigure(1, weight=1)

        output_wrap = ttk.Frame(logcat_frame)
        output_wrap.pack(fill=tk.BOTH, expand=True)
        self.output_text = tk.Text(output_wrap, wrap="none", height=12)
        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        output_scroll_y = ttk.Scrollbar(output_wrap, orient=tk.VERTICAL, command=self.output_text.yview)
        output_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.configure(yscrollcommand=output_scroll_y.set)
        self.output_text.configure(state=tk.DISABLED)

        task_frame = ttk.LabelFrame(bottom_container, text="最近任务（最多 10 条）", padding=8)
        task_frame.pack(fill=tk.X, pady=(8, 0))
        columns = ("time", "task", "status", "code", "duration")
        self.task_tree = ttk.Treeview(task_frame, columns=columns, show="headings", height=6)
        self.task_tree.heading("time", text="时间")
        self.task_tree.heading("task", text="任务")
        self.task_tree.heading("status", text="状态")
        self.task_tree.heading("code", text="退出码")
        self.task_tree.heading("duration", text="耗时(s)")
        self.task_tree.column("time", width=90, anchor=tk.W)
        self.task_tree.column("task", width=240, anchor=tk.W)
        self.task_tree.column("status", width=100, anchor=tk.W)
        self.task_tree.column("code", width=80, anchor=tk.CENTER)
        self.task_tree.column("duration", width=90, anchor=tk.E)
        self.task_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        task_scroll = ttk.Scrollbar(task_frame, orient=tk.VERTICAL, command=self.task_tree.yview)
        task_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.task_tree.configure(yscrollcommand=task_scroll.set)

        status_row = ttk.Frame(bottom_container)
        status_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(status_row, text="状态:").pack(side=tk.LEFT)
        ttk.Label(status_row, textvariable=self.status_var).pack(side=tk.LEFT, padx=(8, 0))

    def _append_output(self, text: str) -> None:
        self.output_text.configure(state=tk.NORMAL)
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.configure(state=tk.DISABLED)

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _stamp(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _record_task(self, task: str, status: str, code: int | str, duration_sec: float) -> None:
        row = (self._stamp(), task, status, str(code), f"{duration_sec:.2f}")
        self.task_history.insert(0, row)
        self.task_history = self.task_history[:10]
        self.task_tree.delete(*self.task_tree.get_children())
        for item in self.task_history:
            self.task_tree.insert("", tk.END, values=item)

    def _append_tokens(self, current: str, addon: str) -> str:
        current_tokens = shlex.split(current) if current.strip() else []
        addon_tokens = shlex.split(addon) if addon.strip() else []
        return " ".join([*current_tokens, *addon_tokens]).strip()

    def _refresh_install_options(self) -> None:
        category = self.install_category_var.get().strip()
        values = INSTALL_FLAG_GROUPS.get(category, [])
        self.install_option_combo["values"] = values
        if values:
            self.install_option_var.set(values[0])
        else:
            self.install_option_var.set("")
        self._update_install_option_desc()

    def _update_install_option_desc(self) -> None:
        self.install_option_desc_var.set(INSTALL_FLAG_DOCS.get(self.install_option_var.get().strip(), ""))

    def _append_install_option(self) -> None:
        opt = self.install_option_var.get().strip()
        if not opt:
            return
        self.install_flags_var.set(self._append_tokens(self.install_flags_var.get(), opt))
        self._append_output(f"[Info] 已追加安装参数: {opt}\n")

    def _clear_install_options(self) -> None:
        self.install_flags_var.set("")
        self._append_output("[Info] 已清空安装参数\n")

    def _refresh_logcat_options(self) -> None:
        category = self.logcat_category_var.get().strip()
        values = LOGCAT_FLAG_GROUPS.get(category, [])
        self.logcat_option_combo["values"] = values
        if values:
            self.logcat_option_var.set(values[0])
        else:
            self.logcat_option_var.set("")
        self._update_logcat_option_desc()

    def _update_logcat_option_desc(self) -> None:
        self.logcat_option_desc_var.set(LOGCAT_FLAG_DOCS.get(self.logcat_option_var.get().strip(), ""))

    def _append_logcat_option(self) -> None:
        opt = self.logcat_option_var.get().strip()
        if not opt:
            return
        self.logcat_filter_var.set(self._append_tokens(self.logcat_filter_var.get(), opt))
        self._append_output(f"[Info] 已追加 logcat 参数: {opt}\n")

    def _clear_logcat_options(self) -> None:
        self.logcat_filter_var.set("")
        self._append_output("[Info] 已清空 logcat 参数\n")

    def _drain_log_queue(self) -> None:
        while True:
            try:
                text = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_output(text)
        self.root.after(120, self._drain_log_queue)

    def _device_serial(self) -> str | None:
        chosen = self.device_var.get()
        if not chosen:
            self._append_output("[Error] 未选择设备\n")
            return None
        return chosen.split(" | ", 1)[0].strip()

    def _refresh_devices(self) -> None:
        try:
            self.devices = list_devices()
        except RuntimeError as err:
            self._append_output(f"[Error] {err}\n")
            return
        values = []
        for d in self.devices:
            details = f" | {d.details}" if d.details else ""
            values.append(f"{d.serial} | {d.state}{details}")
        self.device_combo["values"] = values
        if values:
            self.device_var.set(values[0])
            self._append_output(f"[Info] 已刷新设备，共 {len(values)} 台\n")
        else:
            self.device_var.set("")
            self._append_output("[Info] 当前无设备连接\n")

    def _pick_apk(self) -> None:
        selected = filedialog.askopenfilename(
            title="选择 APK",
            filetypes=[("APK files", "*.apk"), ("All files", "*.*")],
        )
        if selected:
            self.apk_path_var.set(selected)

    def _run_subprocess_async(self, cmd: list[str], title: str) -> None:
        def worker() -> None:
            started = perf_counter()
            self.root.after(0, self._set_status, f"{title} 运行中...")
            self.log_queue.put(f"\n[{self._stamp()}] [{title}] {shlex.join(cmd)}\n")
            proc = subprocess.run(cmd, capture_output=True, check=False)
            if proc.stdout:
                self.log_queue.put(self._decode_output(proc.stdout))
            if proc.stderr:
                self.log_queue.put(self._decode_output(proc.stderr))
            self.log_queue.put(f"[{self._stamp()}] [Exit] code={proc.returncode}\n")
            duration = perf_counter() - started
            if proc.returncode == 0:
                self.root.after(0, self._set_status, f"{title} 执行成功")
                self.root.after(0, self._record_task, title, "成功", proc.returncode, duration)
            else:
                self.root.after(0, self._set_status, f"{title} 执行失败 (code={proc.returncode})")
                self.root.after(0, self._record_task, title, "失败", proc.returncode, duration)

        threading.Thread(target=worker, daemon=True).start()

    def _decode_output(self, data: bytes) -> str:
        for encoding in ("utf-8", "gbk"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        return data.decode("utf-8", errors="replace")

    def _run_adb_help(self) -> str:
        proc = subprocess.run(["adb", "help"], capture_output=True, check=False)
        output = b""
        if proc.stdout:
            output += proc.stdout
        if proc.stderr:
            output += b"\n" + proc.stderr
        return self._decode_output(output)

    def _extract_adb_commands(self, help_text: str) -> list[str]:
        commands: set[str] = set()
        for raw_line in help_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("Android Debug Bridge") or line.startswith("global options"):
                continue
            match = re.match(r"^([a-z][a-z0-9_-]*)\b", line)
            if match:
                token = match.group(1)
                if token not in {"usage", "adb"}:
                    commands.add(token)
        if "shell" not in commands:
            commands.add("shell")
        return sorted(commands)

    def _load_adb_commands(self) -> None:
        try:
            help_text = self._run_adb_help()
        except OSError as err:
            self._append_output(f"[Error] 读取 adb help 失败: {err}\n")
            return
        commands = self._extract_adb_commands(help_text)
        if not commands:
            self._append_output("[Error] 未能从 adb help 解析出命令\n")
            return
        self.adb_commands = commands
        self._apply_command_filter()
        if self.filtered_adb_commands:
            self.selected_cmd_var.set(self.filtered_adb_commands[0])
            self._update_command_doc(self.filtered_adb_commands[0])
        self._append_output(f"[Info] 已加载 ADB 命令 {len(commands)} 个\n")

    def _apply_command_filter(self) -> None:
        key = self.cmd_filter_var.get().strip().lower()
        category = self.cmd_category_var.get().strip()
        self.cmd_listbox.delete(0, tk.END)
        candidate = list(self.adb_commands)
        if category and category != "全部":
            candidate = [c for c in candidate if self._command_category(c) == category]
        if key:
            candidate = [c for c in candidate if key in c.lower()]
        self.filtered_adb_commands = candidate
        for cmd in self.filtered_adb_commands:
            self.cmd_listbox.insert(tk.END, cmd)

    def _command_category(self, cmd: str) -> str:
        if cmd in ADB_COMMAND_DOCS:
            return ADB_COMMAND_DOCS[cmd].get("category", "其它")
        return "其它"

    def _on_command_selected(self, _event: tk.Event) -> None:
        selected = self.cmd_listbox.curselection()
        if not selected:
            return
        cmd = self.filtered_adb_commands[selected[0]]
        self.selected_cmd_var.set(cmd)
        self._update_command_doc(cmd)

    def _update_command_doc(self, cmd: str) -> None:
        if cmd in ADB_COMMAND_DOCS:
            doc = ADB_COMMAND_DOCS[cmd]
            self.selected_cmd_example_var.set(doc.get("example", ""))
            text = (
                f"分类: {doc.get('category', '其它')}\n"
                f"作用: {doc.get('desc', '-')}\n"
                f"用法: {doc.get('usage', '-')}\n"
                f"示例: {doc.get('example', '-')}\n"
                f"提示: {doc.get('tips', '-')}"
            )
        else:
            self.selected_cmd_example_var.set(f"adb {cmd} --help")
            text = (
                f"分类: 其它\n"
                f"作用: `{cmd}` 是 ADB 子命令。\n"
                f"用法: {cmd} [args]\n"
                f"示例: adb {cmd} --help\n"
                f"提示: 可在“参数”输入框补充参数后执行。"
            )
        self.cmd_doc_var.set(text)
        self.cmd_doc_text.configure(state=tk.NORMAL)
        self.cmd_doc_text.delete("1.0", tk.END)
        self.cmd_doc_text.insert("1.0", text)
        self.cmd_doc_text.configure(state=tk.DISABLED)

    def _extract_args_from_example(self, cmd_name: str, example: str) -> str:
        if not example:
            return ""
        example = example.strip()
        prefix = "adb "
        if example.startswith(prefix):
            example = example[len(prefix):].strip()
        if example.startswith(cmd_name):
            return example[len(cmd_name):].strip()
        parts = shlex.split(example)
        if parts and parts[0] == cmd_name:
            return " ".join(parts[1:])
        return ""

    def _fill_example_args(self) -> None:
        cmd_name = self.selected_cmd_var.get().strip()
        if not cmd_name:
            self._append_output("[Error] 请先选择一个 ADB 命令\n")
            return
        example = self.selected_cmd_example_var.get().strip()
        args = self._extract_args_from_example(cmd_name, example)
        if not args:
            self._append_output("[Info] 示例中无可填充参数，请手动输入参数\n")
            return
        self.selected_cmd_args_var.set(args)
        self._append_output(f"[Info] 已填充示例参数: {args}\n")

    def _fill_example_and_run(self) -> None:
        self._fill_example_args()
        cmd_name = self.selected_cmd_var.get().strip()
        if not cmd_name:
            return
        self._run_selected_command()

    def _run_selected_command(self) -> None:
        serial = self._device_serial()
        if not serial:
            return
        cmd_name = self.selected_cmd_var.get().strip()
        if not cmd_name:
            self._append_output("[Error] 请先选择一个 ADB 命令\n")
            return
        extra = self.selected_cmd_args_var.get().strip()
        extra_args = shlex.split(extra) if extra else []
        cmd = ["adb", "-s", serial, cmd_name, *extra_args]
        self._run_subprocess_async(cmd, f"ADB {cmd_name}")

    def _run_common_adb(self, title: str, raw_args: list[str]) -> None:
        serial = self._device_serial()
        if not serial:
            return
        cmd = ["adb", "-s", serial, *raw_args]
        self._run_subprocess_async(cmd, title)

    def _run_install(self) -> None:
        serial = self._device_serial()
        if not serial:
            return
        apk_path = self.apk_path_var.get().strip()
        if not apk_path:
            self._append_output("[Error] 请先选择 APK 文件\n")
            return
        if not Path(apk_path).exists():
            self._append_output(f"[Error] APK 不存在: {apk_path}\n")
            return
        install_flags = shlex.split(self.install_flags_var.get().strip()) if self.install_flags_var.get().strip() else []
        cmd = ["adb", "-s", serial, "install", *install_flags, apk_path]
        self._run_subprocess_async(cmd, "Install")

    def _run_custom_command(self) -> None:
        serial = self._device_serial()
        if not serial:
            return
        raw = self.custom_cmd_var.get().strip()
        if not raw:
            self._append_output("[Error] 请输入命令参数\n")
            return
        cmd = ["adb", "-s", serial, *shlex.split(raw)]
        self._run_subprocess_async(cmd, "Exec")

    def _quick_reboot(self) -> None:
        self._run_common_adb("Quick Reboot", ["reboot"])

    def _quick_clear_app_data(self) -> None:
        package = self.package_var.get().strip()
        if not package:
            self._append_output("[Error] 请先填写包名\n")
            return
        self._run_common_adb("Quick Clear App Data", ["shell", "pm", "clear", package])

    def _quick_start_app(self) -> None:
        package = self.package_var.get().strip()
        if not package:
            self._append_output("[Error] 请先填写包名\n")
            return
        self._run_common_adb("Quick Start App", ["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"])

    def _quick_pull_file(self) -> None:
        remote = self.remote_path_var.get().strip()
        if not remote:
            self._append_output("[Error] 请先填写远程路径\n")
            return
        local = filedialog.asksaveasfilename(title="保存到本地", initialfile=Path(remote).name or "pulled_file")
        if not local:
            return
        self._run_common_adb("Quick Pull File", ["pull", remote, local])

    def _quick_screencap_to_local(self) -> None:
        local = filedialog.asksaveasfilename(
            title="保存截图到本地",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialfile="screenshot.png",
        )
        if not local:
            return
        serial = self._device_serial()
        if not serial:
            return
        cmd = ["adb", "-s", serial, "exec-out", "screencap", "-p"]

        def worker() -> None:
            started = perf_counter()
            self.log_queue.put(f"\n[Quick Screencap To Local] {shlex.join(cmd)} > {local}\n")
            proc = subprocess.run(cmd, capture_output=True, check=False)
            if proc.returncode == 0 and proc.stdout:
                try:
                    Path(local).write_bytes(proc.stdout)
                    self.log_queue.put(f"[Info] 截图已保存: {local}\n")
                    duration = perf_counter() - started
                    self.root.after(0, self._set_status, "Quick Screencap 执行成功")
                    self.root.after(0, self._record_task, "Quick Screencap To Local", "成功", 0, duration)
                except OSError as err:
                    self.log_queue.put(f"[Error] 保存截图失败: {err}\n")
                    duration = perf_counter() - started
                    self.root.after(0, self._set_status, "Quick Screencap 执行失败")
                    self.root.after(0, self._record_task, "Quick Screencap To Local", "失败", "write", duration)
            else:
                err = proc.stderr.decode(errors="ignore") if proc.stderr else ""
                self.log_queue.put(f"[Error] 截图失败，code={proc.returncode} {err}\n")
                duration = perf_counter() - started
                self.root.after(0, self._set_status, f"Quick Screencap 执行失败 (code={proc.returncode})")
                self.root.after(0, self._record_task, "Quick Screencap To Local", "失败", proc.returncode, duration)

        threading.Thread(target=worker, daemon=True).start()

    def _start_logcat(self) -> None:
        if self.logcat_process and self.logcat_process.poll() is None:
            self._append_output("[Info] Logcat 已在运行\n")
            return
        serial = self._device_serial()
        if not serial:
            return
        filters = self.logcat_filter_var.get().strip()
        logcat_args = shlex.split(filters) if filters else []
        cmd = ["adb", "-s", serial, "logcat", *logcat_args]
        self._append_output(f"\n[{self._stamp()}] [Logcat Start] {shlex.join(cmd)}\n")
        self._set_status("Logcat 运行中...")
        self._record_task("Logcat Start", "运行中", "-", 0.0)
        try:
            self.logcat_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
                bufsize=0,
            )
        except OSError as err:
            self._append_output(f"[Error] 启动 logcat 失败: {err}\n")
            self._set_status("Logcat 启动失败")
            self.logcat_process = None
            return

        def stream_worker() -> None:
            assert self.logcat_process is not None
            for line in self.logcat_process.stdout or []:
                decoded_line = self._decode_output(line)
                self.log_queue.put(decoded_line)
                if self.logcat_save_fp:
                    try:
                        self.logcat_save_fp.write(decoded_line)
                    except OSError as err:
                        self.log_queue.put(f"[Error] 写入日志文件失败: {err}\n")
                        self.logcat_save_fp = None
            code = self.logcat_process.poll()
            self.log_queue.put(f"[{self._stamp()}] [Logcat Exit] code={code}\n")
            self.root.after(0, self._set_status, "Logcat 已停止")
            self.root.after(0, self._record_task, "Logcat Stop", "完成", code if code is not None else "-", 0.0)

        threading.Thread(target=stream_worker, daemon=True).start()

    def _stop_logcat(self) -> None:
        if not self.logcat_process or self.logcat_process.poll() is not None:
            self._append_output("[Info] Logcat 未在运行\n")
            return
        self.logcat_process.terminate()
        self._append_output("[Info] 已发送停止信号给 Logcat\n")
        self._set_status("Logcat 正在停止...")
        if self.logcat_save_fp:
            self.logcat_save_fp.close()
            self.logcat_save_fp = None
            self._append_output("[Info] 已关闭日志保存文件\n")

    def _save_output_to_file(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="保存 logcat 输出",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="logcat.log",
        )
        if not file_path:
            return
        try:
            if self.logcat_save_fp:
                self.logcat_save_fp.close()
            self.logcat_save_fp = open(file_path, "a", encoding="utf-8")
        except OSError as err:
            self._append_output(f"[Error] 无法打开保存文件: {err}\n")
            self.logcat_save_fp = None
            return
        self._append_output(f"[Info] logcat 将追加保存到: {file_path}\n")

    def _clear_output(self) -> None:
        self.output_text.configure(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.configure(state=tk.DISABLED)

    def _on_close(self) -> None:
        self._stop_logcat()
        if self.logcat_save_fp:
            self.logcat_save_fp.close()
            self.logcat_save_fp = None
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AdbToolboxGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
