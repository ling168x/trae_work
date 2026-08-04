# 战斗伤害计算器

基于战斗伤害流程实现的Python工具，支持计算普攻伤害、技能伤害和暴击伤害。

## 文件结构

```
DamageCalculator/
├── damage_calculator.py    # 核心计算逻辑
├── damage_calculator_gui.py # GUI界面
├── start_gui.bat           # Windows启动脚本
└── README.md               # 说明文档
```

## 使用方法

### 方法1：双击启动（Windows）
直接双击 `start_gui.bat` 文件即可启动GUI界面。

### 方法2：命令行启动
```bash
python damage_calculator_gui.py
```

### 方法3：命令行计算
```bash
python damage_calculator.py --attacker_atk=961 --defender_def=1 --attacker_skill_coeff=0.63
```

## 战斗伤害流程

| 步骤 | 名称 | 说明 |
|------|------|------|
| Step 1 | 闪避判定 | 闪避率=守方闪避率-攻方命中率 |
| Step 2 | 基础伤害 | 攻击^2/(攻击+K*防御)，K=2.5 |
| Step 3 | 普攻/技能伤害 | 根据攻击类型计算 |
| Step 4 | 暴击伤害 | 暴击判定与伤害计算 |
| Step 5 | 克制修正 | 统御→战斗→谋略→统御 |
| Step 6 | 士气修正 | 伤害*max(1,攻方士气/守方士气) |
| Step 7 | 累加型伤害系数 | 累加系数修正 |
| Step 8 | 伤害加深/减免 | 伤害加深与减免修正 |
| Step 9 | 易伤修正 | 易伤伤害加成 |
| Step 10 | PVP/PVE修正 | 战斗模式修正 |
| Step 11 | 指挥修正 | 指挥属性修正 |

## 参数说明

### 基础属性
- 攻击方：总攻击、技能系数、类型、士气、指挥
- 防守方：总防御、类型、士气、指挥

### 高级属性
- 暴击属性：暴击率、抗暴率、暴击伤害、暴击减免
- 伤害修正：普攻增加/减少、技能增加/减少、伤害加深/减免
- 战斗设置：克制增加/减免、累加增加/减免、易伤加成
- 模式设置：PVP模式、PVP加成/减免、PVE增加、命中率、闪避率