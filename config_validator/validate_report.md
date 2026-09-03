# 配置表交叉校验报告 v2.0

> 生成时间: 2026-09-03 12:11:25  |  耗时: 33.1s  |  校验规则: 111 条

---

## 总览

| 级别 | 数量 | 说明 |
|:----:|:----:|------|
| **ERROR** | **14** | 必须修复：引用了不存在的ID、主键重复等 |
| WARN | 13 | 建议检查：空值、格式异常、文件/列缺失等 |

## 按模块统计

| 模块 | 错误 | 警告 | 涉及文件数 |
|------|:----:|:----:|:----------:|
| SoldierConfig | **4** | 0 | 1 |
| client | **2** | 0 | 2 |
| Population | **2** | 0 | 1 |
| Activity | **2** | 0 | 1 |
| ToolConfig | **1** | 0 | 1 |
| Card | **1** | 0 | 1 |
| ScienceConfig | **1** | 0 | 1 |
| Ranking | **1** | 0 | 1 |
| Battle | 0 | 11 | 5 |
| Field | 0 | 1 | 1 |
| public | 0 | 1 | 1 |

## 目录

1. [public\Battle\BattlePosTest.xlsx](#public-battle-battlepostest-xlsx) (1 WARN)
2. [public\Battle\Buff.xlsx](#public-battle-buff-xlsx) (2 WARN)
3. [public\Battle\Bullet.xlsx](#public-battle-bullet-xlsx) (1 WARN)
4. [public\Battle\Skill.xlsx](#public-battle-skill-xlsx) (5 WARN)
5. [public\Battle\SkillTalent.xlsx](#public-battle-skilltalent-xlsx) (2 WARN)
6. [public\Field\EventConfig.xlsx](#public-field-eventconfig-xlsx) (1 WARN)
7. [public\Monster.xlsx](#public-monster-xlsx) (1 WARN)
8. [client\Localize_English.xlsx](#client-localize_english-xlsx) (1 ERROR)
9. [client\Localize_ChineseSimplified.xlsx](#client-localize_chinesesimplified-xlsx) (1 ERROR)
10. [public\Population\PopulationType.xlsx](#public-population-populationtype-xlsx) (2 ERROR)
11. [public/SoldierConfig/SoldierConfig.xlsx](#public-soldierconfig-soldierconfig-xlsx) (4 ERROR)
12. [public/ToolConfig/ToolConfig.xlsx](#public-toolconfig-toolconfig-xlsx) (1 ERROR)
13. [public/Card/CardConfig.xlsx](#public-card-cardconfig-xlsx) (1 ERROR)
14. [public/ScienceConfig/ScienceConfig.xlsx](#public-scienceconfig-scienceconfig-xlsx) (1 ERROR)
15. [public/Ranking/RankingConfig.xlsx](#public-ranking-rankingconfig-xlsx) (1 ERROR)
16. [public/Activity/ActivitySevenDaysTask.xlsx](#public-activity-activitysevendaystask-xlsx) (2 ERROR)

---

## 详细结果

### public\Battle\BattlePosTest.xlsx

> 错误: 0  |  警告: 1

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| WARN | BattlePosTest | soldier_key | 列 soldier_key(int32[]) 有 8 行数据格式异常 | 示例: 行5: '[1011,6]'; 行7: '[2013,6]'; 行9: '[3011,6]'; 行10: '[1011,6]'; 行11: '[1012,6]'... 等共 8 行 | - |

### public\Battle\Buff.xlsx

> 错误: 0  |  警告: 2

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| WARN | buff | id | 列 id(int32) 有 6 行数据格式异常 | 示例: 行14: '#打地块技能提供属性'; 行32: '#英雄主动技能BUFF'; 行218: '#英雄被动技能BUFF'; 行583: '#英雄终极被动'; 行616: '#英雄全局技能BUFF'... 等共 6 行 | - |
| WARN | #被动BUFF配置 | id | 列 id(int32) 有 2 行数据格式异常 | 示例: 行10: '#英雄被动技能BUFF'; 行375: '#英雄终极被动' | - |

### public\Battle\Bullet.xlsx

> 错误: 0  |  警告: 1

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| WARN | Bullet | id | 列 id(int16) 有 1 行数据格式异常 | 示例: 行16: '#打地块士兵子弹' | - |

### public\Battle\Skill.xlsx

> 错误: 0  |  警告: 5

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| WARN | skill | id | 列 id(int32) 有 13 行数据格式异常 | 示例: 行6: '#测试数据'; 行32: '#打地块副本'; 行34: '#BUFF技能描述（兵种+时代+星级'; 行54: '#打地块士兵技能'; 行119: '#士兵普攻'... 等共 13 行 | - |
| WARN | skill | trigger_1 | 列 trigger_1(int32[][]) 有 67 行数据格式异常 | 示例: 行9: '[[1]]'; 行20: '[[1]]'; 行27: '[[3,1,10000]]'; 行28: '[[3,0,3000]]'; 行68: '[[4,3]]'... 等共 67 行 | - |
| WARN | skill | skill_function1 | 列 skill_function1(int32[][]) 有 1071 行数据格式异常 | 示例: 行9: '[[1,10011]]'; 行10: '[[1,10011]]'; 行14: '[[1,10011]]'; 行15: '[[1,10011]]'; 行16: '[[1,10011]]'... 等共 1071 行 | - |
| WARN | skill | trigger_2 | 列 trigger_2(int32[][]) 有 2 行数据格式异常 | 示例: 行9: '[[1]]'; 行20: '[[1]]' | - |
| WARN | skill | skill_function2 | 列 skill_function2(int32[][]) 有 8 行数据格式异常 | 示例: 行9: '[[1,10011]]'; 行10: '[[1,10011]]'; 行14: '[[1,10011]]'; 行15: '[[1,10011]]'; 行16: '[[1,10011]]'... 等共 8 行 | - |

### public\Battle\SkillTalent.xlsx

> 错误: 0  |  警告: 2

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| WARN | skill_talent | id | 列 id(int32) 有 1 行数据格式异常 | 示例: 行421: '#打地块玩法-士兵天赋' | - |
| WARN | skill_talent | effect | 列 effect(int32[][]) 有 302 行数据格式异常 | 示例: 行5: '[[101,1500]]'; 行6: '[[101,1500]]'; 行7: '[[101,2000]]'; 行8: '[[101,2500]]'; 行9: '[[101,4500]]'... 等共 302 行 | - |

### public\Field\EventConfig.xlsx

> 错误: 0  |  警告: 1

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| WARN | EventEffect | id | 列 id(int32) 有 1 行数据格式异常 | 示例: 行137: '#副本事件效果' | - |

### public\Monster.xlsx

> 错误: 0  |  警告: 1

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| WARN | Monster | id | 列 id(int32) 有 2 行数据格式异常 | 示例: 行5009: '#打地块副本'; 行5353: '#打地块-普通战斗' | - |

### client\Localize_English.xlsx

> 错误: 1  |  警告: 0

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| **ERROR** | Localize_English | key | Localize_English 缺少 40 个Key（存在于中文表但英文表没有） | #活动框架, #道具获取途径, RankingConfig_name_2, RankingConfig_name_3, RankingConfig_name_4, RankingConfig_name_5, RankingConfig_name_6, RankingConfig_score_name_2, RankingConfig_score_name_3, RankingConfig_scor... | client\Localize_ChineseSimplified.xlsx / Localize_ChineseSimplified |

### client\Localize_ChineseSimplified.xlsx

> 错误: 1  |  警告: 0

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| **ERROR** | Localize_ChineseSimplified | key | Localize_ChineseSimplified 缺少 1 个Key（存在于英文表但中文表没有） | RankingConfig_score_name_990001 | client\Localize_English.xlsx / Localize_English |

### public\Population\PopulationType.xlsx

> 错误: 2  |  警告: 0

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| **ERROR** | PopulationTypeModel | era | [自动] PopulationTypeModel.era -> EraConfig.id | ID=11 (行: 1, 5); ID=12 (行: 2, 6); ID=13 (行: 3, 7); ID=21 (行: 4, 8); ID=22 (行: 9, 11); ID=23 (行: 10, 12) | public\Era\EraConfig.xlsx / EraConfig.id |
| **ERROR** | PopulationTool | era | [自动] PopulationTool.era -> EraConfig.id | ID=11 (共8行, 如: 1, 5, 9...); ID=12 (共8行, 如: 2, 6, 10...); ID=13 (共8行, 如: 3, 7, 11...); ID=21 (共8行, 如: 4, 8, 12...); ID=22 (共8行, 如: 33, 35, 37...); ID=23 (共8行, 如: 34, 36, 38...) | public\Era\EraConfig.xlsx / EraConfig.id |

### public/SoldierConfig/SoldierConfig.xlsx

> 错误: 4  |  警告: 0

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| **ERROR** | SoldierConfig | cure_item_2 | 士兵-治疗消耗道具2 -> ItemConfig | ID=1000 (行: 1000) | public/Item/ItemConfig.xlsx / ItemConfig.id |
| **ERROR** | ArmsConfig | time | 兵种-所属时代 -> EraConfig | ID=6 (共9行, 如: 1020, 1021, 1022...) | public/Era/EraConfig.xlsx / EraConfig.id |
| **ERROR** | ArmsConfig | skill_id | 兵种-被动技能 -> Skill.id | ID=11251 (行: 3013) | public/Battle/Skill.xlsx / skill.id |
| **ERROR** | SoldierConfig | barrack_level | 士兵-兵营等级 -> BarrackConfig | ID=1 (行: 1); ID=5 (行: 2); ID=10 (行: 3); ID=13 (行: 4); ID=16 (行: 5); ID=19 (行: 6); ID=21 (行: 7); ID=24 (行: 8); ID=27 (行: 9); ID=30 (行: 10) | public/Buildings/BarrackConfig.xlsx / BarrackConfig.id |

### public/ToolConfig/ToolConfig.xlsx

> 错误: 1  |  警告: 0

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| **ERROR** | ToolConfig | science_node | 工具-科研节点 -> ScienceNode | ID=1080101 (行: 101); ID=1100101 (行: 10102); ID=1100301 (行: 10202); ID=1130101 (行: 201, 401); ID=1130301 (行: 301); ID=1170101 (行: 102); ID=1190101 (行: 10103); ID=1190301 (行: 10203) | public/ScienceConfig/ScienceConfig.xlsx / ScienceNode.id |

### public/Card/CardConfig.xlsx

> 错误: 1  |  警告: 0

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| **ERROR** | CardConfig | unique_skill_id | 英雄-专属技能 -> Skill.skill_id | ID=101 (行: 10001); ID=102 (行: 10002); ID=103 (行: 10003); ID=104 (行: 10004); ID=105 (行: 10005); ID=106 (行: 10006); ID=107 (行: 10007); ID=108 (行: 10008); ID=109 (行: 10009); ID=110 (行: 10010); ID=111 (行:... | public/Battle/Skill.xlsx / skill.skill_id |

### public/ScienceConfig/ScienceConfig.xlsx

> 错误: 1  |  警告: 0

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| **ERROR** | ScienceNode | sub_era_id | 科技节点-小时代ID -> SubEraConfig | ID=31 (共102行, 如: 2100201, 2100202, 2100203...); ID=41 (共120行, 如: 2150201, 2150202, 2150203...); ID=51 (共104行, 如: 2210201, 2210202, 2210203...) | public/Era/EraConfig.xlsx / SubEraConfig.id |

### public/Ranking/RankingConfig.xlsx

> 错误: 1  |  警告: 0

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| **ERROR** | RankingConfig | reward_group_id | 排行榜-奖励组 -> RankingReward | ID=990101 (行: 990001, 990002); ID=990102 (行: 990003) | public/Ranking/RankingConfig.xlsx / RankingReward.id |

### public/Activity/ActivitySevenDaysTask.xlsx

> 错误: 2  |  警告: 0

| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |
|:----:|-------|-----|------|------|--------|
| **ERROR** | ActivitySevenDaysTask | task_tab_group_id | 七天活动-任务标签组 -> SevenDaysTaskTab | ID=1 (行: 1) | public/Activity/ActivitySevenDaysTask.xlsx / SevenDaysTaskTab.id |
| **ERROR** | ActivitySevenDaysTask | score_reward_group_id | 七天活动-积分奖励组 -> SevenDaysTaskScoreReward | ID=1 (行: 1) | public/Activity/ActivitySevenDaysTask.xlsx / SevenDaysTaskScoreReward.id |

---

## 附录：多语言Key差异明细

| 项目 | 值 |
|------|-----|
| 中文表 | client\Localize_ChineseSimplified.xlsx / Localize_ChineseSimplified |
| 英文表 | client\Localize_English.xlsx / Localize_English |
| 中文表Key总数 | 3704 |
| 英文表Key总数 | 3665 |
| 英文表缺少 | **40** 个Key |
| 中文表缺少 | **1** 个Key |

### 英文表缺少的Key（共 40 个）

以下Key存在于 Localize_ChineseSimplified 但不存在于 Localize_English：

| # | Key | 中文表行号 |
|:--:|-----|:----------:|
| 1 | `#活动框架` | 962 |
| 2 | `#道具获取途径` | 474 |
| 3 | `RankingConfig_name_2` | 3062 |
| 4 | `RankingConfig_name_3` | 3063 |
| 5 | `RankingConfig_name_4` | 3064 |
| 6 | `RankingConfig_name_5` | 3065 |
| 7 | `RankingConfig_name_6` | 3066 |
| 8 | `RankingConfig_score_name_2` | 3072 |
| 9 | `RankingConfig_score_name_3` | 3073 |
| 10 | `RankingConfig_score_name_4` | 3074 |
| 11 | `activity_7day_reward_vip_desc` | 975 |
| 12 | `activity_no_open` | 963 |
| 13 | `cityPopupGetMore_go` | 483 |
| 14 | `cityPopupGetMore_purchase` | 482 |
| 15 | `cityPopupGetMore_quick_use` | 486 |
| 16 | `cityPopupGetMore_title` | 481 |
| 17 | `cityPopupGetMore_use` | 484 |
| 18 | `cityPopupGetMore_use_all` | 485 |
| 19 | `cityPopupQuickFill_cancel` | 479 |
| 20 | `cityPopupQuickFill_confirm` | 480 |
| 21 | `cityPopupQuickFill_not_show` | 478 |
| 22 | `cityPopupQuickFill_tips` | 476 |
| 23 | `cityPopupQuickFill_title_quick_fill` | 475 |
| 24 | `cityPopupQuickFill_warning` | 477 |
| 25 | `game_avatar_invalid` | 399 |
| 26 | `game_avatar_not_unlocked` | 398 |
| 27 | `game_field_shop_sold_out` | 333 |
| 28 | `game_gender_invalid` | 397 |
| 29 | `game_gender_modify_cost_not_enough` | 396 |
| 30 | `game_name_invalid` | 392 |
| 31 | `game_name_same` | 394 |
| 32 | `game_name_taken` | 393 |
| 33 | `game_name_unique_failed` | 401 |
| 34 | `game_player_brief_not_found` | 400 |
| 35 | `game_rename_cost_not_enough` | 395 |
| 36 | `game_rename_cost_type_invalid` | 402 |
| 37 | `player_name_confirm` | 1209 |
| 38 | `player_name_duplicate_error` | 1210 |
| 39 | `player_name_length_error` | 1208 |
| 40 | `player_name_same_error` | 1207 |

### 中文表缺少的Key（共 1 个）

以下Key存在于 Localize_English 但不存在于 Localize_ChineseSimplified：

| # | Key | 英文表行号 |
|:--:|-----|:----------:|
| 1 | `RankingConfig_score_name_990001` | 3036 |

---

## 附录：无效ID速查表

以下表格按无效ID聚合，方便快速排查是目标表缺少配置还是源表填写错误。

| 无效ID | 来源规则 | 目标表 | 涉及行数 |
|:------:|----------|--------|:--------:|
| 1 | 士兵-兵营等级 -> BarrackConfig | public/Buildings/BarrackConfig.xlsx / BarrackConfig.id | 10 |
| 1 | 七天活动-任务标签组 -> SevenDaysTaskTab | public/Activity/ActivitySevenDaysTask.xlsx / SevenDaysTaskTab.id | 1 |
| 1 | 七天活动-积分奖励组 -> SevenDaysTaskScoreReward | public/Activity/ActivitySevenDaysTask.xlsx / SevenDaysTaskScoreReward.id | 1 |
| 5 | 士兵-兵营等级 -> BarrackConfig | public/Buildings/BarrackConfig.xlsx / BarrackConfig.id | 10 |
| 6 | 兵种-所属时代 -> EraConfig | public/Era/EraConfig.xlsx / EraConfig.id | 9 |
| 10 | 士兵-兵营等级 -> BarrackConfig | public/Buildings/BarrackConfig.xlsx / BarrackConfig.id | 10 |
| 11 | [自动] PopulationTypeModel.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 12 |
| 11 | [自动] PopulationTool.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 48 |
| 12 | [自动] PopulationTypeModel.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 12 |
| 12 | [自动] PopulationTool.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 48 |
| 13 | [自动] PopulationTypeModel.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 12 |
| 13 | [自动] PopulationTool.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 48 |
| 13 | 士兵-兵营等级 -> BarrackConfig | public/Buildings/BarrackConfig.xlsx / BarrackConfig.id | 10 |
| 16 | 士兵-兵营等级 -> BarrackConfig | public/Buildings/BarrackConfig.xlsx / BarrackConfig.id | 10 |
| 19 | 士兵-兵营等级 -> BarrackConfig | public/Buildings/BarrackConfig.xlsx / BarrackConfig.id | 10 |
| 21 | [自动] PopulationTypeModel.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 12 |
| 21 | [自动] PopulationTool.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 48 |
| 21 | 士兵-兵营等级 -> BarrackConfig | public/Buildings/BarrackConfig.xlsx / BarrackConfig.id | 10 |
| 22 | [自动] PopulationTypeModel.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 12 |
| 22 | [自动] PopulationTool.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 48 |
| 23 | [自动] PopulationTypeModel.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 12 |
| 23 | [自动] PopulationTool.era -> EraConfig.id | public\Era\EraConfig.xlsx / EraConfig.id | 48 |
| 24 | 士兵-兵营等级 -> BarrackConfig | public/Buildings/BarrackConfig.xlsx / BarrackConfig.id | 10 |
| 27 | 士兵-兵营等级 -> BarrackConfig | public/Buildings/BarrackConfig.xlsx / BarrackConfig.id | 10 |
| 30 | 士兵-兵营等级 -> BarrackConfig | public/Buildings/BarrackConfig.xlsx / BarrackConfig.id | 10 |
| 31 | 科技节点-小时代ID -> SubEraConfig | public/Era/EraConfig.xlsx / SubEraConfig.id | 326 |
| 41 | 科技节点-小时代ID -> SubEraConfig | public/Era/EraConfig.xlsx / SubEraConfig.id | 326 |
| 51 | 科技节点-小时代ID -> SubEraConfig | public/Era/EraConfig.xlsx / SubEraConfig.id | 326 |
| 101 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 102 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 103 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 104 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 105 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 106 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 107 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 108 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 109 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 110 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 111 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 112 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 113 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 114 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 115 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 116 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 117 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 118 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 119 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 120 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 121 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 122 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 123 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 124 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 125 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 126 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 127 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 128 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 129 | 英雄-专属技能 -> Skill.skill_id | public/Battle/Skill.xlsx / skill.skill_id | 29 |
| 1000 | 士兵-治疗消耗道具2 -> ItemConfig | public/Item/ItemConfig.xlsx / ItemConfig.id | 1 |
| 11251 | 兵种-被动技能 -> Skill.id | public/Battle/Skill.xlsx / skill.id | 1 |
| 990101 | 排行榜-奖励组 -> RankingReward | public/Ranking/RankingConfig.xlsx / RankingReward.id | 3 |
| 990102 | 排行榜-奖励组 -> RankingReward | public/Ranking/RankingConfig.xlsx / RankingReward.id | 3 |
| 1080101 | 工具-科研节点 -> ScienceNode | public/ScienceConfig/ScienceConfig.xlsx / ScienceNode.id | 9 |
| 1100101 | 工具-科研节点 -> ScienceNode | public/ScienceConfig/ScienceConfig.xlsx / ScienceNode.id | 9 |
| 1100301 | 工具-科研节点 -> ScienceNode | public/ScienceConfig/ScienceConfig.xlsx / ScienceNode.id | 9 |
| 1130101 | 工具-科研节点 -> ScienceNode | public/ScienceConfig/ScienceConfig.xlsx / ScienceNode.id | 9 |
| 1130301 | 工具-科研节点 -> ScienceNode | public/ScienceConfig/ScienceConfig.xlsx / ScienceNode.id | 9 |
| 1170101 | 工具-科研节点 -> ScienceNode | public/ScienceConfig/ScienceConfig.xlsx / ScienceNode.id | 9 |
| 1190101 | 工具-科研节点 -> ScienceNode | public/ScienceConfig/ScienceConfig.xlsx / ScienceNode.id | 9 |
| 1190301 | 工具-科研节点 -> ScienceNode | public/ScienceConfig/ScienceConfig.xlsx / ScienceNode.id | 9 |
