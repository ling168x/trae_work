# Unity UI Prefab Scanner 操作文档

## 一、项目概述

本工具用于扫描Unity项目中的UI预制体，在不同语言配置下自动检测UI问题（超框、重叠、缺少翻译等），并生成截图和检测报告。

## 二、环境要求

### 必要环境
- **Unity版本**：Unity 2021.3 或更高版本
- **操作系统**：Windows / macOS / Linux
- **Git客户端**：用于克隆项目（可选，也可直接下载）

### Unity包依赖
- Unity UI系统（Unity自带，无需额外安装）

## 三、克隆项目

### 方法一：使用Git命令（推荐）

#### 3.1.1 使用SSH方式
```bash
# 克隆仓库
git clone git@github.com:ling168x/trae_work.git

# 进入项目目录
cd trae_work

# 切换到项目目录（如果仓库中有多个项目）
cd unity_prefab_check
```

#### 3.1.2 使用HTTPS方式
```bash
# 克隆仓库
git clone https://github.com/ling168x/trae_work.git

# 进入项目目录
cd trae_work

# 切换到项目目录
cd unity_prefab_check
```

### 方法二：直接下载ZIP

1. 访问仓库地址：https://github.com/ling168x/trae_work
2. 点击绿色的 "Code" 按钮
3. 选择 "Download ZIP"
4. 解压下载的文件
5. 进入 `unity_prefab_check` 目录

## 四、打开项目

### 4.1 使用Unity Hub打开

1. 打开 **Unity Hub**
2. 点击右上角的 **"Add"** 或 **"添加项目"**
3. 选择 `unity_prefab_check` 文件夹
4. 选择合适的Unity版本（推荐Unity 2021.3或更高）
5. 点击项目卡片打开项目

### 4.2 直接使用Unity编辑器打开

1. 打开Unity编辑器
2. 点击菜单 **"File" > "Open Project"**
3. 选择 `unity_prefab_check` 文件夹
4. 等待Unity加载完成

## 五、使用工具

### 5.1 打开工具窗口

在Unity编辑器中，点击顶部菜单栏：
```
Tools > UI Prefab Scanner
```

### 5.2 扫描UI预制体

1. 在打开的 "UI Prefab Scanner" 窗口中
2. 点击 **"Scan for UI Prefabs"** 按钮
3. 等待扫描完成（会弹出提示框显示找到的预制体数量）
4. 扫描结果会显示在窗口列表中

### 5.3 配置输出路径

在窗口底部的 **"Output Folder"** 输入框中，可以修改输出文件夹名称（默认为 `UI_Scan_Results`）

### 5.4 开始测试

1. 点击 **"Start Language Test"** 按钮
2. 工具会自动：
   - 遍历扫描到的所有UI预制体
   - 切换不同语言配置
   - 检测UI问题
   - 生成截图
3. 测试完成后会弹出提示框，显示结果保存路径

### 5.5 查看测试结果

测试结果保存在 `Assets/UI_Scan_Results/[时间戳]` 文件夹中，例如：
```
Assets/UI_Scan_Results/2026-04-15 22-22-50/
```

文件夹内容包括：
- `预制体名_语言.png` - 每个预制体在不同语言下的截图
- `report.txt` - 详细的测试报告

## 六、多语言配置

### 6.1 配置文件位置

多语言配置文件位于：
```
Assets/StreamingAssets/Localization/
```

### 6.2 添加新语言

1. 在 `Assets/StreamingAssets/Localization/` 文件夹中创建新的JSON文件
2. 文件名为语言代码（例如 `ja.json` 表示日语）
3. 按以下格式编写配置：

```json
{
  "items": [
    {
      "key": "welcome_text",
      "value": "ようこそゲームへ！"
    },
    {
      "key": "start_button",
      "value": "ゲーム開始"
    }
  ]
}
```

### 6.3 现有语言配置

| 文件名 | 语言 | 用途 |
|--------|------|------|
| `en.json` | 英文 | 正常翻译测试 |
| `zh.json` | 中文 | 正常翻译测试 |
| `zh_long.json` | 中文（长文本） | 测试文本超框问题 |

### 6.4 修改测试语言

打开 `Assets/Scripts/Editor/UILanguageTester.cs` 文件，找到第9行：
```csharp
private string[] languages = { "en", "zh", "zh_long" };
```

可以修改此数组来添加或删除要测试的语言，例如：
```csharp
private string[] languages = { "en", "zh", "ja", "ko" };
```

## 七、UI预制体配置

### 7.1 添加LocalizedText组件

要让UI文本支持多语言，需要添加 `LocalizedText` 组件：

1. 在Unity编辑器中选择UI文本对象
2. 点击 **"Add Component"**
3. 搜索并添加 **"LocalizedText"** 组件
4. 在Inspector面板中设置 **"Key"** 字段

### 7.2 Key字段说明

`Key` 字段对应多语言配置文件中的键名。例如：
- 如果Key设置为 `welcome_text`
- 工具会自动从 `en.json` 中读取 `welcome_text` 对应的值
- 英文显示为 "Welcome to the game!"
- 中文显示为 "欢迎来到游戏！"

## 八、检测的问题类型

| 问题类型 | 说明 | 检测方式 |
|---------|------|---------|
| **TextOverflow** | 文本超框 | 检测文本宽度是否超过容器宽度 |
| **MissingTranslation** | 缺少翻译 | 检查Key是否在语言配置中存在 |
| **ElementOverlap** | 元素重叠 | 检测UI元素矩形是否有交叉 |

## 九、常见问题解答

### Q1: 扫描不到任何预制体？

**原因**：预制体中没有使用UI元素或LocalizedText组件。

**解决**：
1. 确保预制体中包含Unity UI元素（Text、Button、Image等）
2. 如果需要检测翻译问题，需添加LocalizedText组件

### Q2: 测试时没有截图生成？

**原因**：Unity没有正确渲染场景。

**解决**：
1. 确保Unity编辑器处于非播放模式
2. 尝试在测试前保存当前场景
3. 检查Console是否有错误信息

### Q3: 如何自定义问题检测规则？

打开 `Assets/Scripts/Editor/UILanguageTester.cs` 文件，找到 `DetectUIIssues` 方法，可以修改或添加新的检测规则。

### Q4: 如何修改截图大小？

打开 `Assets/Scripts/Editor/UILanguageTester.cs` 文件，找到 `TakeScreenshot` 方法，修改相机参数：
```csharp
camera.orthographicSize = 5;  // 调整此值改变截图大小
```

### Q5: 如何使用自己的项目进行测试？

1. 将你的UI预制体复制到当前项目的 `Assets` 目录下
2. 确保预制体使用了LocalizedText组件
3. 按上述步骤运行测试即可

## 十、项目文件结构

```
unity_prefab_check/
├── Assets/
│   ├── Scripts/
│   │   ├── Editor/
│   │   │   ├── UIPrefabScanner.cs      # 编辑器窗口脚本
│   │   │   └── UILanguageTester.cs     # 语言测试核心逻辑
│   │   └── Localization/
│   │       ├── LocalizationManager.cs  # 多语言管理器
│   │       └── LocalizedText.cs        # 本地化文本组件
│   ├── StreamingAssets/
│   │   └── Localization/
│   │       ├── en.json                 # 英文配置
│   │       ├── zh.json                 # 中文配置
│   │       └── zh_long.json            # 长文本中文配置
│   ├── TestUIPrefab.prefab             # 示例UI预制体
│   └── UI_Scan_Results/                # 测试结果输出目录（自动生成）
├── ProjectSettings/
│   └── ProjectSettings.asset           # Unity项目配置
├── .gitignore                          # Git忽略规则
└── README.md                           # 本说明文档
```

## 十一、技术支持

如遇到问题，请检查：
1. Unity版本是否符合要求（2021.3+）
2. 项目文件是否完整
3. Console窗口是否有错误信息
4. 多语言配置文件格式是否正确

---

**文档版本**: v1.0  
**最后更新**: 2026-08-03
