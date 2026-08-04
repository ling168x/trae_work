# adb-toolbox

一个 ADB 命令集合工具：支持设备选择，并自动将设备序列号注入到命令中（`adb -s <serial> ...`）。

## 功能

- 列出当前连接设备
- 多设备场景下交互选择设备
- 执行安装 APK
- 查看 logcat
- 执行自定义 adb 子命令

## 环境要求

- Python 3.10+
- 已安装 Android Platform Tools（可直接在命令行使用 `adb`）

## 使用方式

在项目目录下运行：

```bash
python adb_toolbox.py devices
```

## 图形界面版

启动 GUI：

```bash
python adb_toolbox_gui.py
```

GUI 支持：

- 设备下拉选择 + 刷新设备
- 选择 APK 并安装（自动注入 `-s <serial>`）
- 安装参数二级下拉（先选分类，再选参数；可一键追加并查看中文作用）
- 启动/停止 logcat，并在窗口中实时显示
- logcat 参数二级下拉（先选分类，再选参数；可一键追加并查看中文作用）
- logcat 一键保存到本地文件（持续追加）
- 执行自定义 adb 命令（自动注入 `-s <serial>`）
- ADB 命令大全（自动解析 `adb help`，支持搜索、选中并附加参数执行）
- 常用命令按钮（重启设备、清空应用数据、启动应用、拉取文件、截图到本地）

### 1) 安装 APK

自动选择设备（多设备时会弹出选择）：

```bash
python adb_toolbox.py install "C:\path\to\app.apk" --install-flag -r
```

指定设备序列号：

```bash
python adb_toolbox.py install "C:\path\to\app.apk" -d emulator-5554 --install-flag -r
```

### 2) 查看日志

```bash
python adb_toolbox.py logcat
```

附加 logcat 参数（例如过滤某个 tag）：

```bash
python adb_toolbox.py logcat -- MyTag:D *:S
```

### 3) 执行任意 adb 命令

例如查看设备属性：

```bash
python adb_toolbox.py exec -- shell getprop ro.product.model
```

例如截图：

```bash
python adb_toolbox.py exec -- shell screencap -p /sdcard/screen.png
```

## 说明

- `devices` 不需要指定设备。
- `install` / `logcat` / `exec` 如果不传 `-d`，会自动根据当前设备列表选择。
- 若只连接一台设备，会自动使用该设备，无需手动选择。

## 新增：Android/iOS 性能数据记录工具（Unity 优先）

已在仓库中新增 `perf_recorder` 采集主控模块，包含：

- 统一指标模型：`timestamp/device/app/metric/source/confidence`
- PC 主控会话：多采集器轮询、SQLite 落盘、实时终端看板
- Android 采集：ADB CPU/内存/温度/FPS 基础链路
- iOS 企业链路：`ideviceinfo/idevice_id` 桥接 + 指标分级
- Unity 探针：`unity_sdk/UnityPerfProbe.cs`（JSONL 帧数据输出）
- 报告导出：CSV/JSON/HTML
- 精度验证：`validate_accuracy.py`

### 快速开始

1) Android 录制（可选 Unity 探针）：

```bash
python perf_recorder_cli.py monitor --platform android --device-id <serial> --app-id <package> --duration 60 --live
```

2) iOS 录制（企业链路）：

```bash
python perf_recorder_cli.py monitor --platform ios --device-id <udid> --app-id <bundleId> --duration 60 --live
```

3) 导出数据：

```bash
python perf_recorder_cli.py export --db sessions/perf_metrics.db --format json --out sessions/metrics.json
python perf_recorder_cli.py export --db sessions/perf_metrics.db --format csv --out sessions/metrics.csv
```

4) 生成 HTML 报告：

```bash
python perf_recorder_cli.py report --db sessions/perf_metrics.db --out sessions/report.html
```

5) 验证 FPS 误差与丢点率：

```bash
python validate_accuracy.py --input sessions/metrics.json
```
