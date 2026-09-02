#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置表交叉校验工具
- 自动扫描所有 xlsx 配置表
- 根据列名和类型自动推断跨表引用关系
- 支持手动规则覆盖/补充
- 新增表格无需修改代码即可自动校验
"""

import os
import re
import sys
import glob
from collections import defaultdict
from openpyxl import load_workbook

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
DEFAULT_CONFIG_DIR = r"d:\Client\template"

# 排除的列名模式（这些列不参与自动校验）
SKIP_COLUMN_PATTERNS = [
    r'^id$',           # 主键
    r'^name$',         # 名称
    r'^desc',          # 描述
    r'^icon',          # 图标
    r'^color',         # 颜色
    r'^value$',        # 数值
    r'^num$',          # 数量
    r'^level$',        # 等级
    r'^star$',         # 星级
    r'^quality$',      # 品质
    r'^type$',         # 类型
    r'^sort',          # 排序
    r'^weight',        # 权重
    r'^prob',          # 概率
    r'^cd$',           # 冷却
    r'^time$',         # 时间
    r'^duration',      # 持续
    r'^radius',        # 半径
    r'^range',         # 范围
    r'^angle',         # 角度
    r'^speed',         # 速度
    r'^scale',         # 缩放
    r'^pos',           # 位置
    r'^offset',        # 偏移
    r'^model',         # 模型
    r'^ani',           # 动画
    r'^text',          # 文本
    r'^string',        # 字符串
    r'^float',         # 浮点参数
    r'^param',         # 参数
    r'^flag',          # 标记
    r'^enable',        # 启用
    r'^unlock',        # 解锁
    r'^count',         # 计数
    r'^amount',        # 数量
    r'^max$',          # 最大值
    r'^min$',          # 最小值
    r'^need',          # 需求
    r'^limit',         # 限制
    r'^extra',         # 额外
    r'^page',          # 页签
    r'^show',          # 显示
    r'^is_',           # 布尔标记
    r'^order',         # 顺序
    r'^index',         # 索引
    r'^prize',         # 奖励
    r'^display',       # 展示
    r'^tips',          # 提示
    r'^fx',            # 特效
    r'^vfx',           # 视觉特效
    r'^sfx',           # 音效
    r'^bgm',           # 背景音乐
    r'^condition',     # 条件表达式
    r'^conditions',    # 条件表达式
    r'^formula',       # 公式
]


# ---------------------------------------------------------------------------
# 数据读取
# ---------------------------------------------------------------------------

def read_sheet_data(filepath, sheet_name):
    """读取 sheet 数据，返回 (headers_cn, headers_en, types_row, data_rows)"""
    wb = load_workbook(filepath, read_only=True, data_only=True)
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if len(rows) < 4:
        return None, None, None, []

    headers_cn = [str(c) if c is not None else "" for c in rows[0]]
    headers_en = [str(c) if c is not None else "" for c in rows[1]]
    types_row  = [str(c) if c is not None else "" for c in rows[2]]
    data_rows  = [list(r) for r in rows[3:]]

    return headers_cn, headers_en, types_row, data_rows


def extract_id_set(data_rows, col_idx):
    """从数据行中提取指定列的 ID 集合"""
    ids = set()
    for row in data_rows:
        if col_idx < len(row):
            val = row[col_idx]
            if val is not None and str(val).strip() != "":
                try:
                    ids.add(int(val))
                except (ValueError, TypeError):
                    pass
    return ids


def parse_int_array(val):
    """解析 int[] 或 int[][] 类型，提取所有整型 ID"""
    ids = set()
    if val is None or str(val).strip() == "":
        return ids
    s = str(val).strip()
    if s.startswith("[["):
        matches = re.findall(r'\[(\d+)\s*,\s*\d+\]', s)
        for m in matches:
            ids.add(int(m))
    elif s.startswith("["):
        matches = re.findall(r'\d+', s)
        for m in matches:
            ids.add(int(m))
    else:
        try:
            ids.add(int(s))
        except ValueError:
            pass
    return ids


# ---------------------------------------------------------------------------
# 表注册中心
# ---------------------------------------------------------------------------

class TableInfo:
    """单个 sheet 的元信息"""
    def __init__(self, rel_path, xlsx_name, sheet_name):
        self.rel_path = rel_path          # "public/Item/ItemConfig.xlsx"
        self.xlsx_name = xlsx_name        # "ItemConfig.xlsx"
        self.sheet_name = sheet_name      # "ItemConfig"
        self.pk_col = None                # 主键列名
        self.pk_values = set()            # 主键值集合
        self.columns = {}                 # col_name -> {"type": "int", "cn": "道具ID"}
        self.col_index = {}               # col_name -> 列索引

    def __repr__(self):
        return f"TableInfo({self.rel_path}/{self.sheet_name})"


class TableRegistry:
    """全局表注册中心：扫描所有 xlsx，建立索引"""
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.tables = []          # 所有 TableInfo
        self.id_cache = {}        # (rel_path, sheet, col) -> set of IDs
        self._by_name = {}        # sheet_name -> [TableInfo, ...]  (用于按名称查找)

    def discover(self):
        """扫描所有 xlsx 文件"""
        print("  扫描配置表...")
        xlsx_files = []
        for sub in ["public", "client"]:
            root = os.path.join(self.config_dir, sub)
            if os.path.isdir(root):
                for f in glob.glob(os.path.join(root, "**", "*.xlsx"), recursive=True):
                    fname = os.path.basename(f)
                    if fname.startswith("~$"):
                        continue
                    rel = os.path.relpath(f, self.config_dir)
                    xlsx_files.append(rel)

        for rel in sorted(xlsx_files):
            full = os.path.join(self.config_dir, rel)
            try:
                wb = load_workbook(full, read_only=True, data_only=True)
                for sn in wb.sheetnames:
                    if sn.startswith("Sheet"):
                        continue
                    try:
                        _, headers_en, types_row, data_rows = read_sheet_data(full, sn)
                        if headers_en is None or len(headers_en) == 0:
                            continue

                        ti = TableInfo(rel, os.path.basename(rel), sn)
                        # 第一列作为主键
                        ti.pk_col = headers_en[0] if headers_en[0] else "id"
                        ti.pk_values = extract_id_set(data_rows, 0)

                        # 记录所有列
                        for ci, (cn, ct, cc) in enumerate(zip(headers_en, types_row, [""] * len(headers_en))):
                            if cn and cn.strip():
                                cname = cn.strip().lower()
                                ti.columns[cname] = {"type": ct.strip().lower() if ct else "", "cn": ""}
                                ti.col_index[cname] = ci

                        self.tables.append(ti)
                        name = sn.lower()
                        if name not in self._by_name:
                            self._by_name[name] = []
                        self._by_name[name].append(ti)

                    except Exception:
                        pass
                wb.close()
            except Exception as e:
                print(f"    警告: 无法读取 {rel}: {e}")

        print(f"  发现 {len(xlsx_files)} 个文件, {len(self.tables)} 个 Sheet")

    def get_ids(self, rel_path, sheet, col="id"):
        """获取指定表+列的 ID 集合"""
        key = (rel_path, sheet, col)
        if key in self.id_cache:
            return self.id_cache[key]

        full = os.path.join(self.config_dir, rel_path)
        if not os.path.exists(full):
            self.id_cache[key] = set()
            return set()

        try:
            _, headers_en, _, data_rows = read_sheet_data(full, sheet)
            if headers_en is None:
                self.id_cache[key] = set()
                return set()
            col_idx = None
            for i, h in enumerate(headers_en):
                if h and h.strip().lower() == col.lower():
                    col_idx = i
                    break
            if col_idx is None:
                self.id_cache[key] = set()
                return set()
            ids = extract_id_set(data_rows, col_idx)
            self.id_cache[key] = ids
            return ids
        except Exception:
            self.id_cache[key] = set()
            return set()

    def find_table_by_name(self, name):
        """根据 sheet 名称查找表"""
        return self._by_name.get(name.lower(), [])


# ---------------------------------------------------------------------------
# 自动规则生成
# ---------------------------------------------------------------------------

# column_name_pattern -> [(target_sheet_pattern, target_col, value_type_override)]
# 匹配优先级：按列表顺序，先匹配先生效
# target_sheet_pattern 支持精确匹配和模糊匹配

AUTO_REFERENCE_PATTERNS = [
    # ====== Item 道具引用 ======
    # 单值道具 ID
    (r"item_id\d*$", [
        ("itemconfig", "id", None),
    ]),
    (r"item_\d+$", [
        ("itemconfig", "id", None),
    ]),
    (r"cost_\d+_id$", [
        ("itemconfig", "id", None),
    ]),
    (r"reward_id$", [
        ("itemconfig", "id", None),
    ]),
    (r"reward_\d+$", [
        ("itemconfig", "id", None),
    ]),
    (r"exp_item_id$", [
        ("itemconfig", "id", None),
    ]),
    (r"fragment_id$", [
        ("itemconfig", "id", None),
    ]),
    (r"universal_item_id$", [
        ("itemconfig", "id", None),
    ]),
    (r"score_item_id$", [
        ("itemconfig", "id", None),
    ]),
    (r"produce_output_id$", [
        ("itemconfig", "id", None),
    ]),
    (r"generate_item_\d$", [
        ("itemconfig", "id", None),
    ]),
    (r"cure_item_\d$", [
        ("itemconfig", "id", None),
    ]),
    (r"exclusive_gift_id$", [
        ("giftpackconfig", "id", None),
    ]),

    # 数组型道具奖励/消耗
    (r"reward_items$", [
        ("itemconfig", "id", None),
    ]),
    (r"cost_items$", [
        ("itemconfig", "id", None),
    ]),
    (r"extra_rewards$", [
        ("itemconfig", "id", None),
    ]),
    (r"upgrade_rewards$", [
        ("itemconfig", "id", None),
    ]),
    (r"config_rewards$", [
        ("itemconfig", "id", None),
    ]),
    (r"daily_gift$", [
        ("itemconfig", "id", None),
    ]),
    (r"event_cost$", [
        ("itemconfig", "id", None),
    ]),
    (r"^rewards$", [
        ("itemconfig", "id", None),
    ]),
    (r"produce_cost$", [
        ("itemconfig", "id", None),
    ]),

    # ====== Science 科技引用 ======
    (r"science_node$", [
        ("sciencenode", "id", None),
    ]),
    (r"pre_nodes$", [
        ("sciencenode", "id", None),
    ]),
    (r"tree_id$", [
        ("sciencemenu", "id", None),
    ]),

    # ====== Skill 技能引用 ======
    (r"bullet_id$", [
        ("bullet", "id", None),
    ]),
    (r"skill_id1$", [
        ("skill", "skill_id", None),
    ]),
    (r"skill_id2$", [
        ("skill", "skill_id", None),
    ]),
    (r"skill_ids$", [
        ("skill", "skill_id", None),
    ]),
    (r"unique_skill_id$", [
        ("skill", "skill_id", None),
    ]),
    (r"skill_id$", [
        ("skill", "id", None),
    ]),
    (r"gift_id$", [
        ("skill_talent", "id", None),
    ]),

    # ====== Card/Hero 英雄引用 ======
    (r"hero_id$", [
        ("cardconfig", "id", None),
    ]),
    (r"unit_id$", [
        ("unitsconfig", "id", None),
    ]),

    # ====== Building 建筑引用 ======
    (r"father_building$", [
        ("buildingconfig", "id", None),
    ]),
    (r"population_work_type$", [
        ("populationworktype", "id", None),
    ]),

    # ====== Era 时代引用 ======
    (r"^era_id$", [
        ("eraconfig", "id", None),
    ]),
    (r"sub_era_id$", [
        ("suberaconfig", "id", None),
    ]),
    (r"^era$", [
        ("eraconfig", "id", None),
    ]),

    # ====== Draw 抽卡引用 ======
    (r"default_pool$", [
        ("drawpool", "pool_id", None),
    ]),
    (r"draw_rule_group$", [
        ("customizedpool", "id", None),
    ]),
    (r"guaranteed_rule_group$", [
        ("guaranteedrule", "group_id", None),
    ]),
    (r"pool_id$", [
        ("drawpool", "id", None),
    ]),
    (r"reward_group_id$", [
        ("rewardgroup", "reward_group_id", None),
    ]),

    # ====== Stage 关卡引用 ======
    (r"stage_id$", [
        ("stage", "id", None),
    ]),

    # ====== Guide 引导/剧情引用 ======
    (r"timelineid$", [
        ("storytimeline", "id", None),
    ]),
    (r"storyid$", [
        ("storymain", "id", None),
    ]),
    (r"story_id_after$", [
        ("storymain", "id", None),
    ]),
    (r"story_id$", [
        ("storymain", "id", None),
    ]),

    # ====== Mail 邮件引用 ======
    (r"tab_id$", [
        ("mailtabconfig", "id", None),
    ]),

    # ====== Ranking 排行榜引用 ======
    (r"reward_group_id$", [
        ("rankingreward", "id", None),
    ]),

    # ====== Function 功能解锁引用 ======
    (r"function_id$", [
        ("functionconfig", "id", None),
    ]),
    (r"unlock_functions$", [
        ("functionconfig", "id", None),
    ]),

    # ====== Activity 活动引用 ======
    (r"task_tab_group_id$", [
        ("sevendaystasktab", "id", None),
    ]),
    (r"score_reward_group_id$", [
        ("sevendaystaskscorereward", "id", None),
    ]),

    # ====== Shop 引用 ======
    (r"pack_group_id$", [
        ("giftpackconfig", "group_id", None),
    ]),

    # ====== Soldier 士兵引用 ======
    (r"barrack_level$", [
        ("barrackconfig", "id", None),
    ]),
    (r"tool_id$", [
        ("toolconfig", "id", None),
    ]),

    # ====== Audio 音频引用 ======
    (r"audio_ids$", [
        ("audioconfig", "id", None),
    ]),

    # ====== Attr 属性引用 ======
    (r"attr_effect$", [
        ("attr", "id", None),
    ]),

    # ====== 自引用（前置/父节点） ======
    (r"fore_id$", [
        (None, "id", None),
    ]),
]


def _should_skip_column(col_name):
    """判断列是否应该跳过自动校验"""
    for pat in SKIP_COLUMN_PATTERNS:
        if re.match(pat, col_name, re.IGNORECASE):
            return True
    return False


def _match_column(col_name, col_type, source_sheet_name):
    """
    根据列名和类型，返回匹配的目标表列表。
    返回 [(target_sheet_name, target_col, value_type), ...]
    """
    results = []
    cn = col_name.lower().replace("_", "")

    # 跳过非 ID 引用列
    if _should_skip_column(col_name):
        return results

    # 只处理 int 相关类型
    if "int" not in col_type.lower():
        return results

    # 按列名模式匹配
    for pattern, targets in AUTO_REFERENCE_PATTERNS:
        if re.search(pattern, cn, re.IGNORECASE):
            for tgt_sheet, tgt_col, vt in targets:
                if tgt_sheet is None:
                    tgt_sheet = source_sheet_name.lower()
                results.append((tgt_sheet, tgt_col, vt))
            break  # 只匹配第一个规则

    return results


def _deduplicate_rules(rules):
    """去重规则"""
    seen = set()
    result = []
    for r in rules:
        key = (r["source_file"], r["source_sheet"], r["source_col"],
               r["target_file"], r["target_sheet"], r["target_col"])
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result


def auto_generate_rules(registry):
    """
    自动扫描所有表，生成校验规则。
    返回规则列表（与手动规则格式一致）。
    """
    print("  自动生成校验规则...")
    rules = []
    stats = {"总列数": 0, "生成规则": 0, "跳过列": 0}

    for ti in registry.tables:
        for col_name, col_info in ti.columns.items():
            stats["总列数"] += 1
            col_type = col_info["type"]

            if _should_skip_column(col_name):
                stats["跳过列"] += 1
                continue

            if "int" not in col_type.lower():
                stats["跳过列"] += 1
                continue

            source_sheet_lower = ti.sheet_name.lower()
            matches = _match_column(col_name, col_type, source_sheet_lower)

            if not matches:
                stats["跳过列"] += 1
                continue

            for tgt_sheet_name, tgt_col, vt in matches:
                # 查找目标表
                candidates = registry.find_table_by_name(tgt_sheet_name)
                if not candidates:
                    continue

                tgt = candidates[0]  # 取第一个匹配

                # 确定 value_type
                if vt:
                    value_type = vt
                elif "int[][]" in col_type.lower():
                    value_type = "int[][]"
                elif "int[]" in col_type.lower():
                    value_type = "int[]"
                else:
                    value_type = "int"

                rule = {
                    "source_file": ti.rel_path,
                    "source_sheet": ti.sheet_name,
                    "source_col": col_name,
                    "target_file": tgt.rel_path,
                    "target_sheet": tgt.sheet_name,
                    "target_col": tgt_col,
                    "value_type": value_type,
                    "description": f"[自动] {ti.sheet_name}.{col_name} → {tgt.sheet_name}.{tgt_col}",
                }
                rules.append(rule)
                stats["生成规则"] += 1

    rules = _deduplicate_rules(rules)
    print(f"  列数: {stats['总列数']}, 生成规则: {stats['生成规则']}, 跳过: {stats['跳过列']}")
    return rules, stats


# ---------------------------------------------------------------------------
# 手动规则（覆盖/补充自动规则的不足）
# ---------------------------------------------------------------------------

MANUAL_RULES = [
    # ==================== Item 道具引用 ====================
    # GiftPack 礼包
    {"source_file": "public/GiftPack/GiftPackConfig.xlsx", "source_sheet": "GiftPackConfig", "source_col": "cost_items", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "礼包-消耗道具 → ItemConfig"},
    {"source_file": "public/GiftPack/GiftPackConfig.xlsx", "source_sheet": "GiftPackConfig", "source_col": "reward_items", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "礼包-基础奖励 → ItemConfig"},
    {"source_file": "public/GiftPack/GiftPackConfig.xlsx", "source_sheet": "GiftPackConfig", "source_col": "extra_rewards", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "礼包-附加奖励 → ItemConfig"},
    # Shop 商店
    {"source_file": "public/Shop/ShopConfig.xlsx", "source_sheet": "GoodsConfig", "source_col": "cost_items", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "商店商品-消耗道具 → ItemConfig"},
    {"source_file": "public/Shop/ShopConfig.xlsx", "source_sheet": "GoodsConfig", "source_col": "reward_items", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "商店商品-奖励道具 → ItemConfig"},
    # Draw 抽卡
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "cost_1_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "抽卡-单抽消耗 → ItemConfig"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "cost_10_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "抽卡-十连消耗 → ItemConfig"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "reward_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "抽卡-单抽奖励道具 → ItemConfig"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "RewardGroup", "source_col": "item_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "抽卡-奖励组道具 → ItemConfig"},
    # Card 英雄
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardConfig", "source_col": "item_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "英雄-道具ID → ItemConfig"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardConfig", "source_col": "fragment_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "英雄-碎片ID → ItemConfig"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardLevelConfig", "source_col": "exp_item_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "英雄升级-经验道具 → ItemConfig"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardStarConfig", "source_col": "universal_item_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "英雄升星-通用道具 → ItemConfig"},
    # Building 建筑
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "item_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑-消耗道具1 → ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "item_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑-消耗道具2 → ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "item_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑-消耗道具3 → ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "item_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑-消耗道具4 → ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "item_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑等级-升级道具1 → ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "item_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑等级-升级道具2 → ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "item_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑等级-升级道具3 → ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "item_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑等级-升级道具4 → ItemConfig"},
    # Soldier 士兵
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "generate_item_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-生产消耗道具1 → ItemConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "generate_item_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-生产消耗道具2 → ItemConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "generate_item_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-生产消耗道具3 → ItemConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "generate_item_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-生产消耗道具4 → ItemConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "cure_item_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-治疗消耗道具1 → ItemConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "cure_item_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-治疗消耗道具2 → ItemConfig"},
    # Tower 爬塔
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励1 → ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励2 → ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励3 → ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励4 → ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id5", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励5 → ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id6", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励6 → ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id7", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励7 → ItemConfig"},
    # Task 任务
    {"source_file": "public/Task/TaskConfig.xlsx", "source_sheet": "TaskConfig", "source_col": "reward_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "任务-奖励1 → ItemConfig"},
    {"source_file": "public/Task/TaskConfig.xlsx", "source_sheet": "TaskConfig", "source_col": "reward_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "任务-奖励2 → ItemConfig"},
    {"source_file": "public/Task/TaskConfig.xlsx", "source_sheet": "TaskConfig", "source_col": "reward_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "任务-奖励3 → ItemConfig"},
    {"source_file": "public/Task/TaskConfig.xlsx", "source_sheet": "TaskConfig", "source_col": "reward_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "任务-奖励4 → ItemConfig"},
    {"source_file": "public/Task/TaskConfig.xlsx", "source_sheet": "TaskConfig", "source_col": "reward_5", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "任务-奖励5 → ItemConfig"},
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "reward_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "章节任务-奖励1 → ItemConfig"},
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "reward_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "章节任务-奖励2 → ItemConfig"},
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "reward_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "章节任务-奖励3 → ItemConfig"},
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "reward_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "章节任务-奖励4 → ItemConfig"},
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "reward_5", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "章节任务-奖励5 → ItemConfig"},
    # Mail 邮件
    {"source_file": "public/Mail/MailConfig.xlsx", "source_sheet": "MailConfig", "source_col": "config_rewards", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "邮件-配置奖励 → ItemConfig"},
    # VIP
    {"source_file": "public/VIP/VipConfig.xlsx", "source_sheet": "VipLevelConfig", "source_col": "upgrade_rewards", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "VIP-升级奖励 → ItemConfig"},
    {"source_file": "public/VIP/VipConfig.xlsx", "source_sheet": "VipLevelConfig", "source_col": "daily_gift", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "VIP-每日礼包 → ItemConfig"},
    # Activity 活动
    {"source_file": "public/Activity/ActivitySevenDaysTask.xlsx", "source_sheet": "ActivitySevenDaysTask", "source_col": "score_item_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "七天活动-积分道具 → ItemConfig"},
    # Science 科技
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "item_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "科技节点-消耗资源1 → ItemConfig"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "item_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "科技节点-消耗资源2 → ItemConfig"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "item_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "科技节点-消耗资源3 → ItemConfig"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "item_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "科技节点-消耗资源4 → ItemConfig"},
    # Field 地块
    {"source_file": "public/Field/EventConfig.xlsx", "source_sheet": "EventLab", "source_col": "event_cost", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "地块事件-事件消耗 → ItemConfig"},
    {"source_file": "public/Field/EventConfig.xlsx", "source_sheet": "EventLab", "source_col": "rewards", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "地块事件-奖励 → ItemConfig"},
    # ResourceBuilding
    {"source_file": "public/Buildings/ResourceBuildingConfig.xlsx", "source_sheet": "ResourceBuildingConfig", "source_col": "produce_output_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "资源建筑-产出资源ID → ItemConfig"},
    {"source_file": "public/Buildings/ResourceBuildingConfig.xlsx", "source_sheet": "ResourceBuildingConfig", "source_col": "produce_cost", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[]", "description": "资源建筑-生产消耗 → ItemConfig"},

    # ==================== Science 科技引用 ====================
    {"source_file": "public/ToolConfig/ToolConfig.xlsx", "source_sheet": "ToolConfig", "source_col": "science_node", "target_file": "public/ScienceConfig/ScienceConfig.xlsx", "target_sheet": "ScienceNode", "value_type": "int", "description": "工具-科研节点 → ScienceNode"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "pre_nodes", "target_file": "public/ScienceConfig/ScienceConfig.xlsx", "target_sheet": "ScienceNode", "value_type": "int[]", "description": "科技节点-前置节点 → ScienceNode"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "tree_id", "target_file": "public/ScienceConfig/ScienceConfig.xlsx", "target_sheet": "ScienceMenu", "value_type": "int", "description": "科技节点-所属目录 → ScienceMenu"},

    # ==================== Building 建筑引用 ====================
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "father_building", "target_file": "public/Buildings/BuildingConfig.xlsx", "target_sheet": "BuildingConfig", "value_type": "int", "description": "建筑-父建筑 → BuildingConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "group_id", "target_file": "public/Buildings/BuildingConfig.xlsx", "target_sheet": "BuildingConfig", "target_col": "group_id", "value_type": "int", "description": "建筑等级-参数组ID → BuildingConfig.group_id"},

    # ==================== Card 英雄引用 ====================
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardConfig", "source_col": "skill_ids", "target_file": "public/Battle/Skill.xlsx", "target_sheet": "skill", "target_col": "skill_id", "value_type": "int[]", "description": "英雄-技能列表 → Skill.skill_id"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardConfig", "source_col": "unique_skill_id", "target_file": "public/Battle/Skill.xlsx", "target_sheet": "skill", "target_col": "skill_id", "value_type": "int", "description": "英雄-专属技能 → Skill.skill_id"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardLevelConfig", "source_col": "template_id", "target_file": "public/Card/CardConfig.xlsx", "target_sheet": "CardConfig", "target_col": "level_growth_id", "value_type": "int", "description": "英雄等级-模板ID → CardConfig.level_growth_id"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardConfig", "source_col": "unit_id", "target_file": "client/ArtAsset/UnitsConfig.xlsx", "target_sheet": "UnitsConfig", "value_type": "int", "description": "英雄-模型编号 → UnitsConfig"},
    {"source_file": "public/Activity/ActivitySevenDaysTask.xlsx", "source_sheet": "ActivitySevenDaysTask", "source_col": "hero_id", "target_file": "public/Card/CardConfig.xlsx", "target_sheet": "CardConfig", "value_type": "int", "description": "七天活动-跳转英雄 → CardConfig"},

    # ==================== Draw 抽卡引用 ====================
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "default_pool", "target_file": "public/Draw/Draw.xlsx", "target_sheet": "DrawPool", "target_col": "pool_id", "value_type": "int", "description": "抽卡-默认奖池 → DrawPool.pool_id"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "draw_rule_group", "target_file": "public/Draw/Draw.xlsx", "target_sheet": "CustomizedPool", "value_type": "int", "description": "抽卡-定制奖池组 → CustomizedPool"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "guaranteed_rule_group", "target_file": "public/Draw/Draw.xlsx", "target_sheet": "GuaranteedRule", "target_col": "group_id", "value_type": "int", "description": "抽卡-保底规则组 → GuaranteedRule.group_id"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "DrawPool", "source_col": "reward_group_id", "target_file": "public/Draw/Draw.xlsx", "target_sheet": "RewardGroup", "target_col": "reward_group_id", "value_type": "int", "description": "抽卡池-奖励组 → RewardGroup.reward_group_id"},

    # ==================== Era 时代引用 ====================
    {"source_file": "public/Era/EraConfig.xlsx", "source_sheet": "SubEraConfig", "source_col": "era_id", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "EraConfig", "value_type": "int", "description": "子时代-所属大时代 → EraConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "era", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "EraConfig", "value_type": "int", "description": "建筑-所属大时代 → EraConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "era", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "EraConfig", "value_type": "int", "description": "建筑等级-所属大时代 → EraConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "era", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "EraConfig", "value_type": "int", "description": "士兵-所属大时代 → EraConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "ArmsConfig", "source_col": "time", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "EraConfig", "value_type": "int", "description": "兵种-所属时代 → EraConfig"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "sub_era_id", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "SubEraConfig", "value_type": "int", "description": "科技节点-小时代ID → SubEraConfig"},

    # ==================== Soldier 士兵引用 ====================
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "ArmsConfig", "source_col": "skill_id", "target_file": "public/Battle/Skill.xlsx", "target_sheet": "skill", "target_col": "id", "value_type": "int[]", "description": "兵种-被动技能 → Skill.id"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "ArmsConfig", "source_col": "gift_id", "target_file": "public/Battle/SkillTalent.xlsx", "target_sheet": "skill_talent", "value_type": "int", "description": "兵种-天赋ID → SkillTalent"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "ArmsConfig", "source_col": "unit_id", "target_file": "client/ArtAsset/UnitsConfig.xlsx", "target_sheet": "UnitsConfig", "value_type": "int", "description": "兵种-模型ID → UnitsConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "ArmsConfig", "source_col": "tool_id", "target_file": "public/ToolConfig/ToolConfig.xlsx", "target_sheet": "ToolConfig", "value_type": "int", "description": "兵种-工具ID → ToolConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "barrack_level", "target_file": "public/Buildings/BarrackConfig.xlsx", "target_sheet": "BarrackConfig", "value_type": "int", "description": "士兵-兵营等级 → BarrackConfig"},

    # ==================== Battle 战斗引用 ====================
    {"source_file": "public/Battle/Skill.xlsx", "source_sheet": "skill", "source_col": "bullet_id", "target_file": "public/Battle/Bullet.xlsx", "target_sheet": "Bullet", "value_type": "int", "description": "技能-子弹ID → Bullet"},
    {"source_file": "public/Battle/Skill.xlsx", "source_sheet": "skill", "source_col": "skill_id1", "target_file": "public/Battle/Skill.xlsx", "target_sheet": "skill", "target_col": "skill_id", "value_type": "int", "description": "技能-关联技能1 → Skill.skill_id"},
    {"source_file": "public/Battle/Skill.xlsx", "source_sheet": "skill", "source_col": "skill_id2", "target_file": "public/Battle/Skill.xlsx", "target_sheet": "skill", "target_col": "skill_id", "value_type": "int", "description": "技能-关联技能2 → Skill.skill_id"},

    # ==================== Tower 爬塔引用 ====================
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "stage_id", "target_file": "public/Stage.xlsx", "target_sheet": "Stage", "value_type": "int", "description": "爬塔-关卡ID → Stage"},

    # ==================== Guide 引导引用 ====================
    {"source_file": "public/Guide/Guide.xlsx", "source_sheet": "Guide", "source_col": "timeLineId", "target_file": "public/Guide/Timeline.xlsx", "target_sheet": "StoryTimeline", "value_type": "int", "description": "新手引导-TimelineID → StoryTimeline"},
    {"source_file": "public/Guide/Guide.xlsx", "source_sheet": "Guide", "source_col": "storyId", "target_file": "public/Guide/Story.xlsx", "target_sheet": "StoryMain", "value_type": "int", "description": "新手引导-剧情ID → StoryMain"},

    # ==================== Field 地块事件引用 ====================
    {"source_file": "public/Field/EventConfig.xlsx", "source_sheet": "EventLab", "source_col": "story_id", "target_file": "public/Guide/Story.xlsx", "target_sheet": "StoryMain", "value_type": "int", "description": "地块事件-剧情ID → StoryMain"},
    {"source_file": "public/Field/EventConfig.xlsx", "source_sheet": "EventLab", "source_col": "story_id_after", "target_file": "public/Guide/Story.xlsx", "target_sheet": "StoryMain", "value_type": "int", "description": "地块事件-领取后剧情ID → StoryMain"},
    {"source_file": "public/Field/EventConfig.xlsx", "source_sheet": "EventLab", "source_col": "fore_id", "target_file": "public/Field/EventConfig.xlsx", "target_sheet": "EventLab", "value_type": "int", "description": "地块事件-前置事件 → EventLab"},

    # ==================== Mail 邮件引用 ====================
    {"source_file": "public/Mail/MailConfig.xlsx", "source_sheet": "MailConfig", "source_col": "tab_id", "target_file": "public/Mail/MailConfig.xlsx", "target_sheet": "MailTabConfig", "value_type": "int", "description": "邮件-所属页签 → MailTabConfig"},

    # ==================== Ranking 排行榜引用 ====================
    {"source_file": "public/Ranking/RankingConfig.xlsx", "source_sheet": "RankingConfig", "source_col": "reward_group_id", "target_file": "public/Ranking/RankingConfig.xlsx", "target_sheet": "RankingReward", "value_type": "int", "description": "排行榜-奖励组 → RankingReward"},

    # ==================== VIP 引用 ====================
    {"source_file": "public/VIP/VipConfig.xlsx", "source_sheet": "VipLevelConfig", "source_col": "exclusive_gift_id", "target_file": "public/GiftPack/GiftPackConfig.xlsx", "target_sheet": "GiftPackConfig", "value_type": "int", "description": "VIP-专属礼包 → GiftPackConfig"},
    {"source_file": "public/VIP/VipConfig.xlsx", "source_sheet": "VipLevelConfig", "source_col": "unlock_functions", "target_file": "public/Common/FunctionConfig.xlsx", "target_sheet": "FunctionConfig", "value_type": "int[]", "description": "VIP-功能解锁 → FunctionConfig"},

    # ==================== Activity 活动引用 ====================
    {"source_file": "public/Activity/ActivitySevenDaysTask.xlsx", "source_sheet": "ActivitySevenDaysTask", "source_col": "task_tab_group_id", "target_file": "public/Activity/ActivitySevenDaysTask.xlsx", "target_sheet": "SevenDaysTaskTab", "value_type": "int", "description": "七天活动-任务标签组 → SevenDaysTaskTab"},
    {"source_file": "public/Activity/ActivitySevenDaysTask.xlsx", "source_sheet": "ActivitySevenDaysTask", "source_col": "score_reward_group_id", "target_file": "public/Activity/ActivitySevenDaysTask.xlsx", "target_sheet": "SevenDaysTaskScoreReward", "value_type": "int", "description": "七天活动-积分奖励组 → SevenDaysTaskScoreReward"},

    # ==================== Shop 商店引用 ====================
    {"source_file": "public/GiftPack/GiftPackStore.xlsx", "source_sheet": "GiftPackStore", "source_col": "function_id", "target_file": "public/Common/FunctionConfig.xlsx", "target_sheet": "FunctionConfig", "value_type": "int", "description": "礼包商店-功能ID → FunctionConfig"},
    {"source_file": "public/GiftPack/GiftPackStore.xlsx", "source_sheet": "GiftPackStore", "source_col": "pack_group_id", "target_file": "public/GiftPack/GiftPackConfig.xlsx", "target_sheet": "GiftPackConfig", "target_col": "group_id", "value_type": "int", "description": "礼包商店-礼包组 → GiftPackConfig.group_id"},

    # ==================== Population 人口引用 ====================
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "population_work_type", "target_file": "public/Population/PopulationWorkType.xlsx", "target_sheet": "PopulationWorkType", "value_type": "int", "description": "建筑-工作类型 → PopulationWorkType"},

    # ==================== Task 任务引用 ====================
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "group", "target_file": "public/Task/TaskConfig.xlsx", "target_sheet": "TaskConfig", "target_col": "group", "value_type": "int", "description": "章节任务-任务组 → TaskConfig.group"},
]


# ---------------------------------------------------------------------------
# 校验器
# ---------------------------------------------------------------------------

class ConfigValidator:
    def __init__(self, config_dir, rules, registry):
        self.config_dir = config_dir
        self.rules = rules
        self.registry = registry
        self.errors = []
        self.warnings = []

    def _get_full_path(self, rel_path):
        return os.path.join(self.config_dir, rel_path)

    def validate_rule(self, rule):
        """校验单条规则"""
        source_file = rule["source_file"]
        source_sheet = rule["source_sheet"]
        source_col = rule["source_col"]
        target_file = rule["target_file"]
        target_sheet = rule["target_sheet"]
        target_col = rule.get("target_col", "id")
        value_type = rule.get("value_type", "int")
        description = rule.get("description", "")

        # 跳过自引用（source == target 且 source_col == target_col）
        if source_file == target_file and source_sheet == target_sheet and source_col == target_col:
            return

        # 加载目标 ID 集合
        target_ids = self.registry.get_ids(target_file, target_sheet, target_col)
        if not target_ids and not os.path.exists(self._get_full_path(target_file)):
            return

        # 读取源表数据
        full_path = self._get_full_path(source_file)
        if not os.path.exists(full_path):
            self.warnings.append(f"源文件不存在: {source_file}")
            return

        try:
            _, headers_en, _, data_rows = read_sheet_data(full_path, source_sheet)
            if headers_en is None:
                self.warnings.append(f"源 Sheet 不存在: {source_file} / {source_sheet}")
                return

            col_idx = None
            for i, h in enumerate(headers_en):
                if h and h.strip().lower() == source_col.lower():
                    col_idx = i
                    break
            if col_idx is None:
                self.warnings.append(f"源列 '{source_col}' 不存在: {source_file} / {source_sheet}")
                return

            for row_idx, row in enumerate(data_rows):
                if col_idx >= len(row):
                    continue
                val = row[col_idx]
                ref_ids = self._extract_ref_ids(val, value_type)

                if not ref_ids:
                    continue

                source_row_id = row[0] if len(row) > 0 else f"行{row_idx + 4}"

                for ref_id in ref_ids:
                    if ref_id not in target_ids:
                        self.errors.append(
                            f"[{description}] {source_file} / {source_sheet} "
                            f"行ID={source_row_id} 列={source_col} 引用了不存在的ID: {ref_id} "
                            f"(目标表: {target_file} / {target_sheet}.{target_col})"
                        )
        except Exception as e:
            self.warnings.append(f"校验异常: {source_file} / {source_sheet} / {source_col}: {e}")

    def _extract_ref_ids(self, val, value_type):
        if val is None or str(val).strip() == "":
            return set()
        s = str(val).strip()
        if value_type in ("int[][]", "int[]"):
            return parse_int_array(s)
        elif value_type == "int":
            try:
                return {int(s)}
            except ValueError:
                return set()
        else:
            return parse_int_array(s)

    def run(self, verbose=False, report_path=None):
        print("=" * 70)
        print("  配置表交叉校验工具 (自动检测模式)")
        print("=" * 70)
        print(f"\n校验规则: {len(self.rules)} 条\n")

        # 预加载目标表
        target_keys = set()
        for rule in self.rules:
            key = (rule["target_file"], rule["target_sheet"], rule.get("target_col", "id"))
            target_keys.add(key)

        for key in target_keys:
            if verbose:
                print(f"  预加载: {key[0]} / {key[1]}.{key[2]} ...")
            self.registry.get_ids(*key)

        # 逐条校验
        total = len(self.rules)
        for i, rule in enumerate(self.rules):
            if verbose:
                desc = rule.get("description", "")
                print(f"  [{i+1}/{total}] {desc} ...")
            self.validate_rule(rule)

        if report_path is None:
            report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validate_report.md")
        self._generate_report(report_path)

    def _generate_report(self, report_path):
        lines = []
        lines.append("# 配置表交叉校验报告\n")
        lines.append("## 摘要\n")
        lines.append(f"- 校验规则数: {len(self.rules)}")
        lines.append(f"- 错误数: {len(self.errors)}")
        lines.append(f"- 警告数: {len(self.warnings)}")
        lines.append("")

        if self.errors:
            lines.append(f"## 错误 ({len(self.errors)})\n")
            lines.append("| # | 描述 | 源文件 | 源行ID | 源列 | 无效引用ID | 目标表 |")
            lines.append("|---|------|--------|--------|------|------------|--------|")
            for i, err in enumerate(self.errors, 1):
                parts = err.split(" (目标表: ")
                main_part = parts[0]
                target_part = parts[1].rstrip(")") if len(parts) > 1 else ""
                desc_match = re.match(
                    r'\[(.*?)\]\s+(.*?)\s+/\s+(.*?)\s+行ID=(.*?)\s+列=(.*?)\s+引用了不存在的ID:\s+(\d+)',
                    main_part)
                if desc_match:
                    lines.append(
                        f"| {i} | {desc_match.group(1)} | {desc_match.group(2)}/{desc_match.group(3)} "
                        f"| {desc_match.group(4)} | {desc_match.group(5)} | {desc_match.group(6)} | {target_part} |")
                else:
                    lines.append(f"| {i} | - | - | - | - | - | {err} |")
            lines.append("")

        if self.warnings:
            lines.append(f"## 警告 ({len(self.warnings)})\n")
            for w in self.warnings:
                lines.append(f"- {w}")
            lines.append("")

        if not self.errors and not self.warnings:
            lines.append("## 结果\n")
            lines.append("所有校验均通过，未发现配置表引用错误。\n")

        report = "\n".join(lines)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        print("\n" + "=" * 70)
        print(f"  校验完成")
        print(f"  错误: {len(self.errors)}  警告: {len(self.warnings)}")
        print(f"  报告已保存至: {report_path}")
        print("=" * 70)

        if self.errors:
            print("\n--- 错误列表 ---")
            for err in self.errors[:50]:
                print(f"  [ERROR] {err}")
            if len(self.errors) > 50:
                print(f"  ... 还有 {len(self.errors) - 50} 条错误，详见报告")

        if self.warnings:
            print("\n--- 警告列表 ---")
            for w in self.warnings:
                print(f"  [WARN]  {w}")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="配置表交叉校验工具（自动检测模式）")
    parser.add_argument("-c", "--config-dir", default=DEFAULT_CONFIG_DIR,
                        help=f"配置表所在目录（默认: {DEFAULT_CONFIG_DIR}）")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细输出")
    parser.add_argument("-o", "--output", default=None, help="报告输出路径（默认: 工具目录下 validate_report.md）")
    parser.add_argument("--no-auto", action="store_true", help="禁用自动检测，仅使用手动规则")
    args = parser.parse_args()

    config_dir = args.config_dir
    tool_dir = os.path.dirname(os.path.abspath(__file__))
    report_path = args.output if args.output else os.path.join(tool_dir, "validate_report.md")

    if not os.path.isdir(config_dir):
        print(f"错误: 配置目录不存在: {config_dir}")
        sys.exit(1)

    # 1. 扫描所有表
    registry = TableRegistry(config_dir)
    registry.discover()

    # 2. 生成规则
    if args.no_auto:
        rules = MANUAL_RULES
        print(f"\n使用手动规则: {len(rules)} 条")
    else:
        auto_rules, stats = auto_generate_rules(registry)
        # 合并手动规则（覆盖同 key 的自动规则）
        auto_dict = {}
        for r in auto_rules:
            k = (r["source_file"], r["source_sheet"], r["source_col"],
                 r["target_file"], r["target_sheet"], r["target_col"])
            auto_dict[k] = r
        for r in MANUAL_RULES:
            k = (r["source_file"], r["source_sheet"], r["source_col"],
                 r["target_file"], r["target_sheet"], r.get("target_col", "id"))
            auto_dict[k] = r
        rules = list(auto_dict.values())

    # 3. 执行校验
    validator = ConfigValidator(config_dir, rules, registry)
    validator.run(verbose=args.verbose, report_path=report_path)

    sys.exit(1 if validator.errors else 0)


if __name__ == "__main__":
    main()