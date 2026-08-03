# Unity UI Prefab Scanner

## 功能说明

这是一个基于Unity引擎的工具，用于扫描Unity项目中的UI预制体，在不同语言配置下自动检测UI问题。

### 主要功能

1. **扫描UI预制体**：自动扫描项目中的所有UI预制体
2. **多语言切换**：根据多语言配置自动切换不同语言
3. **UI问题检测**：检测以下问题：
   - 文本超框（翻译超出显示范围）
   - 缺少翻译
   - UI元素重叠
4. **截图保存**：为每个预制体和语言组合生成截图
5. **结果报告**：生成详细的测试报告，包含所有检测到的问题

## 如何使用

1. 在Unity编辑器中，点击顶部菜单栏的 `Tools > UI Prefab Scanner`
2. 在打开的窗口中，点击 `Scan for UI Prefabs` 按钮扫描项目中的UI预制体
3. 扫描完成后，点击 `Start Language Test` 按钮开始测试
4. 测试结果将保存在 `Assets/UI_Scan_Results/[timestamp]` 文件夹中，包含：
   - 每个预制体在不同语言下的截图
   - 详细的测试报告（report.txt）

## 多语言配置

多语言配置文件位于 `Assets/StreamingAssets/Localization/` 目录下，支持以下格式：

```json
{
  "items": [
    {
      "key": "welcome_text",
      "value": "Welcome to the game!"
    }
  ]
}
```

## 注意事项

1. 确保UI预制体中使用了 `LocalizedText` 组件来管理文本
2. 确保多语言配置文件格式正确
3. 测试过程中会在场景中临时创建游戏对象，测试完成后会自动清理
