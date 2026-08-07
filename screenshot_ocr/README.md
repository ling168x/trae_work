# 截图提取文字工具

基于 PaddleOCR 的桌面截图 OCR 工具，微信风格选区截图 + 中英文文字识别，识别结果自动追加保存到 Excel 文件。

## 功能特性

- **微信风格截图**：屏幕实景 + 暗色遮罩，选区清晰可见，实时显示选区尺寸
- **中英文 OCR 识别**：基于 PaddleOCR，支持方向分类（自动纠正旋转/倾斜文字）
- **图像预处理**：小图自动放大 2~3 倍、增强对比度、锐化，提升识别率
- **结果自动归档**：每次识别结果按「序号 / 截图时间 / 提取的文字」追加到同一个 Excel
- **全局热键**：`Ctrl+Shift+S` 随时唤起截图（不可用时退化为按钮点击）
- **Excel 管理**：内置「打开 Excel」「清除所有记录」按钮，支持自定义保存路径
- **PaddleOCR 3.x 兼容**：自动适配 2.x / 3.x 接口差异，并绕过 Windows + OneDNN 下的 PIR 执行器 bug

## 目录结构

```
screenshot_ocr/
├── screenshot_ocr.py        # 主程序（GUI + 截图 + OCR + Excel 写入）
├── requirements.txt         # Python 依赖
├── run.bat                  # Windows 一键启动脚本（自动安装依赖）
├── README.md                # 本文档
└── screenshot_texts.xlsx    # 运行时生成，存放识别记录
```

## 环境要求

- **操作系统**：Windows（截图使用了 `ImageGrab.grab` 和 `os.startfile`，仅 Windows 可用）
- **Python**：3.8+（已在 3.9 验证）
- **PaddlePaddle / PaddleOCR**：兼容 2.x 与 3.x

## 快速开始

### 方式一：一键启动（推荐）

双击 `run.bat`，脚本会：

1. 检测 Python 是否安装
2. 首次运行自动 `pip install -r requirements.txt`（使用清华源加速）
3. 安装成功后写入 `.deps_installed` 标记，后续启动跳过安装
4. 启动 `screenshot_ocr.py`

### 方式二：手动运行

```bash
pip install -r requirements.txt
python screenshot_ocr.py
```

## 使用说明

1. 启动后出现主窗口，状态栏显示「就绪 — Ctrl+Shift+S 截图」
2. 按下 `Ctrl+Shift+S`（或点击「开始截图」按钮），主窗口最小化
3. 屏幕进入截图模式：
   - **拖动鼠标**框选目标区域（选区外暗化，选区内显示原图）
   - 选区左上角实时显示「宽 x 高」像素尺寸
   - **ESC** 取消本次截图
4. 松开鼠标后自动进入识别流程：
   - 图像预处理 → 加载 OCR 模型 → 识别
   - 状态栏实时显示当前阶段
5. 识别完成后：
   - 识别文本显示在「最近识别结果」区域
   - 自动追加一行到 `screenshot_texts.xlsx`
   - 状态栏提示「识别成功！已保存到 Excel」

### 主窗口按钮

| 按钮 | 功能 |
| --- | --- |
| 开始截图 (Ctrl+Shift+S) | 进入截图模式 |
| 更改 | 自定义 Excel 保存路径 |
| 打开 Excel 文件 | 用系统默认程序打开当前 Excel |
| 清除所有记录 | 删除 Excel 文件（二次确认，不可恢复） |

## Excel 输出格式

| 序号 | 截图时间 | 提取的文字 |
| --- | --- | --- |
| 1 | 2026-08-07 22:30:15 | 识别到的第一段文字 |

- 表头深色填充 + 白字加粗
- 「提取的文字」列自动换行，多行文字按原顺序合并
- 每次识别追加到 `max_row + 1`，不覆盖历史记录

## 技术细节

### PaddleOCR 3.x 适配

PaddleOCR 3.x 相对 2.x 有破坏性变更，代码做了双重兼容：

1. **构造参数**：移除 3.x 不再支持的 `use_gpu` / `show_log`，新增 `enable_mkldnn=False`
2. **调用方式**：优先用 `ocr.predict(img)`，回退到 `ocr.ocr(img, cls=True)`
3. **结果解析**：3.x 返回 `list[dict]`（含 `rec_texts` 字段），2.x 返回嵌套 `list`

### 绕过 PIR + OneDNN 崩溃

PaddlePaddle 3.x 在 Windows + OneDNN 下存在已知 bug（[PaddleOCR #18119](https://github.com/PaddlePaddle/PaddleOCR/issues/18119)）：

```
NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support
[pir::ArrayAttribute<pir::DoubleAttribute>]
```

通过在 `import paddle` **之前**设置环境变量规避：

```python
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
os.environ.setdefault("FLAGS_use_mkldnn", "0")
```

> 注：关闭 mkldnn 后 CPU 推理略慢，但对小尺寸截图影响可忽略。

### 线程模型

- OCR 在独立 daemon 线程执行，避免阻塞 tkinter 主循环
- 跨线程更新 UI 通过 `root.after(0, ...)` 调度回主线程
- OCR 模型使用双检锁单例懒加载，首次识别时才初始化（约几秒）

### 图像预处理

小截图识别率低，统一做预处理：

- 宽 < 200 或高 < 200：放大 3 倍
- 宽 < 400 或高 < 200：放大 2 倍
- 对比度增强 1.8 倍
- 一次锐化滤镜

## 常见问题

**Q: 启动后状态栏显示「就绪 — 点击按钮截图」，热键不可用？**
A: `keyboard` 模块需要管理员权限才能注册全局热键。用管理员身份运行 `run.bat` 即可。

**Q: 首次识别很慢？**
A: 首次调用会下载 PaddleOCR 模型并初始化推理引擎，后续识别会快很多。

**Q: 识别结果为空？**
A: 尝试框选更大、更清晰的区域，确保文字对比度足够。工具会自动放大和增强图像，但过小的文字仍可能识别失败。

**Q: Excel 文件被占用导致保存失败？**
A: 关闭正在打开该 Excel 的程序（如 WPS / Excel）后重试。
