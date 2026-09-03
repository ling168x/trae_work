#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
配置表交叉校验工具 v2.0
- 自动扫描所有 xlsx 配置表
- 根据列名和类型自动推断跨表引用关系
- 支持手动规则覆盖/补充
- 新增：主键重复检测、空值检测、数据格式校验
- 新增：报告按模块分组聚合，快速定位问题
"""

import os
import re
import sys
import glob
import time
from collections import defaultdict, OrderedDict
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
# 严重级别
# ---------------------------------------------------------------------------
class Severity:
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"


class Issue:
    """一条校验问题"""
    def __init__(self, severity, category, source_file, source_sheet,
                 description, details, row_ids=None, invalid_ids=None,
                 source_col="", target_info=""):
        self.severity = severity
        self.category = category          # "引用校验" / "主键重复" / "空值检测" / "格式校验"
        self.source_file = source_file
        self.source_sheet = source_sheet
        self.description = description
        self.details = details
        self.row_ids = row_ids or []
        self.invalid_ids = invalid_ids or []
        self.source_col = source_col
        self.target_info = target_info


# ---------------------------------------------------------------------------
# 数据读取
# ---------------------------------------------------------------------------

def read_sheet_data(filepath, sheet_name):
    """读取 sheet 数据，返回 (headers_cn, headers_en, types_row, data_rows)
    表头共 4 行: 中文名 / 字段名 / 数据类型 / 前后端标记，数据从第 5 行开始。
    """
    wb = load_workbook(filepath, read_only=True, data_only=True)
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if len(rows) < 5:
        return None, None, None, []

    headers_cn = [str(c) if c is not None else "" for c in rows[0]]
    headers_en = [str(c) if c is not None else "" for c in rows[1]]
    types_row  = [str(c) if c is not None else "" for c in rows[2]]
    # rows[3] = 前后端标记行（both / s / c 等），跳过
    data_rows  = [list(r) for r in rows[4:]]

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
    """解析 int[] 或 int[][] 类型，提取所有整型 ID（取每个子数组的第一个元素作为引用ID）"""
    ids = set()
    if val is None or str(val).strip() == "":
        return ids
    s = str(val).strip()
    if s.startswith("[["):
        # int[][] — 例如 [[1001,2],[1002,3]]，每个子数组第一个元素是引用ID
        inner_arrays = re.findall(r'\[(\d+(?:\s*,\s*\d+)*)\]', s)
        for arr_str in inner_arrays:
            nums = [x.strip() for x in arr_str.split(',')]
            if nums:
                try:
                    ids.add(int(nums[0]))
                except ValueError:
                    pass
    elif s.startswith("["):
        # int[] — 例如 [1001,1002,1003]
        matches = re.findall(r'\d+', s)
        for m in matches:
            ids.add(int(m))
    else:
        try:
            ids.add(int(s))
        except ValueError:
            pass
    return ids


def validate_int_format(val):
    """校验 int 类型值格式是否合法，返回 (is_valid, cleaned_value)"""
    if val is None or str(val).strip() == "":
        return True, None  # 空值另外检测
    s = str(val).strip()
    try:
        int(float(s))  # 允许 "1.0" 这种 excel 带出来的浮点
        return True, int(float(s))
    except (ValueError, TypeError):
        return False, s


def validate_array_format(val, expected_type):
    """校验 int[] / int[][] 格式是否合法"""
    if val is None or str(val).strip() == "":
        return True, []
    s = str(val).strip()
    errors = []

    if expected_type == "int[][]":
        # 应为 [[a,b],[c,d]] 格式
        if not (s.startswith("[[") and s.endswith("]]")) and not (s.startswith("[") and s.endswith("]")):
            errors.append(f"格式错误: 期望 int[][] 格式，实际值: {s[:50]}")
    elif expected_type == "int[]":
        if not (s.startswith("[") and s.endswith("]")):
            # 允许单个数值
            try:
                int(s)
            except ValueError:
                errors.append(f"格式错误: 期望 int[] 格式，实际值: {s[:50]}")

    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# 表注册中心
# ---------------------------------------------------------------------------

class TableInfo:
    """单个 sheet 的元信息"""
    def __init__(self, rel_path, xlsx_name, sheet_name):
        self.rel_path = rel_path
        self.xlsx_name = xlsx_name
        self.sheet_name = sheet_name
        self.pk_col = None
        self.pk_values = set()
        self.columns = {}          # col_name -> {"type": "int", "cn": "...", "col_idx": N}
        self.col_index = {}
        self.headers_cn = []
        self.headers_en = []
        self.types_row = []
        self.data_rows = []        # 缓存数据行用于额外检查
        self.row_count = 0

    def __repr__(self):
        return f"TableInfo({self.rel_path}/{self.sheet_name})"


class TableRegistry:
    """全局表注册中心：扫描所有 xlsx，建立索引"""
    def __init__(self, config_dir):
        self.config_dir = config_dir
        self.tables = []
        self.id_cache = {}
        self._by_name = {}

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
                        hcn, headers_en, types_row, data_rows = read_sheet_data(full, sn)
                        if headers_en is None or len(headers_en) == 0:
                            continue

                        ti = TableInfo(rel, os.path.basename(rel), sn)
                        ti.pk_col = headers_en[0] if headers_en[0] else "id"
                        ti.pk_values = extract_id_set(data_rows, 0)
                        ti.headers_cn = hcn or []
                        ti.headers_en = headers_en
                        ti.types_row = types_row
                        ti.data_rows = data_rows
                        ti.row_count = len(data_rows)

                        for ci, cn in enumerate(headers_en):
                            ct = types_row[ci] if ci < len(types_row) else ""
                            cc = hcn[ci] if hcn and ci < len(hcn) else ""
                            if cn and cn.strip():
                                cname = cn.strip().lower()
                                ti.columns[cname] = {
                                    "type": ct.strip().lower() if ct else "",
                                    "cn": cc.strip() if cc else "",
                                    "col_idx": ci,
                                }
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
        return self._by_name.get(name.lower(), [])


# ---------------------------------------------------------------------------
# 自动规则生成
# ---------------------------------------------------------------------------

AUTO_REFERENCE_PATTERNS = [
    # ====== Item 道具引用 ======
    (r"item_id\d*$", [("itemconfig", "id", None)]),
    (r"item_\d+$", [("itemconfig", "id", None)]),
    (r"cost_\d+_id$", [("itemconfig", "id", None)]),
    (r"reward_id$", [("itemconfig", "id", None)]),
    (r"reward_\d+$", [("itemconfig", "id", None)]),
    (r"exp_item_id$", [("itemconfig", "id", None)]),
    (r"fragment_id$", [("itemconfig", "id", None)]),
    (r"universal_item_id$", [("itemconfig", "id", None)]),
    (r"score_item_id$", [("itemconfig", "id", None)]),
    (r"produce_output_id$", [("itemconfig", "id", None)]),
    (r"generate_item_\d$", [("itemconfig", "id", None)]),
    (r"cure_item_\d$", [("itemconfig", "id", None)]),
    (r"exclusive_gift_id$", [("giftpackconfig", "id", None)]),
    (r"reward_items$", [("itemconfig", "id", None)]),
    (r"cost_items$", [("itemconfig", "id", None)]),
    (r"extra_rewards$", [("itemconfig", "id", None)]),
    (r"upgrade_rewards$", [("itemconfig", "id", None)]),
    (r"config_rewards$", [("itemconfig", "id", None)]),
    (r"daily_gift$", [("itemconfig", "id", None)]),
    (r"event_cost$", [("itemconfig", "id", None)]),
    (r"^rewards$", [("itemconfig", "id", None)]),
    (r"produce_cost$", [("itemconfig", "id", None)]),
    # ====== Science 科技引用 ======
    (r"science_node$", [("sciencenode", "id", None)]),
    (r"pre_nodes$", [("sciencenode", "id", None)]),
    (r"tree_id$", [("sciencemenu", "id", None)]),
    # ====== Skill 技能引用 ======
    (r"bullet_id$", [("bullet", "id", None)]),
    (r"skill_id1$", [("skill", "skill_id", None)]),
    (r"skill_id2$", [("skill", "skill_id", None)]),
    (r"skill_ids$", [("skill", "skill_id", None)]),
    (r"unique_skill_id$", [("skill", "skill_id", None)]),
    (r"skill_id$", [("skill", "id", None)]),
    (r"gift_id$", [("skill_talent", "id", None)]),
    # ====== Card/Hero 英雄引用 ======
    (r"hero_id$", [("cardconfig", "id", None)]),
    (r"unit_id$", [("unitsconfig", "id", None)]),
    # ====== Building 建筑引用 ======
    (r"father_building$", [("buildingconfig", "id", None)]),
    (r"population_work_type$", [("populationworktype", "id", None)]),
    # ====== Era 时代引用 ======
    (r"^era_id$", [("eraconfig", "id", None)]),
    (r"sub_era_id$", [("suberaconfig", "id", None)]),
    (r"^era$", [("eraconfig", "id", None)]),
    # ====== Draw 抽卡引用 ======
    (r"default_pool$", [("drawpool", "pool_id", None)]),
    (r"draw_rule_group$", [("customizedpool", "id", None)]),
    (r"guaranteed_rule_group$", [("guaranteedrule", "group_id", None)]),
    (r"pool_id$", [("drawpool", "id", None)]),
    (r"reward_group_id$", [("rewardgroup", "reward_group_id", None)]),
    # ====== Stage 关卡引用 ======
    (r"stage_id$", [("stage", "id", None)]),
    # ====== Guide 引导/剧情引用 ======
    (r"timelineid$", [("storytimeline", "id", None)]),
    (r"storyid$", [("storymain", "id", None)]),
    (r"story_id_after$", [("storymain", "id", None)]),
    (r"story_id$", [("storymain", "id", None)]),
    # ====== Mail 邮件引用 ======
    (r"tab_id$", [("mailtabconfig", "id", None)]),
    # ====== Ranking 排行榜引用 ======
    (r"reward_group_id$", [("rankingreward", "id", None)]),
    # ====== Function 功能解锁引用 ======
    (r"function_id$", [("functionconfig", "id", None)]),
    (r"unlock_functions$", [("functionconfig", "id", None)]),
    # ====== Activity 活动引用 ======
    (r"task_tab_group_id$", [("sevendaystasktab", "id", None)]),
    (r"score_reward_group_id$", [("sevendaystaskscorereward", "id", None)]),
    # ====== Shop 引用 ======
    (r"pack_group_id$", [("giftpackconfig", "group_id", None)]),
    # ====== Soldier 士兵引用 ======
    (r"barrack_level$", [("barrackconfig", "id", None)]),
    (r"tool_id$", [("toolconfig", "id", None)]),
    # ====== Audio 音频引用 ======
    (r"audio_ids$", [("audioconfig", "id", None)]),
    # ====== Attr 属性引用 ======
    (r"attr_effect$", [("attr", "id", None)]),
    # ====== 自引用（前置/父节点） ======
    (r"fore_id$", [(None, "id", None)]),
]


def _should_skip_column(col_name):
    for pat in SKIP_COLUMN_PATTERNS:
        if re.match(pat, col_name, re.IGNORECASE):
            return True
    return False


def _match_column(col_name, col_type, source_sheet_name):
    results = []
    cn = col_name.lower().replace("_", "")

    if _should_skip_column(col_name):
        return results
    if "int" not in col_type.lower():
        return results

    for pattern, targets in AUTO_REFERENCE_PATTERNS:
        if re.search(pattern, cn, re.IGNORECASE):
            for tgt_sheet, tgt_col, vt in targets:
                if tgt_sheet is None:
                    tgt_sheet = source_sheet_name.lower()
                results.append((tgt_sheet, tgt_col, vt))
            break

    return results


def _deduplicate_rules(rules):
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
                candidates = registry.find_table_by_name(tgt_sheet_name)
                if not candidates:
                    continue

                tgt = candidates[0]

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
                    "description": f"[自动] {ti.sheet_name}.{col_name} -> {tgt.sheet_name}.{tgt_col}",
                }
                rules.append(rule)
                stats["生成规则"] += 1

    rules = _deduplicate_rules(rules)
    print(f"  列数: {stats['总列数']}, 生成规则: {stats['生成规则']}, 跳过: {stats['跳过列']}")
    return rules, stats


# ---------------------------------------------------------------------------
# 手动规则
# ---------------------------------------------------------------------------

MANUAL_RULES = [
    # ==================== Item 道具引用 ====================
    {"source_file": "public/GiftPack/GiftPackConfig.xlsx", "source_sheet": "GiftPackConfig", "source_col": "cost_items", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "礼包-消耗道具 -> ItemConfig"},
    {"source_file": "public/GiftPack/GiftPackConfig.xlsx", "source_sheet": "GiftPackConfig", "source_col": "reward_items", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "礼包-基础奖励 -> ItemConfig"},
    {"source_file": "public/GiftPack/GiftPackConfig.xlsx", "source_sheet": "GiftPackConfig", "source_col": "extra_rewards", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "礼包-附加奖励 -> ItemConfig"},
    {"source_file": "public/Shop/ShopConfig.xlsx", "source_sheet": "GoodsConfig", "source_col": "cost_items", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "商店商品-消耗道具 -> ItemConfig"},
    {"source_file": "public/Shop/ShopConfig.xlsx", "source_sheet": "GoodsConfig", "source_col": "reward_items", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "商店商品-奖励道具 -> ItemConfig"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "cost_1_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "抽卡-单抽消耗 -> ItemConfig"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "cost_10_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "抽卡-十连消耗 -> ItemConfig"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "reward_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "抽卡-单抽奖励道具 -> ItemConfig"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "RewardGroup", "source_col": "item_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "抽卡-奖励组道具 -> ItemConfig"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardConfig", "source_col": "item_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "英雄-道具ID -> ItemConfig"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardConfig", "source_col": "fragment_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "英雄-碎片ID -> ItemConfig"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardLevelConfig", "source_col": "exp_item_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "英雄升级-经验道具 -> ItemConfig"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardStarConfig", "source_col": "universal_item_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "英雄升星-通用道具 -> ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "item_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑-消耗道具1 -> ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "item_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑-消耗道具2 -> ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "item_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑-消耗道具3 -> ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "item_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑-消耗道具4 -> ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "item_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑等级-升级道具1 -> ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "item_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑等级-升级道具2 -> ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "item_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑等级-升级道具3 -> ItemConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "item_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "建筑等级-升级道具4 -> ItemConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "generate_item_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-生产消耗道具1 -> ItemConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "generate_item_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-生产消耗道具2 -> ItemConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "generate_item_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-生产消耗道具3 -> ItemConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "generate_item_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-生产消耗道具4 -> ItemConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "cure_item_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-治疗消耗道具1 -> ItemConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "cure_item_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "士兵-治疗消耗道具2 -> ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励1 -> ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励2 -> ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励3 -> ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励4 -> ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id5", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励5 -> ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id6", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励6 -> ItemConfig"},
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "item_id7", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "爬塔-挂机奖励7 -> ItemConfig"},
    {"source_file": "public/Task/TaskConfig.xlsx", "source_sheet": "TaskConfig", "source_col": "reward_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "任务-奖励1 -> ItemConfig"},
    {"source_file": "public/Task/TaskConfig.xlsx", "source_sheet": "TaskConfig", "source_col": "reward_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "任务-奖励2 -> ItemConfig"},
    {"source_file": "public/Task/TaskConfig.xlsx", "source_sheet": "TaskConfig", "source_col": "reward_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "任务-奖励3 -> ItemConfig"},
    {"source_file": "public/Task/TaskConfig.xlsx", "source_sheet": "TaskConfig", "source_col": "reward_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "任务-奖励4 -> ItemConfig"},
    {"source_file": "public/Task/TaskConfig.xlsx", "source_sheet": "TaskConfig", "source_col": "reward_5", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "任务-奖励5 -> ItemConfig"},
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "reward_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "章节任务-奖励1 -> ItemConfig"},
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "reward_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "章节任务-奖励2 -> ItemConfig"},
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "reward_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "章节任务-奖励3 -> ItemConfig"},
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "reward_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "章节任务-奖励4 -> ItemConfig"},
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "reward_5", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "章节任务-奖励5 -> ItemConfig"},
    {"source_file": "public/Mail/MailConfig.xlsx", "source_sheet": "MailConfig", "source_col": "config_rewards", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "邮件-配置奖励 -> ItemConfig"},
    {"source_file": "public/VIP/VipConfig.xlsx", "source_sheet": "VipLevelConfig", "source_col": "upgrade_rewards", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "VIP-升级奖励 -> ItemConfig"},
    {"source_file": "public/VIP/VipConfig.xlsx", "source_sheet": "VipLevelConfig", "source_col": "daily_gift", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "VIP-每日礼包 -> ItemConfig"},
    {"source_file": "public/Activity/ActivitySevenDaysTask.xlsx", "source_sheet": "ActivitySevenDaysTask", "source_col": "score_item_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "七天活动-积分道具 -> ItemConfig"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "item_1", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "科技节点-消耗资源1 -> ItemConfig"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "item_2", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "科技节点-消耗资源2 -> ItemConfig"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "item_3", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "科技节点-消耗资源3 -> ItemConfig"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "item_4", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "科技节点-消耗资源4 -> ItemConfig"},
    {"source_file": "public/Field/EventConfig.xlsx", "source_sheet": "EventLab", "source_col": "event_cost", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "地块事件-事件消耗 -> ItemConfig"},
    {"source_file": "public/Field/EventConfig.xlsx", "source_sheet": "EventLab", "source_col": "rewards", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[][]", "description": "地块事件-奖励 -> ItemConfig"},
    {"source_file": "public/Buildings/ResourceBuildingConfig.xlsx", "source_sheet": "ResourceBuildingConfig", "source_col": "produce_output_id", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int", "description": "资源建筑-产出资源ID -> ItemConfig"},
    {"source_file": "public/Buildings/ResourceBuildingConfig.xlsx", "source_sheet": "ResourceBuildingConfig", "source_col": "produce_cost", "target_file": "public/Item/ItemConfig.xlsx", "target_sheet": "ItemConfig", "value_type": "int[]", "description": "资源建筑-生产消耗 -> ItemConfig"},
    # ==================== Science 科技引用 ====================
    {"source_file": "public/ToolConfig/ToolConfig.xlsx", "source_sheet": "ToolConfig", "source_col": "science_node", "target_file": "public/ScienceConfig/ScienceConfig.xlsx", "target_sheet": "ScienceNode", "value_type": "int", "description": "工具-科研节点 -> ScienceNode"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "pre_nodes", "target_file": "public/ScienceConfig/ScienceConfig.xlsx", "target_sheet": "ScienceNode", "value_type": "int[]", "description": "科技节点-前置节点 -> ScienceNode"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "tree_id", "target_file": "public/ScienceConfig/ScienceConfig.xlsx", "target_sheet": "ScienceMenu", "value_type": "int", "description": "科技节点-所属目录 -> ScienceMenu"},
    # ==================== Building 建筑引用 ====================
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "father_building", "target_file": "public/Buildings/BuildingConfig.xlsx", "target_sheet": "BuildingConfig", "value_type": "int", "description": "建筑-父建筑 -> BuildingConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "group_id", "target_file": "public/Buildings/BuildingConfig.xlsx", "target_sheet": "BuildingConfig", "target_col": "group_id", "value_type": "int", "description": "建筑等级-参数组ID -> BuildingConfig.group_id"},
    # ==================== Card 英雄引用 ====================
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardConfig", "source_col": "skill_ids", "target_file": "public/Battle/Skill.xlsx", "target_sheet": "skill", "target_col": "skill_id", "value_type": "int[]", "description": "英雄-技能列表 -> Skill.skill_id"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardConfig", "source_col": "unique_skill_id", "target_file": "public/Battle/Skill.xlsx", "target_sheet": "skill", "target_col": "skill_id", "value_type": "int", "description": "英雄-专属技能 -> Skill.skill_id"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardLevelConfig", "source_col": "template_id", "target_file": "public/Card/CardConfig.xlsx", "target_sheet": "CardConfig", "target_col": "level_growth_id", "value_type": "int", "description": "英雄等级-模板ID -> CardConfig.level_growth_id"},
    {"source_file": "public/Card/CardConfig.xlsx", "source_sheet": "CardConfig", "source_col": "unit_id", "target_file": "client/ArtAsset/UnitsConfig.xlsx", "target_sheet": "UnitsConfig", "value_type": "int", "description": "英雄-模型编号 -> UnitsConfig"},
    {"source_file": "public/Activity/ActivitySevenDaysTask.xlsx", "source_sheet": "ActivitySevenDaysTask", "source_col": "hero_id", "target_file": "public/Card/CardConfig.xlsx", "target_sheet": "CardConfig", "value_type": "int", "description": "七天活动-跳转英雄 -> CardConfig"},
    # ==================== Draw 抽卡引用 ====================
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "default_pool", "target_file": "public/Draw/Draw.xlsx", "target_sheet": "DrawPool", "target_col": "pool_id", "value_type": "int", "description": "抽卡-默认奖池 -> DrawPool.pool_id"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "draw_rule_group", "target_file": "public/Draw/Draw.xlsx", "target_sheet": "CustomizedPool", "value_type": "int", "description": "抽卡-定制奖池组 -> CustomizedPool"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "Draw", "source_col": "guaranteed_rule_group", "target_file": "public/Draw/Draw.xlsx", "target_sheet": "GuaranteedRule", "target_col": "group_id", "value_type": "int", "description": "抽卡-保底规则组 -> GuaranteedRule.group_id"},
    {"source_file": "public/Draw/Draw.xlsx", "source_sheet": "DrawPool", "source_col": "reward_group_id", "target_file": "public/Draw/Draw.xlsx", "target_sheet": "RewardGroup", "target_col": "reward_group_id", "value_type": "int", "description": "抽卡池-奖励组 -> RewardGroup.reward_group_id"},
    # ==================== Era 时代引用 ====================
    {"source_file": "public/Era/EraConfig.xlsx", "source_sheet": "SubEraConfig", "source_col": "era_id", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "EraConfig", "value_type": "int", "description": "子时代-所属大时代 -> EraConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "era", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "EraConfig", "value_type": "int", "description": "建筑-所属大时代 -> EraConfig"},
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingLevelConfig", "source_col": "era", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "EraConfig", "value_type": "int", "description": "建筑等级-所属大时代 -> EraConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "era", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "EraConfig", "value_type": "int", "description": "士兵-所属大时代 -> EraConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "ArmsConfig", "source_col": "time", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "EraConfig", "value_type": "int", "description": "兵种-所属时代 -> EraConfig"},
    {"source_file": "public/ScienceConfig/ScienceConfig.xlsx", "source_sheet": "ScienceNode", "source_col": "sub_era_id", "target_file": "public/Era/EraConfig.xlsx", "target_sheet": "SubEraConfig", "value_type": "int", "description": "科技节点-小时代ID -> SubEraConfig"},
    # ==================== Soldier 士兵引用 ====================
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "ArmsConfig", "source_col": "skill_id", "target_file": "public/Battle/Skill.xlsx", "target_sheet": "skill", "target_col": "id", "value_type": "int[]", "description": "兵种-被动技能 -> Skill.id"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "ArmsConfig", "source_col": "gift_id", "target_file": "public/Battle/SkillTalent.xlsx", "target_sheet": "skill_talent", "value_type": "int", "description": "兵种-天赋ID -> SkillTalent"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "ArmsConfig", "source_col": "unit_id", "target_file": "client/ArtAsset/UnitsConfig.xlsx", "target_sheet": "UnitsConfig", "value_type": "int", "description": "兵种-模型ID -> UnitsConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "ArmsConfig", "source_col": "tool_id", "target_file": "public/ToolConfig/ToolConfig.xlsx", "target_sheet": "ToolConfig", "value_type": "int", "description": "兵种-工具ID -> ToolConfig"},
    {"source_file": "public/SoldierConfig/SoldierConfig.xlsx", "source_sheet": "SoldierConfig", "source_col": "barrack_level", "target_file": "public/Buildings/BarrackConfig.xlsx", "target_sheet": "BarrackConfig", "value_type": "int", "description": "士兵-兵营等级 -> BarrackConfig"},
    # ==================== Battle 战斗引用 ====================
    {"source_file": "public/Battle/Skill.xlsx", "source_sheet": "skill", "source_col": "bullet_id", "target_file": "public/Battle/Bullet.xlsx", "target_sheet": "Bullet", "value_type": "int", "description": "技能-子弹ID -> Bullet"},
    {"source_file": "public/Battle/Skill.xlsx", "source_sheet": "skill", "source_col": "skill_id1", "target_file": "public/Battle/Skill.xlsx", "target_sheet": "skill", "target_col": "skill_id", "value_type": "int", "description": "技能-关联技能1 -> Skill.skill_id"},
    {"source_file": "public/Battle/Skill.xlsx", "source_sheet": "skill", "source_col": "skill_id2", "target_file": "public/Battle/Skill.xlsx", "target_sheet": "skill", "target_col": "skill_id", "value_type": "int", "description": "技能-关联技能2 -> Skill.skill_id"},
    # ==================== Tower 爬塔引用 ====================
    {"source_file": "public/Tower/TowerConfig.xlsx", "source_sheet": "TowerConfig", "source_col": "stage_id", "target_file": "public/Stage.xlsx", "target_sheet": "Stage", "value_type": "int", "description": "爬塔-关卡ID -> Stage"},
    # ==================== Guide 引导引用 ====================
    {"source_file": "public/Guide/Guide.xlsx", "source_sheet": "Guide", "source_col": "timeLineId", "target_file": "public/Guide/Timeline.xlsx", "target_sheet": "StoryTimeline", "value_type": "int", "description": "新手引导-TimelineID -> StoryTimeline"},
    {"source_file": "public/Guide/Guide.xlsx", "source_sheet": "Guide", "source_col": "storyId", "target_file": "public/Guide/Story.xlsx", "target_sheet": "StoryMain", "value_type": "int", "description": "新手引导-剧情ID -> StoryMain"},
    # ==================== Field 地块事件引用 ====================
    {"source_file": "public/Field/EventConfig.xlsx", "source_sheet": "EventLab", "source_col": "story_id", "target_file": "public/Guide/Story.xlsx", "target_sheet": "StoryMain", "value_type": "int", "description": "地块事件-剧情ID -> StoryMain"},
    {"source_file": "public/Field/EventConfig.xlsx", "source_sheet": "EventLab", "source_col": "story_id_after", "target_file": "public/Guide/Story.xlsx", "target_sheet": "StoryMain", "value_type": "int", "description": "地块事件-领取后剧情ID -> StoryMain"},
    {"source_file": "public/Field/EventConfig.xlsx", "source_sheet": "EventLab", "source_col": "fore_id", "target_file": "public/Field/EventConfig.xlsx", "target_sheet": "EventLab", "value_type": "int", "description": "地块事件-前置事件 -> EventLab"},
    # ==================== Mail 邮件引用 ====================
    {"source_file": "public/Mail/MailConfig.xlsx", "source_sheet": "MailConfig", "source_col": "tab_id", "target_file": "public/Mail/MailConfig.xlsx", "target_sheet": "MailTabConfig", "value_type": "int", "description": "邮件-所属页签 -> MailTabConfig"},
    # ==================== Ranking 排行榜引用 ====================
    {"source_file": "public/Ranking/RankingConfig.xlsx", "source_sheet": "RankingConfig", "source_col": "reward_group_id", "target_file": "public/Ranking/RankingConfig.xlsx", "target_sheet": "RankingReward", "value_type": "int", "description": "排行榜-奖励组 -> RankingReward"},
    # ==================== VIP 引用 ====================
    {"source_file": "public/VIP/VipConfig.xlsx", "source_sheet": "VipLevelConfig", "source_col": "exclusive_gift_id", "target_file": "public/GiftPack/GiftPackConfig.xlsx", "target_sheet": "GiftPackConfig", "value_type": "int", "description": "VIP-专属礼包 -> GiftPackConfig"},
    {"source_file": "public/VIP/VipConfig.xlsx", "source_sheet": "VipLevelConfig", "source_col": "unlock_functions", "target_file": "public/Common/FunctionConfig.xlsx", "target_sheet": "FunctionConfig", "value_type": "int[]", "description": "VIP-功能解锁 -> FunctionConfig"},
    # ==================== Activity 活动引用 ====================
    {"source_file": "public/Activity/ActivitySevenDaysTask.xlsx", "source_sheet": "ActivitySevenDaysTask", "source_col": "task_tab_group_id", "target_file": "public/Activity/ActivitySevenDaysTask.xlsx", "target_sheet": "SevenDaysTaskTab", "value_type": "int", "description": "七天活动-任务标签组 -> SevenDaysTaskTab"},
    {"source_file": "public/Activity/ActivitySevenDaysTask.xlsx", "source_sheet": "ActivitySevenDaysTask", "source_col": "score_reward_group_id", "target_file": "public/Activity/ActivitySevenDaysTask.xlsx", "target_sheet": "SevenDaysTaskScoreReward", "value_type": "int", "description": "七天活动-积分奖励组 -> SevenDaysTaskScoreReward"},
    # ==================== Shop 商店引用 ====================
    {"source_file": "public/GiftPack/GiftPackStore.xlsx", "source_sheet": "GiftPackStore", "source_col": "function_id", "target_file": "public/Common/FunctionConfig.xlsx", "target_sheet": "FunctionConfig", "value_type": "int", "description": "礼包商店-功能ID -> FunctionConfig"},
    {"source_file": "public/GiftPack/GiftPackStore.xlsx", "source_sheet": "GiftPackStore", "source_col": "pack_group_id", "target_file": "public/GiftPack/GiftPackConfig.xlsx", "target_sheet": "GiftPackConfig", "target_col": "group_id", "value_type": "int", "description": "礼包商店-礼包组 -> GiftPackConfig.group_id"},
    # ==================== Population 人口引用 ====================
    {"source_file": "public/Buildings/BuildingConfig.xlsx", "source_sheet": "BuildingConfig", "source_col": "population_work_type", "target_file": "public/Population/PopulationWorkType.xlsx", "target_sheet": "PopulationWorkType", "value_type": "int", "description": "建筑-工作类型 -> PopulationWorkType"},
    # ==================== Task 任务引用 ====================
    {"source_file": "public/Task/ChapterTaskConfig.xlsx", "source_sheet": "ChapterTaskConfig", "source_col": "group", "target_file": "public/Task/TaskConfig.xlsx", "target_sheet": "TaskConfig", "target_col": "group", "value_type": "int", "description": "章节任务-任务组 -> TaskConfig.group"},
]


# ---------------------------------------------------------------------------
# 校验器 v2
# ---------------------------------------------------------------------------

class ConfigValidator:
    def __init__(self, config_dir, rules, registry):
        self.config_dir = config_dir
        self.rules = rules
        self.registry = registry
        self.issues = []     # List[Issue]

    def _get_full_path(self, rel_path):
        return os.path.join(self.config_dir, rel_path)

    # -----------------------------------------------------------------------
    # 新增检查：数据格式校验（int列是否包含非数值）
    # -----------------------------------------------------------------------
    def check_data_format(self):
        """检查 int 类型列中是否包含无法解析的非数值数据"""
        print("  检查数据格式...")
        fmt_count = 0
        for ti in self.registry.tables:
            if not ti.data_rows:
                continue
            for col_name, col_info in ti.columns.items():
                col_type = col_info["type"]
                col_idx = col_info["col_idx"]

                if not col_type:
                    continue

                # 只检查 int 相关类型
                if "int" not in col_type.lower():
                    continue

                bad_rows = []
                for row_idx, row in enumerate(ti.data_rows):
                    if col_idx >= len(row):
                        continue
                    val = row[col_idx]
                    if val is None or str(val).strip() == "":
                        continue

                    s = str(val).strip()

                    if "int[][]" in col_type.lower() or "int[]" in col_type.lower():
                        ok, _ = validate_array_format(s, col_type.lower().strip())
                        if not ok:
                            bad_rows.append((row_idx + 5, s[:40]))
                    else:
                        ok, _ = validate_int_format(val)
                        if not ok:
                            bad_rows.append((row_idx + 5, s[:40]))

                if bad_rows:
                    fmt_count += 1
                    sample = "; ".join([f"行{r}: '{v}'" for r, v in bad_rows[:5]])
                    self.issues.append(Issue(
                        severity=Severity.WARN,
                        category="格式校验",
                        source_file=ti.rel_path,
                        source_sheet=ti.sheet_name,
                        description=f"列 {col_name}({col_type}) 有 {len(bad_rows)} 行数据格式异常",
                        details=f"示例: {sample}" +
                                (f"... 等共 {len(bad_rows)} 行" if len(bad_rows) > 5 else ""),
                        source_col=col_name,
                    ))
        print(f"    发现 {fmt_count} 处格式问题")

    # -----------------------------------------------------------------------
    # 新增检查：多语言 Key 一致性检查
    # -----------------------------------------------------------------------
    def check_localize_consistency(self):
        """对比 Localize_ChineseSimplified 和 Localize_English 的 key 列差异"""
        print("  检查多语言Key一致性...")
        self.localize_diff = None  # 存储差异结果供报告使用

        # 在 registry 中查找这两张表
        cn_tables = []
        en_tables = []
        for ti in self.registry.tables:
            sn_lower = ti.sheet_name.lower()
            if "localize_chinesesimplified" in sn_lower or sn_lower == "localize_chinesesimplified":
                cn_tables.append(ti)
            elif "localize_english" in sn_lower or sn_lower == "localize_english":
                en_tables.append(ti)

        if not cn_tables:
            print("    未找到 Localize_ChineseSimplified 表，跳过")
            return
        if not en_tables:
            print("    未找到 Localize_English 表，跳过")
            return

        cn_ti = cn_tables[0]
        en_ti = en_tables[0]

        # 用第一列做对比
        def extract_keys(ti):
            """从表中提取第一列的所有值，返回 {key_value: row_number}"""
            keys = {}
            for row_idx, row in enumerate(ti.data_rows):
                if len(row) == 0:
                    continue
                val = row[0]
                if val is not None and str(val).strip():
                    key_str = str(val).strip()
                    if key_str not in keys:
                        keys[key_str] = row_idx + 5  # 数据从第5行开始
            return keys, None

        cn_keys, cn_err = extract_keys(cn_ti)
        en_keys, en_err = extract_keys(en_ti)

        if cn_err:
            self.issues.append(Issue(
                severity=Severity.WARN,
                category="多语言一致性",
                source_file=cn_ti.rel_path,
                source_sheet=cn_ti.sheet_name,
                description=f"Localize_ChineseSimplified: {cn_err}",
                details="无法进行多语言Key对比",
            ))
            print(f"    Localize_ChineseSimplified: {cn_err}")
            return

        if en_err:
            self.issues.append(Issue(
                severity=Severity.WARN,
                category="多语言一致性",
                source_file=en_ti.rel_path,
                source_sheet=en_ti.sheet_name,
                description=f"Localize_English: {en_err}",
                details="无法进行多语言Key对比",
            ))
            print(f"    Localize_English: {en_err}")
            return

        cn_key_set = set(cn_keys.keys())
        en_key_set = set(en_keys.keys())

        only_in_cn = sorted(cn_key_set - en_key_set)
        only_in_en = sorted(en_key_set - cn_key_set)

        # 保存差异结果供报告专用节使用
        self.localize_diff = {
            "cn_file": cn_ti.rel_path,
            "cn_sheet": cn_ti.sheet_name,
            "cn_total": len(cn_key_set),
            "en_file": en_ti.rel_path,
            "en_sheet": en_ti.sheet_name,
            "en_total": len(en_key_set),
            "only_in_cn": only_in_cn,
            "only_in_en": only_in_en,
            "cn_keys": cn_keys,  # key -> row_num
            "en_keys": en_keys,
        }

        if only_in_cn:
            self.issues.append(Issue(
                severity=Severity.ERROR,
                category="多语言一致性",
                source_file=en_ti.rel_path,
                source_sheet=en_ti.sheet_name,
                description=f"Localize_English 缺少 {len(only_in_cn)} 个Key（存在于中文表但英文表没有）",
                details=", ".join(only_in_cn[:30]) + (f" ... 等共 {len(only_in_cn)} 个" if len(only_in_cn) > 30 else ""),
                invalid_ids=only_in_cn[:100],
                source_col="key",
                target_info=f"{cn_ti.rel_path} / {cn_ti.sheet_name}",
            ))

        if only_in_en:
            self.issues.append(Issue(
                severity=Severity.ERROR,
                category="多语言一致性",
                source_file=cn_ti.rel_path,
                source_sheet=cn_ti.sheet_name,
                description=f"Localize_ChineseSimplified 缺少 {len(only_in_en)} 个Key（存在于英文表但中文表没有）",
                details=", ".join(only_in_en[:30]) + (f" ... 等共 {len(only_in_en)} 个" if len(only_in_en) > 30 else ""),
                invalid_ids=only_in_en[:100],
                source_col="key",
                target_info=f"{en_ti.rel_path} / {en_ti.sheet_name}",
            ))

        if not only_in_cn and not only_in_en:
            print(f"    两张表Key完全一致（共 {len(cn_key_set)} 个Key）")
        else:
            print(f"    中文表共 {len(cn_key_set)} Key, 英文表共 {len(en_key_set)} Key")
            print(f"    英文缺少: {len(only_in_cn)} 个, 中文缺少: {len(only_in_en)} 个")

    # -----------------------------------------------------------------------
    # 跨表引用校验（核心逻辑，优化版）
    # -----------------------------------------------------------------------
    def validate_rule(self, rule):
        """校验单条引用规则，返回聚合后的 Issue 列表"""
        source_file = rule["source_file"]
        source_sheet = rule["source_sheet"]
        source_col = rule["source_col"]
        target_file = rule["target_file"]
        target_sheet = rule["target_sheet"]
        target_col = rule.get("target_col", "id")
        value_type = rule.get("value_type", "int")
        description = rule.get("description", "")

        if source_file == target_file and source_sheet == target_sheet and source_col == target_col:
            return

        target_ids = self.registry.get_ids(target_file, target_sheet, target_col)
        if not target_ids and not os.path.exists(self._get_full_path(target_file)):
            return

        full_path = self._get_full_path(source_file)
        if not os.path.exists(full_path):
            self.issues.append(Issue(
                severity=Severity.WARN,
                category="引用校验",
                source_file=source_file,
                source_sheet=source_sheet,
                description=f"源文件不存在: {source_file}",
                details="文件可能已被删除或移动",
                source_col=source_col,
            ))
            return

        try:
            _, headers_en, _, data_rows = read_sheet_data(full_path, source_sheet)
            if headers_en is None:
                self.issues.append(Issue(
                    severity=Severity.WARN,
                    category="引用校验",
                    source_file=source_file,
                    source_sheet=source_sheet,
                    description=f"源 Sheet 不存在: {source_sheet}",
                    details=f"在文件 {source_file} 中未找到名为 {source_sheet} 的Sheet",
                    source_col=source_col,
                ))
                return

            col_idx = None
            for i, h in enumerate(headers_en):
                if h and h.strip().lower() == source_col.lower():
                    col_idx = i
                    break
            if col_idx is None:
                self.issues.append(Issue(
                    severity=Severity.WARN,
                    category="引用校验",
                    source_file=source_file,
                    source_sheet=source_sheet,
                    description=f"源列 '{source_col}' 不存在",
                    details=f"在 {source_file}/{source_sheet} 中未找到列 {source_col}",
                    source_col=source_col,
                ))
                return

            # 聚合：收集所有无效引用 {invalid_id -> [source_row_ids]}
            invalid_map = defaultdict(list)

            for row_idx, row in enumerate(data_rows):
                if col_idx >= len(row):
                    continue
                val = row[col_idx]
                ref_ids = self._extract_ref_ids(val, value_type)
                if not ref_ids:
                    continue

                source_row_id = row[0] if len(row) > 0 and row[0] is not None else f"行{row_idx + 5}"

                for ref_id in ref_ids:
                    # 跳过 0 值（通常表示"无引用"）
                    if ref_id == 0:
                        continue
                    if ref_id not in target_ids:
                        invalid_map[ref_id].append(str(source_row_id))

            # 生成聚合后的 Issue
            if invalid_map:
                invalid_ids_sorted = sorted(invalid_map.keys())
                all_row_ids = []
                for iid in invalid_ids_sorted:
                    all_row_ids.extend(invalid_map[iid])

                # 构建详情
                details_parts = []
                for iid in invalid_ids_sorted[:20]:
                    rows = invalid_map[iid]
                    if len(rows) <= 5:
                        details_parts.append(f"ID={iid} (行: {', '.join(rows)})")
                    else:
                        details_parts.append(f"ID={iid} (共{len(rows)}行, 如: {', '.join(rows[:3])}...)")
                if len(invalid_ids_sorted) > 20:
                    details_parts.append(f"... 还有 {len(invalid_ids_sorted) - 20} 个无效ID")

                self.issues.append(Issue(
                    severity=Severity.ERROR,
                    category="引用校验",
                    source_file=source_file,
                    source_sheet=source_sheet,
                    description=description,
                    details="; ".join(details_parts),
                    row_ids=all_row_ids,
                    invalid_ids=invalid_ids_sorted,
                    source_col=source_col,
                    target_info=f"{target_file} / {target_sheet}.{target_col}",
                ))

        except Exception as e:
            self.issues.append(Issue(
                severity=Severity.WARN,
                category="引用校验",
                source_file=source_file,
                source_sheet=source_sheet,
                description=f"校验异常: {source_col}",
                details=str(e),
                source_col=source_col,
            ))

    def _extract_ref_ids(self, val, value_type):
        if val is None or str(val).strip() == "":
            return set()
        s = str(val).strip()
        if value_type in ("int[][]", "int[]"):
            return parse_int_array(s)
        elif value_type == "int":
            try:
                v = int(float(s))
                return {v}
            except (ValueError, TypeError):
                return set()
        else:
            return parse_int_array(s)

    # -----------------------------------------------------------------------
    # 主运行入口
    # -----------------------------------------------------------------------
    def run(self, verbose=False, report_path=None):
        print("=" * 70)
        print("  配置表交叉校验工具 v2.0 (增强检测模式)")
        print("=" * 70)

        start_time = time.time()

        # 1. 基础检查
        self.check_data_format()

        # 2. 多语言Key一致性检查
        self.check_localize_consistency()

        # 3. 跨表引用校验
        print(f"\n  执行跨表引用校验 ({len(self.rules)} 条规则)...")

        target_keys = set()
        for rule in self.rules:
            key = (rule["target_file"], rule["target_sheet"], rule.get("target_col", "id"))
            target_keys.add(key)
        for key in target_keys:
            self.registry.get_ids(*key)

        total = len(self.rules)
        for i, rule in enumerate(self.rules):
            if verbose:
                desc = rule.get("description", "")
                print(f"  [{i+1}/{total}] {desc} ...")
            self.validate_rule(rule)

        elapsed = time.time() - start_time

        # 3. 生成报告
        if report_path is None:
            report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validate_report.md")
        self._generate_report(report_path, elapsed)

    # -----------------------------------------------------------------------
    # 报告生成 v2 —— 按模块分组、聚合、带目录
    # -----------------------------------------------------------------------
    def _generate_report(self, report_path, elapsed):
        errors = [i for i in self.issues if i.severity == Severity.ERROR]
        warns = [i for i in self.issues if i.severity == Severity.WARN]
        infos = [i for i in self.issues if i.severity == Severity.INFO]

        # 按源文件分组
        groups = OrderedDict()  # source_file -> [Issue, ...]
        for issue in self.issues:
            key = issue.source_file
            if key not in groups:
                groups[key] = []
            groups[key].append(issue)

        # 按模块（目录前缀）聚合统计
        module_stats = defaultdict(lambda: {"error": 0, "warn": 0, "info": 0, "files": set()})
        for issue in self.issues:
            parts = issue.source_file.replace("\\", "/").split("/")
            module = parts[1] if len(parts) > 2 else parts[0] if parts else "unknown"
            module_stats[module][issue.severity.lower()] += 1
            module_stats[module]["files"].add(issue.source_file)

        lines = []

        # ===== 标题 =====
        lines.append("# 配置表交叉校验报告 v2.0\n")
        lines.append(f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}  |  耗时: {elapsed:.1f}s  |  校验规则: {len(self.rules)} 条\n")

        # ===== 总览 =====
        lines.append("---\n")
        lines.append("## 总览\n")

        total_issues = len(self.issues)
        if total_issues == 0:
            lines.append("**所有校验均通过，未发现配置表问题。**\n")
        else:
            lines.append(f"| 级别 | 数量 | 说明 |")
            lines.append(f"|:----:|:----:|------|")
            if errors:
                lines.append(f"| **ERROR** | **{len(errors)}** | 必须修复：引用了不存在的ID、主键重复等 |")
            if warns:
                lines.append(f"| WARN | {len(warns)} | 建议检查：空值、格式异常、文件/列缺失等 |")
            if infos:
                lines.append(f"| INFO | {len(infos)} | 信息提示 |")
            lines.append("")

        # ===== 模块统计 =====
        if module_stats:
            lines.append("## 按模块统计\n")
            lines.append("| 模块 | 错误 | 警告 | 涉及文件数 |")
            lines.append("|------|:----:|:----:|:----------:|")
            for mod in sorted(module_stats.keys(), key=lambda m: -module_stats[m]["error"]):
                st = module_stats[mod]
                err_str = f"**{st['error']}**" if st['error'] > 0 else "0"
                lines.append(f"| {mod} | {err_str} | {st['warn']} | {len(st['files'])} |")
            lines.append("")

        # ===== 快速导航 =====
        if groups:
            lines.append("## 目录\n")
            for idx, (src_file, file_issues) in enumerate(groups.items(), 1):
                err_count = sum(1 for i in file_issues if i.severity == Severity.ERROR)
                warn_count = sum(1 for i in file_issues if i.severity == Severity.WARN)
                badge = ""
                if err_count:
                    badge += f" ({err_count} ERROR)"
                if warn_count:
                    badge += f" ({warn_count} WARN)"
                anchor = src_file.replace("\\", "/").replace("/", "-").replace(".", "-").replace(" ", "-").lower()
                lines.append(f"{idx}. [{src_file}](#{anchor}){badge}")
            lines.append("")

        # ===== 按文件详细列表 =====
        if groups:
            lines.append("---\n")
            lines.append("## 详细结果\n")

            for src_file, file_issues in groups.items():
                anchor = src_file.replace("\\", "/").replace("/", "-").replace(".", "-").replace(" ", "-").lower()
                err_count = sum(1 for i in file_issues if i.severity == Severity.ERROR)
                warn_count = sum(1 for i in file_issues if i.severity == Severity.WARN)

                lines.append(f"### {src_file}\n")
                lines.append(f"> 错误: {err_count}  |  警告: {warn_count}\n")

                # 按 category 分组
                by_category = defaultdict(list)
                for issue in file_issues:
                    by_category[issue.category].append(issue)

                for category, cat_issues in by_category.items():
                    if len(by_category) > 1:
                        lines.append(f"**{category}**\n")

                    lines.append("| 级别 | Sheet | 列 | 描述 | 详情 | 目标表 |")
                    lines.append("|:----:|-------|-----|------|------|--------|")

                    for issue in cat_issues:
                        sev_badge = f"**{issue.severity}**" if issue.severity == Severity.ERROR else issue.severity
                        # 无效ID数量统计
                        id_info = ""
                        if issue.invalid_ids:
                            id_info = f"{len(issue.invalid_ids)}个无效ID, {len(issue.row_ids)}行受影响"
                        target = issue.target_info if issue.target_info else "-"

                        # 截断过长的详情
                        detail_text = issue.details
                        if len(detail_text) > 200:
                            detail_text = detail_text[:200] + "..."

                        lines.append(
                            f"| {sev_badge} "
                            f"| {issue.source_sheet} "
                            f"| {issue.source_col} "
                            f"| {issue.description} "
                            f"| {detail_text} "
                            f"| {target} |"
                        )
                    lines.append("")

        # ===== 附录：多语言Key差异明细 =====
        if hasattr(self, 'localize_diff') and self.localize_diff is not None:
            diff = self.localize_diff
            only_cn = diff["only_in_cn"]
            only_en = diff["only_in_en"]

            lines.append("---\n")
            lines.append("## 附录：多语言Key差异明细\n")
            lines.append(f"| 项目 | 值 |")
            lines.append(f"|------|-----|")
            lines.append(f"| 中文表 | {diff['cn_file']} / {diff['cn_sheet']} |")
            lines.append(f"| 英文表 | {diff['en_file']} / {diff['en_sheet']} |")
            lines.append(f"| 中文表Key总数 | {diff['cn_total']} |")
            lines.append(f"| 英文表Key总数 | {diff['en_total']} |")
            lines.append(f"| 英文表缺少 | **{len(only_cn)}** 个Key |")
            lines.append(f"| 中文表缺少 | **{len(only_en)}** 个Key |")
            lines.append("")

            if only_cn:
                lines.append(f"### 英文表缺少的Key（共 {len(only_cn)} 个）\n")
                lines.append("以下Key存在于 Localize_ChineseSimplified 但不存在于 Localize_English：\n")
                lines.append("| # | Key | 中文表行号 |")
                lines.append("|:--:|-----|:----------:|")
                cn_keys_map = diff["cn_keys"]
                for idx, k in enumerate(only_cn, 1):
                    row_num = cn_keys_map.get(k, "-")
                    lines.append(f"| {idx} | `{k}` | {row_num} |")
                lines.append("")

            if only_en:
                lines.append(f"### 中文表缺少的Key（共 {len(only_en)} 个）\n")
                lines.append("以下Key存在于 Localize_English 但不存在于 Localize_ChineseSimplified：\n")
                lines.append("| # | Key | 英文表行号 |")
                lines.append("|:--:|-----|:----------:|")
                en_keys_map = diff["en_keys"]
                for idx, k in enumerate(only_en, 1):
                    row_num = en_keys_map.get(k, "-")
                    lines.append(f"| {idx} | `{k}` | {row_num} |")
                lines.append("")

            if not only_cn and not only_en:
                lines.append("**两张表的Key完全一致，无差异。**\n")

        # ===== 附录：无效ID速查表 =====
        ref_errors = [i for i in errors if i.category == "引用校验" and i.invalid_ids]
        if ref_errors:
            lines.append("---\n")
            lines.append("## 附录：无效ID速查表\n")
            lines.append("以下表格按无效ID聚合，方便快速排查是目标表缺少配置还是源表填写错误。\n")
            lines.append("| 无效ID | 来源规则 | 目标表 | 涉及行数 |")
            lines.append("|:------:|----------|--------|:--------:|")

            # 全局聚合 invalid_id -> [(description, target, row_count)]
            id_global = defaultdict(list)
            for issue in ref_errors:
                for iid in issue.invalid_ids:
                    row_count = len([r for r in issue.row_ids])  # 近似
                    id_global[iid].append((issue.description, issue.target_info, row_count))

            for iid in sorted(id_global.keys()):
                entries = id_global[iid]
                for desc, target, rc in entries[:3]:
                    lines.append(f"| {iid} | {desc} | {target} | {rc} |")
                if len(entries) > 3:
                    lines.append(f"| {iid} | ... 还有 {len(entries)-3} 条规则引用 | - | - |")
            lines.append("")

        # ===== 写入文件 =====
        report = "\n".join(lines)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        # 控制台输出摘要
        print("\n" + "=" * 70)
        print(f"  校验完成（耗时 {elapsed:.1f}s）")
        print(f"  错误(ERROR): {len(errors)}  警告(WARN): {len(warns)}  信息(INFO): {len(infos)}")
        print(f"  报告已保存至: {report_path}")
        print("=" * 70)

        if errors:
            print(f"\n--- 错误摘要（共 {len(errors)} 条）---")
            for issue in errors[:30]:
                id_count = f" [{len(issue.invalid_ids)}个无效ID]" if issue.invalid_ids else ""
                print(f"  [ERROR] {issue.source_file}/{issue.source_sheet} | {issue.description}{id_count}")
            if len(errors) > 30:
                print(f"  ... 还有 {len(errors) - 30} 条错误，详见报告")

        if warns:
            print(f"\n--- 警告摘要（共 {len(warns)} 条）---")
            for issue in warns[:10]:
                print(f"  [WARN]  {issue.source_file}/{issue.source_sheet} | {issue.description}")
            if len(warns) > 10:
                print(f"  ... 还有 {len(warns) - 10} 条警告，详见报告")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="配置表交叉校验工具 v2.0（增强检测模式）")
    parser.add_argument("-c", "--config-dir", default=DEFAULT_CONFIG_DIR,
                        help=f"配置表所在目录（默认: {DEFAULT_CONFIG_DIR}）")
    parser.add_argument("-v", "--verbose", action="store_true", help="显示详细输出")
    parser.add_argument("-o", "--output", default=None, help="报告输出路径（默认: 工具目录下 validate_report.md）")
    parser.add_argument("--no-auto", action="store_true", help="禁用自动检测，仅使用手动规则")
    parser.add_argument("--skip-basic", action="store_true", help="跳过基础检查（主键重复/空值/格式），仅做引用校验")
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

    # 如果需要跳过基础检查则覆盖方法
    if args.skip_basic:
        validator.check_data_format = lambda: None

    validator.run(verbose=args.verbose, report_path=report_path)

    error_count = sum(1 for i in validator.issues if i.severity == Severity.ERROR)
    sys.exit(1 if error_count else 0)


if __name__ == "__main__":
    main()
