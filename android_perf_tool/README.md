# Android性能数据记录工具

类似PerfDog的Android性能数据记录工具，支持抓取游戏应用的帧率、CPU、内存等性能指标，并生成Excel和网页报告。

## 功能特性

- ✅ 帧率(FPS)采集
- ✅ CPU使用率采集
- ✅ 内存使用采集
- ✅ 电池电量采集
- ✅ GPU性能指标采集
- ✅ 生成Excel报告
- ✅ 生成网页报告（含图表）
- ✅ 图形化操作界面
- ✅ 实时数据展示
- ✅ 无时间限制记录

## 安装要求

- Python 3.8+
- Android SDK (ADB)
- 已root的Android设备或开发者模式已开启

## 安装

```bash
cd android_perf_tool
pip install .
```

## 使用方法

### 基本用法

```bash
android-perf-tool -p com.example.game -d 60
```

### 参数说明

```
-p, --package     应用包名或应用名称（必填）
-d, --duration    测试时长（秒），默认60秒
-o, --output      报告输出目录，默认./reports
--adb-path        ADB路径，默认adb
--no-excel        不生成Excel报告
--no-html         不生成HTML报告
```

### 示例

```bash
# 测试游戏60秒
android-perf-tool -p com.tencent.pubgmhd -d 60

# 指定ADB路径
android-perf-tool -p com.miHoYo.GenshinImpact --adb-path /path/to/adb

# 只生成HTML报告
android-perf-tool -p com.example.game --no-excel
```

### 图形界面模式（推荐）

```bash
# 方法1：使用启动脚本
python run.py

# 方法2：安装后运行
android-perf-tool-gui
```

## 报告说明

### Excel报告

包含两个工作表：
- **原始数据**: 所有采集到的性能数据
- **汇总报告**: FPS、CPU、内存的统计汇总

### HTML报告

交互式网页报告，包含：
- 性能概览卡片
- FPS趋势图表
- CPU使用率趋势图表
- 内存使用趋势图表
- 详细统计数据
- 原始数据表格

## 注意事项

1. 确保Android设备已连接（`adb devices`可检测到）
2. 确保目标应用已启动
3. 部分指标需要设备有root权限或特殊权限
4. 建议在性能测试前关闭其他后台应用

## 项目结构

```
android_perf_tool/
├── src/
│   └── android_perf_tool/
│       ├── __init__.py
│       ├── adb.py          # ADB命令封装
│       ├── collector.py    # 性能数据采集器
│       ├── cli.py          # 命令行接口
│       ├── excel_report.py # Excel报告生成
│       ├── html_report.py  # HTML报告生成
│       └── utils.py        # 工具函数
├── pyproject.toml
└── README.md
```

## License

MIT License