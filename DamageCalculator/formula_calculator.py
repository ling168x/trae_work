import math
import json

ATTR_DEFINITIONS = [
    {"属性ID": 101, "万分比": 0, "name": "英雄最大生命"},
    {"属性ID": 102, "万分比": 0, "name": "英雄最大攻击"},
    {"属性ID": 103, "万分比": 0, "name": "英雄最大防御"},
    {"属性ID": 1001, "万分比": 0, "name": "英雄基础生命"},
    {"属性ID": 1002, "万分比": 0, "name": "英雄基础攻击"},
    {"属性ID": 1003, "万分比": 0, "name": "英雄基础防御"},
    {"属性ID": 1004, "万分比": 0, "name": "英雄固定生命"},
    {"属性ID": 1005, "万分比": 0, "name": "英雄固定攻击"},
    {"属性ID": 1006, "万分比": 0, "name": "英雄固定防御"},
    {"属性ID": 1007, "万分比": 0, "name": "带兵量上限"},
    {"属性ID": 1008, "万分比": 0, "name": "指挥"},
    {"属性ID": 1009, "万分比": 1, "name": "英雄生命百分比"},
    {"属性ID": 1010, "万分比": 1, "name": "英雄攻击百分比"},
    {"属性ID": 1011, "万分比": 1, "name": "英雄防御百分比"},
    {"属性ID": 1012, "万分比": 1, "name": "部队生命百分比"},
    {"属性ID": 1013, "万分比": 1, "name": "部队攻击百分比"},
    {"属性ID": 1014, "万分比": 1, "name": "部队防御百分比"},
    {"属性ID": 1015, "万分比": 1, "name": "近战英雄生命百分比"},
    {"属性ID": 1016, "万分比": 1, "name": "近战英雄攻击百分比"},
    {"属性ID": 1017, "万分比": 1, "name": "近战英雄防御百分比"},
    {"属性ID": 1018, "万分比": 1, "name": "远程英雄生命百分比"},
    {"属性ID": 1019, "万分比": 1, "name": "远程英雄攻击百分比"},
    {"属性ID": 1020, "万分比": 1, "name": "远程英雄防御百分比"},
    {"属性ID": 1021, "万分比": 1, "name": "突击英雄生命百分比"},
    {"属性ID": 1022, "万分比": 1, "name": "突击英雄攻击百分比"},
    {"属性ID": 1023, "万分比": 1, "name": "突击英雄防御百分比"},
    {"属性ID": 1024, "万分比": 1, "name": "所有英雄生命百分比"},
    {"属性ID": 1025, "万分比": 1, "name": "所有英雄攻击百分比"},
    {"属性ID": 1026, "万分比": 1, "name": "所有英雄防御百分比"},
    {"属性ID": 1027, "万分比": 1, "name": "命中率"},
    {"属性ID": 1028, "万分比": 1, "name": "闪避率"},
    {"属性ID": 1029, "万分比": 1, "name": "暴击率"},
    {"属性ID": 1030, "万分比": 1, "name": "抗暴率"},
    {"属性ID": 1031, "万分比": 1, "name": "暴击伤害"},
    {"属性ID": 1032, "万分比": 1, "name": "暴击伤害减免"},
    {"属性ID": 1033, "万分比": 1, "name": "普攻伤害增加"},
    {"属性ID": 1034, "万分比": 1, "name": "普攻伤害减少"},
    {"属性ID": 1035, "万分比": 1, "name": "技能伤害增加"},
    {"属性ID": 1036, "万分比": 1, "name": "技能伤害减免"},
    {"属性ID": 1037, "万分比": 1, "name": "PVP伤害增加"},
    {"属性ID": 1038, "万分比": 1, "name": "PVP伤害减免"},
    {"属性ID": 1039, "万分比": 1, "name": "克制敌方时伤害提升"},
    {"属性ID": 1040, "万分比": 1, "name": "克制敌方时承受伤害减少"},
    {"属性ID": 1041, "万分比": 1, "name": "伤害加深"},
    {"属性ID": 1042, "万分比": 1, "name": "伤害减免"},
    {"属性ID": 1043, "万分比": 1, "name": "易伤伤害加成"},
    {"属性ID": 1044, "万分比": 1, "name": "攻击速度"},
    {"属性ID": 1045, "万分比": 1, "name": "技能冷却速度"},
    {"属性ID": 1046, "万分比": 1, "name": "近战英雄伤害提升"},
    {"属性ID": 1047, "万分比": 1, "name": "远程英雄伤害提升"},
    {"属性ID": 1048, "万分比": 1, "name": "突击英雄伤害提升"},
    {"属性ID": 1049, "万分比": 1, "name": "所有英雄伤害提升"},
    {"属性ID": 1050, "万分比": 1, "name": "对近战英雄伤害减少"},
    {"属性ID": 1051, "万分比": 1, "name": "对远程英雄伤害减少"},
    {"属性ID": 1052, "万分比": 1, "name": "对突击英雄伤害减少"},
    {"属性ID": 1053, "万分比": 1, "name": "对前排单位伤害提升"},
    {"属性ID": 1054, "万分比": 1, "name": "对后排单位伤害提升"},
    {"属性ID": 1055, "万分比": 1, "name": "对前排单位伤害减免"},
    {"属性ID": 1056, "万分比": 1, "name": "造成伤害提升"},
    {"属性ID": 1057, "万分比": 1, "name": "承受伤害减少"},
    {"属性ID": 1058, "万分比": 1, "name": "对怪物伤害增加"},
    {"属性ID": 1059, "万分比": 1, "name": "承受怪物伤害减少"},
    {"属性ID": 1060, "万分比": 1, "name": "对首领造成伤害提升"},
    {"属性ID": 1061, "万分比": 1, "name": "承受首领伤害减少"},
    {"属性ID": 1062, "万分比": 0, "name": "战场移动速度"},
    {"属性ID": 1063, "万分比": 1, "name": "战场移动速度万分比"},
    {"属性ID": 2001, "万分比": 0, "name": "士兵总生命"},
    {"属性ID": 2002, "万分比": 0, "name": "士兵总攻击"},
    {"属性ID": 2003, "万分比": 0, "name": "士兵总防御"},
    {"属性ID": 2004, "万分比": 0, "name": "士兵基础生命"},
    {"属性ID": 2005, "万分比": 0, "name": "士兵基础攻击"},
    {"属性ID": 2006, "万分比": 0, "name": "士兵基础防御"},
    {"属性ID": 2007, "万分比": 0, "name": "士兵士气"},
    {"属性ID": 2008, "万分比": 0, "name": "士兵负重"},
    {"属性ID": 2009, "万分比": 1, "name": "士兵生命百分比"},
    {"属性ID": 2010, "万分比": 1, "name": "士兵攻击百分比"},
    {"属性ID": 2011, "万分比": 1, "name": "士兵防御百分比"},
    {"属性ID": 2012, "万分比": 1, "name": "士兵负重百分比"},
    {"属性ID": 2013, "万分比": 0, "name": "近战士兵生命"},
    {"属性ID": 2014, "万分比": 0, "name": "近战士兵攻击"},
    {"属性ID": 2015, "万分比": 0, "name": "近战士兵防御"},
    {"属性ID": 2016, "万分比": 1, "name": "近战士兵生命百分比"},
    {"属性ID": 2017, "万分比": 1, "name": "近战士兵攻击百分比"},
    {"属性ID": 2018, "万分比": 1, "name": "近战士兵防御百分比"},
    {"属性ID": 2019, "万分比": 0, "name": "远程士兵生命"},
    {"属性ID": 2020, "万分比": 0, "name": "远程士兵攻击"},
    {"属性ID": 2021, "万分比": 0, "name": "远程士兵防御"},
    {"属性ID": 2022, "万分比": 1, "name": "远程士兵生命百分比"},
    {"属性ID": 2023, "万分比": 1, "name": "远程士兵攻击百分比"},
    {"属性ID": 2024, "万分比": 1, "name": "远程士兵防御百分比"},
    {"属性ID": 2025, "万分比": 0, "name": "突击士兵生命"},
    {"属性ID": 2026, "万分比": 0, "name": "突击士兵攻击"},
    {"属性ID": 2027, "万分比": 0, "name": "突击士兵防御"},
    {"属性ID": 2028, "万分比": 1, "name": "突击士兵生命百分比"},
    {"属性ID": 2029, "万分比": 1, "name": "突击士兵攻击百分比"},
    {"属性ID": 2030, "万分比": 1, "name": "突击士兵防御百分比"},
    {"属性ID": 3001, "万分比": 1, "name": "建造速度"},
    {"属性ID": 3002, "万分比": 1, "name": "研究速度"},
    {"属性ID": 3003, "万分比": 1, "name": "训练速度"},
    {"属性ID": 3004, "万分比": 1, "name": "采集速度"},
    {"属性ID": 3005, "万分比": 1, "name": "建造消耗资源减少"},
    {"属性ID": 3006, "万分比": 1, "name": "研究消耗资源减少"},
    {"属性ID": 3007, "万分比": 1, "name": "训练消耗资源减少"},
    {"属性ID": 3008, "万分比": 0, "name": "训练容量"},
    {"属性ID": 3009, "万分比": 1, "name": "训练容量百分比"},
    {"属性ID": 3010, "万分比": 1, "name": "占位"},
    {"属性ID": 3011, "万分比": 1, "name": "占位"},
    {"属性ID": 3012, "万分比": 1, "name": "全资源生产速度"},
    {"属性ID": 3013, "万分比": 1, "name": "木头资源生产速度"},
    {"属性ID": 3014, "万分比": 1, "name": "石头资源生产速度"},
    {"属性ID": 3015, "万分比": 1, "name": "食物资源生产速度"},
    {"属性ID": 3016, "万分比": 1, "name": "铁矿资源生产速度"},
    {"属性ID": 3017, "万分比": 0, "name": "全资源存储上限"},
    {"属性ID": 3018, "万分比": 0, "name": "木头资源存储上限"},
    {"属性ID": 3019, "万分比": 0, "name": "石头资源存储上限"},
    {"属性ID": 3020, "万分比": 0, "name": "食物资源存储上限"},
    {"属性ID": 3021, "万分比": 0, "name": "铁矿资源存储上限"},
    {"属性ID": 3022, "万分比": 0, "name": "人均工作效率"},
    {"属性ID": 3023, "万分比": 1, "name": "工作速度"},
    {"属性ID": 3024, "万分比": 0, "name": "人均建造工作效率"},
    {"属性ID": 3025, "万分比": 0, "name": "人均科研工作效率"},
    {"属性ID": 3026, "万分比": 0, "name": "人均训练工作效率"},
    {"属性ID": 3027, "万分比": 0, "name": "建造队列可分配队伍数量"},
    {"属性ID": 3028, "万分比": 0, "name": "食物队列可分配队伍数量"},
    {"属性ID": 3029, "万分比": 0, "name": "伐木队列可分配队伍数量"},
    {"属性ID": 3030, "万分比": 0, "name": "采石队列可分配队伍数量"},
    {"属性ID": 3031, "万分比": 0, "name": "采矿队列可分配队伍数量"},
    {"属性ID": 3032, "万分比": 0, "name": "科研队列可分配队伍数量"},
    {"属性ID": 3033, "万分比": 0, "name": "练兵队列可分配队伍数量"},
    {"属性ID": 3034, "万分比": 0, "name": "人均木头生产效率"},
    {"属性ID": 3035, "万分比": 0, "name": "人均石头生产效率"},
    {"属性ID": 3036, "万分比": 0, "name": "人均食物生产效率"},
    {"属性ID": 3037, "万分比": 0, "name": "人均铁矿生产效率"},
    {"属性ID": 3038, "万分比": 0, "name": "基础木头生产效率"},
    {"属性ID": 3039, "万分比": 0, "name": "基础石头生产效率"},
    {"属性ID": 3040, "万分比": 0, "name": "基础食物生产效率"},
    {"属性ID": 3041, "万分比": 0, "name": "基础铁矿生产效率"},
    {"属性ID": 3042, "万分比": 0, "name": "人均生产效率"},
    {"属性ID": 3043, "万分比": 0, "name": "人均木头采集效率"},
    {"属性ID": 3044, "万分比": 0, "name": "人均石头采集效率"},
    {"属性ID": 3045, "万分比": 0, "name": "人均食物采集效率"},
    {"属性ID": 3046, "万分比": 0, "name": "人均铁矿采集效率"},
    {"属性ID": 3047, "万分比": 0, "name": "事件采集效率"},
    {"属性ID": 4001, "万分比": 0, "name": "行军速度"},
    {"属性ID": 4002, "万分比": 1, "name": "行军速度百分比"},
    {"属性ID": 9001, "万分比": 0, "name": "英雄等级上限"},
    {"属性ID": 9002, "万分比": 0, "name": "建筑等级上限"}
]

ATTR_NAME_MAP = {item["属性ID"]: item["name"] for item in ATTR_DEFINITIONS}
ATTR_WAN_MAP = {item["属性ID"]: item["万分比"] for item in ATTR_DEFINITIONS}

FORMULA_CATEGORIES = {
    "建造时间": {
        "id": "build_time",
        "description": "建造时间计算",
        "variables": [
            {"name": "剩余工作量", "default": 10000},
            {"name": "工作人口", "default": 100},
            {"name": "标准工作人口", "default": 100}
        ],
        "attrs_used": [3022, 3024, 3023, 3001]
    },
    "科研时间": {
        "id": "research_time",
        "description": "科研时间计算",
        "variables": [
            {"name": "剩余工作量", "default": 10000},
            {"name": "工作人口", "default": 100},
            {"name": "标准工作人口", "default": 100}
        ],
        "attrs_used": [3022, 3025, 3023, 3002]
    },
    "治疗时间": {
        "id": "heal_time",
        "description": "治疗时间计算",
        "variables": [
            {"name": "剩余工作量", "default": 10000},
            {"name": "工作人口", "default": 100},
            {"name": "标准工作人口", "default": 100}
        ],
        "attrs_used": [3022, 3023]
    },
    "训练时间": {
        "id": "train_time",
        "description": "训练时间计算",
        "variables": [
            {"name": "剩余工作量", "default": 10000},
            {"name": "工作人口", "default": 100},
            {"name": "标准工作人口", "default": 100}
        ],
        "attrs_used": [3022, 3026, 3023, 3003]
    },
    "事件时间": {
        "id": "event_time",
        "description": "事件时间计算",
        "variables": [
            {"name": "剩余工作量", "default": 10000},
            {"name": "工作人口", "default": 100},
            {"name": "标准工作人口", "default": 100}
        ],
        "attrs_used": [3022, 3023, 3004]
    },
    "木头生产效率": {
        "id": "wood_production",
        "description": "木头资源生产效率",
        "variables": [
            {"name": "生产人口", "default": 100},
            {"name": "标准工作人口", "default": 100}
        ],
        "attrs_used": [3038, 3042, 3034, 3012, 3013]
    },
    "石头生产效率": {
        "id": "stone_production",
        "description": "石头资源生产效率",
        "variables": [
            {"name": "生产人口", "default": 100},
            {"name": "标准工作人口", "default": 100}
        ],
        "attrs_used": [3039, 3042, 3035, 3012, 3014]
    },
    "食物生产效率": {
        "id": "food_production",
        "description": "食物资源生产效率",
        "variables": [
            {"name": "生产人口", "default": 100},
            {"name": "标准工作人口", "default": 100}
        ],
        "attrs_used": [3040, 3042, 3036, 3012, 3015]
    },
    "铁矿生产效率": {
        "id": "iron_production",
        "description": "铁矿资源生产效率",
        "variables": [
            {"name": "生产人口", "default": 100},
            {"name": "标准工作人口", "default": 100}
        ],
        "attrs_used": [3041, 3042, 3037, 3012, 3016]
    },
    "事件工作时间": {
        "id": "event_work_time",
        "description": "事件工作时间计算",
        "variables": [
            {"name": "工作量", "default": 10000},
            {"name": "立即加速工作量", "default": 0},
            {"name": "工作人口", "default": 100},
            {"name": "标准工作人口", "default": 100}
        ],
        "attrs_used": [3022, 3047, 3023, 3001]
    },
    "训练工作量": {
        "id": "train_workload",
        "description": "训练工作量计算",
        "variables": [
            {"name": "单士兵训练工作量", "default": 1000},
            {"name": "训练数量", "default": 100}
        ],
        "attrs_used": []
    },
    "治疗工作量": {
        "id": "heal_workload",
        "description": "治疗工作量计算",
        "variables": [
            {"name": "单士兵治疗工作量", "default": 1000},
            {"name": "治疗数量", "default": 100}
        ],
        "attrs_used": []
    }
}


def parse_attrs_json(attrs_json):
    """解析attrs JSON字符串，返回属性字典"""
    try:
        data = json.loads(attrs_json)
        if isinstance(data, dict) and 'attrs' in data:
            attrs = data['attrs']
        elif isinstance(data, list):
            attrs = data
        else:
            return {}
        
        result = {}
        for item in attrs:
            attr_id = int(item.get('attrId', 0))
            value = float(item.get('value', 0))
            if ATTR_WAN_MAP.get(attr_id, 1) == 1:
                value = value / 10000
            else:
                value = int(value)
            result[attr_id] = value
        return result
    except Exception:
        return {}


def get_attr_value(attrs_dict, attr_id, default=0):
    """获取属性值"""
    return attrs_dict.get(attr_id, default)


def calculate_work_time(remaining_work, work_population, standard_population, 
                        per_capita_efficiency, specific_efficiency_sum, 
                        work_speed, specific_speed):
    """计算工作时间通用公式"""
    if standard_population <= 0:
        return 0
    
    efficiency = per_capita_efficiency + specific_efficiency_sum
    
    if work_population <= 0 or efficiency <= 0:
        return 0
    
    if work_population < standard_population:
        total_efficiency = efficiency * work_population
    else:
        ln_term = math.log(max(1e-10, work_population / standard_population))
        population_factor = 1 + 0.3 * ln_term
        population_factor = max(0.1, population_factor)
        total_efficiency = efficiency * standard_population * population_factor
    
    if total_efficiency <= 0:
        return 0
    
    speed_factor = 1 + work_speed + specific_speed
    speed_factor = max(0.1, speed_factor)
    
    return remaining_work / (total_efficiency * speed_factor)


def calculate_build_time(attrs_dict, remaining_work, work_population, standard_population):
    """计算建造时间"""
    per_capita_efficiency = get_attr_value(attrs_dict, 3022)
    build_efficiency = get_attr_value(attrs_dict, 3024)
    work_speed = get_attr_value(attrs_dict, 3023)
    build_speed = get_attr_value(attrs_dict, 3001)
    
    return calculate_work_time(
        remaining_work, work_population, standard_population,
        per_capita_efficiency, build_efficiency, work_speed, build_speed
    )


def calculate_research_time(attrs_dict, remaining_work, work_population, standard_population):
    """计算科研时间"""
    per_capita_efficiency = get_attr_value(attrs_dict, 3022)
    research_efficiency = get_attr_value(attrs_dict, 3025)
    work_speed = get_attr_value(attrs_dict, 3023)
    research_speed = get_attr_value(attrs_dict, 3002)
    
    return calculate_work_time(
        remaining_work, work_population, standard_population,
        per_capita_efficiency, research_efficiency, work_speed, research_speed
    )


def calculate_heal_time(attrs_dict, remaining_work, work_population, standard_population):
    """计算治疗时间"""
    per_capita_efficiency = get_attr_value(attrs_dict, 3022)
    work_speed = get_attr_value(attrs_dict, 3023)
    
    return calculate_work_time(
        remaining_work, work_population, standard_population,
        per_capita_efficiency, 0, work_speed, 0
    )


def calculate_train_time(attrs_dict, remaining_work, work_population, standard_population):
    """计算训练时间"""
    per_capita_efficiency = get_attr_value(attrs_dict, 3022)
    train_efficiency = get_attr_value(attrs_dict, 3026)
    work_speed = get_attr_value(attrs_dict, 3023)
    train_speed = get_attr_value(attrs_dict, 3003)
    
    return calculate_work_time(
        remaining_work, work_population, standard_population,
        per_capita_efficiency, train_efficiency, work_speed, train_speed
    )


def calculate_event_time(attrs_dict, remaining_work, work_population, standard_population):
    """计算事件时间"""
    per_capita_efficiency = get_attr_value(attrs_dict, 3022)
    work_speed = get_attr_value(attrs_dict, 3023)
    gather_speed = get_attr_value(attrs_dict, 3004)
    
    return calculate_work_time(
        remaining_work, work_population, standard_population,
        per_capita_efficiency, 0, work_speed, gather_speed
    )


def calculate_resource_production(attrs_dict, base_production_attr, per_capita_production_attr,
                                   all_resource_speed_attr, specific_resource_speed_attr,
                                   production_population, standard_population=100):
    """计算资源生产效率通用公式"""
    base_production = get_attr_value(attrs_dict, base_production_attr)
    per_capita_production = get_attr_value(attrs_dict, 3042) + get_attr_value(attrs_dict, per_capita_production_attr)
    
    if production_population <= 0:
        return 0
    
    if production_population < standard_population:
        population_term = per_capita_production * production_population
    else:
        ln_term = math.log(max(1e-10, production_population / standard_population))
        population_factor = 1 + 0.3 * ln_term
        population_factor = max(0.1, population_factor)
        population_term = per_capita_production * standard_population * population_factor
    
    all_speed = get_attr_value(attrs_dict, all_resource_speed_attr)
    specific_speed = get_attr_value(attrs_dict, specific_resource_speed_attr)
    
    speed_factor = 1 + all_speed + specific_speed
    speed_factor = max(0.1, speed_factor)
    
    total_production = base_production + population_term
    
    return total_production * speed_factor


def calculate_wood_production(attrs_dict, production_population, standard_population=100):
    """计算木头生产效率"""
    return calculate_resource_production(
        attrs_dict, 3038, 3034, 3012, 3013, production_population, standard_population
    )


def calculate_stone_production(attrs_dict, production_population, standard_population=100):
    """计算石头生产效率"""
    return calculate_resource_production(
        attrs_dict, 3039, 3035, 3012, 3014, production_population, standard_population
    )


def calculate_food_production(attrs_dict, production_population, standard_population=100):
    """计算食物生产效率"""
    return calculate_resource_production(
        attrs_dict, 3040, 3036, 3012, 3015, production_population, standard_population
    )


def calculate_iron_production(attrs_dict, production_population, standard_population=100):
    """计算铁矿生产效率"""
    return calculate_resource_production(
        attrs_dict, 3041, 3037, 3012, 3016, production_population, standard_population
    )


def calculate_event_work_time(attrs_dict, workload, instant_work, work_population, standard_population):
    """计算事件工作时间"""
    remaining_work = workload - instant_work
    if remaining_work <= 0:
        return 0
    
    per_capita_efficiency = get_attr_value(attrs_dict, 3022)
    event_efficiency = get_attr_value(attrs_dict, 3047)
    work_speed = get_attr_value(attrs_dict, 3023)
    build_speed = get_attr_value(attrs_dict, 3001)
    
    return calculate_work_time(
        remaining_work, work_population, standard_population,
        per_capita_efficiency, event_efficiency, work_speed, build_speed
    )


def calculate_train_workload(base_workload, train_count):
    """计算训练工作量"""
    return base_workload * train_count


def calculate_heal_workload(base_workload, heal_count):
    """计算治疗工作量"""
    return base_workload * heal_count


def calculate_all_formulas(attrs_dict, variables):
    """计算所有公式"""
    results = {}
    
    results["建造时间"] = calculate_build_time(
        attrs_dict,
        variables.get("剩余工作量", 10000),
        variables.get("工作人口", 100),
        variables.get("标准工作人口", 100)
    )
    
    results["科研时间"] = calculate_research_time(
        attrs_dict,
        variables.get("剩余工作量", 10000),
        variables.get("工作人口", 100),
        variables.get("标准工作人口", 100)
    )
    
    results["治疗时间"] = calculate_heal_time(
        attrs_dict,
        variables.get("剩余工作量", 10000),
        variables.get("工作人口", 100),
        variables.get("标准工作人口", 100)
    )
    
    results["训练时间"] = calculate_train_time(
        attrs_dict,
        variables.get("剩余工作量", 10000),
        variables.get("工作人口", 100),
        variables.get("标准工作人口", 100)
    )
    
    results["事件时间"] = calculate_event_time(
        attrs_dict,
        variables.get("剩余工作量", 10000),
        variables.get("工作人口", 100),
        variables.get("标准工作人口", 100)
    )
    
    results["木头生产效率"] = calculate_wood_production(
        attrs_dict,
        variables.get("生产人口", 100),
        variables.get("标准工作人口", 100)
    )
    
    results["石头生产效率"] = calculate_stone_production(
        attrs_dict,
        variables.get("生产人口", 100),
        variables.get("标准工作人口", 100)
    )
    
    results["食物生产效率"] = calculate_food_production(
        attrs_dict,
        variables.get("生产人口", 100),
        variables.get("标准工作人口", 100)
    )
    
    results["铁矿生产效率"] = calculate_iron_production(
        attrs_dict,
        variables.get("生产人口", 100),
        variables.get("标准工作人口", 100)
    )
    
    results["事件工作时间"] = calculate_event_work_time(
        attrs_dict,
        variables.get("工作量", 10000),
        variables.get("立即加速工作量", 0),
        variables.get("工作人口", 100),
        variables.get("标准工作人口", 100)
    )
    
    results["训练工作量"] = calculate_train_workload(
        variables.get("单士兵训练工作量", 1000),
        variables.get("训练数量", 100)
    )
    
    results["治疗工作量"] = calculate_heal_workload(
        variables.get("单士兵治疗工作量", 1000),
        variables.get("治疗数量", 100)
    )
    
    return results


if __name__ == "__main__":
    test_attrs_json = '''
    {
        "subType": 1,
        "attrs": [
            {"attrId": 3001, "value": "600"},
            {"attrId": 3002, "value": "500"},
            {"attrId": 3013, "value": "2000"},
            {"attrId": 3015, "value": "2000"},
            {"attrId": 3016, "value": "2000"},
            {"attrId": 3022, "value": "360"},
            {"attrId": 3024, "value": "270"},
            {"attrId": 3025, "value": "54"},
            {"attrId": 3034, "value": "63"},
            {"attrId": 3035, "value": "25"},
            {"attrId": 3036, "value": "100"},
            {"attrId": 3037, "value": "13"},
            {"attrId": 3038, "value": "32400"},
            {"attrId": 3039, "value": "5760"},
            {"attrId": 3040, "value": "32400"}
        ]
    }
    '''
    
    attrs_dict = parse_attrs_json(test_attrs_json)
    print("解析后的属性值：")
    for attr_id, value in attrs_dict.items():
        name = ATTR_NAME_MAP.get(attr_id, str(attr_id))
        print(f"{name}({attr_id}): {value}")
    
    variables = {
        "剩余工作量": 10000,
        "工作人口": 100,
        "标准工作人口": 100,
        "生产人口": 100,
        "工作量": 10000,
        "立即加速工作量": 0,
        "基础训练工作量": 1000,
        "训练数量": 100
    }
    
    results = calculate_all_formulas(attrs_dict, variables)
    print("\n计算结果：")
    for name, value in results.items():
        print(f"{name}: {value:.4f}")