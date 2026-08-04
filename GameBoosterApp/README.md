# GameBooster - Android游戏加速应用

一款专为游戏优化设计的Android应用，通过调整系统资源分配，提升游戏运行性能。

## 功能特性

- **CPU性能优化** - 调整CPU频率和调度策略，释放处理器潜能
- **GPU性能优化** - 提升图形处理能力，让游戏画面更流畅
- **网络加速** - 优化网络参数，降低延迟
- **内存清理** - 释放系统内存，为游戏提供更多资源
- **三种加速模式** - 高性能/平衡/省电模式

## 技术实现

### CPU优化
- 设置CPU调度器为performance模式
- 调整CPU最小/最大频率
- 设置进程优先级

### GPU优化
- 设置GPU最大时钟频率
- 启用TrustZone电源管理

### 网络优化
- 启用TCP时间戳、SACK和窗口缩放
- 优化网络连接参数

## 权限说明

- `INTERNET` - 网络访问权限
- `ACCESS_NETWORK_STATE` - 网络状态检测
- `RECEIVE_BOOT_COMPLETED` - 开机自启动
- `WRITE_SETTINGS` - 修改系统设置
- `SYSTEM_ALERT_WINDOW` - 悬浮窗权限
- `FOREGROUND_SERVICE` - 前台服务权限
- `VIBRATE` - 震动反馈

## 项目结构

```
app/
├── src/main/java/com/example/gamebooster/
│   ├── MainActivity.java      # 主界面
│   ├── BoosterService.java    # 加速服务
│   ├── PerformanceOptimizer.java  # 性能优化核心
│   └── BootReceiver.java      # 开机自启动
├── src/main/res/
│   ├── layout/
│   │   └── activity_main.xml  # 主界面布局
│   ├── values/
│   │   ├── strings.xml        # 字符串资源
│   │   ├── styles.xml         # 样式定义
│   │   └── colors.xml         # 颜色定义
│   ├── drawable/              # 图形资源
│   └── mipmap-hdpi/           # 应用图标
└── AndroidManifest.xml        # 应用配置
```

## 构建运行

1. 使用Android Studio打开项目
2. 确保安装了Android SDK 34
3. 连接Android设备或启动模拟器
4. 点击Run按钮构建并运行应用

## 注意事项

- 需要Android 7.0 (API 24)或更高版本
- 部分功能需要Root权限才能生效
- 建议在游戏前开启加速功能
- 长时间使用高性能模式可能会增加电池消耗

## License

MIT License