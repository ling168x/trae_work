import random

K = 2.5

def calculate_battle_damage(
    attacker_atk=0,
    defender_def=0,
    attacker_skill_coeff=1.0,
    attacker_normal_dmg_boost=0,
    defender_normal_dmg_reduction=0,
    attacker_skill_dmg_boost=0,
    defender_skill_dmg_reduction=0,
    attacker_crit_rate=0,
    defender_crit_resist=0,
    attacker_crit_dmg=0,
    defender_crit_dmg_reduction=0,
    attacker_type="统御",
    defender_type="统御",
    attacker_counter_dmg_boost=0,
    defender_counter_dmg_reduction=0,
    attacker_morale=1,
    defender_morale=1,
    attacker_accum_dmg_boost=0,
    defender_accum_dmg_reduction=0,
    attacker_dmg_boost=0,
    defender_dmg_reduction=0,
    defender_vulnerable=0,
    is_pvp=False,
    attacker_pvp_boost=0,
    defender_pvp_reduction=0,
    pve_dmg_boost=0,
    attacker_command=0,
    defender_command=0,
    attacker_hit_rate=1.0,
    defender_dodge_rate=0,
    is_skill=False,
    simulate=True
):
    results = {
        "is_dodge": False,
        "is_crit": False,
        "is_counter": False,
        "step1_dodge_rate": 0,
        "step2_base_dmg": 0,
        "step3_skill_or_normal_dmg": 0,
        "step4_crit_dmg": 0,
        "step5_counter_dmg": 0,
        "step6_morale_dmg": 0,
        "step7_accum_dmg": 0,
        "step8_dmg_boost_reduction": 0,
        "step9_vulnerable_dmg": 0,
        "step10_pvp_pve_dmg": 0,
        "step11_final_dmg": 0,
        "final_damage": 0
    }
    
    counter_relations = {
        "统御": "战斗",
        "战斗": "谋略",
        "谋略": "统御"
    }
    
    step1_dodge_rate = max(0, defender_dodge_rate - attacker_hit_rate)
    results["step1_dodge_rate"] = step1_dodge_rate
    
    is_dodge = False
    if simulate:
        is_dodge = random.random() < step1_dodge_rate
    results["is_dodge"] = is_dodge
    
    if is_dodge:
        results["final_damage"] = 0
        return results
    
    step2_base_dmg = (attacker_atk ** 2) / (attacker_atk + K * defender_def) if attacker_atk > 0 else 0
    results["step2_base_dmg"] = step2_base_dmg
    
    if is_skill:
        step3_skill_or_normal_dmg = step2_base_dmg * (attacker_skill_coeff + attacker_skill_dmg_boost - defender_skill_dmg_reduction)
    else:
        step3_skill_or_normal_dmg = step2_base_dmg * (attacker_skill_coeff + attacker_normal_dmg_boost - defender_normal_dmg_reduction)
    results["step3_skill_or_normal_dmg"] = step3_skill_or_normal_dmg
    
    current_dmg = step3_skill_or_normal_dmg
    
    current_crit_rate = max(0, attacker_crit_rate - defender_crit_resist)
    is_crit = False
    if simulate:
        is_crit = random.random() < current_crit_rate
    results["is_crit"] = is_crit
    
    if is_crit:
        crit_multiplier = 1 + max(0, attacker_crit_dmg - defender_crit_dmg_reduction)
        step4_crit_dmg = current_dmg * crit_multiplier
    else:
        step4_crit_dmg = current_dmg
    results["step4_crit_dmg"] = step4_crit_dmg
    current_dmg = step4_crit_dmg
    
    is_counter = counter_relations.get(attacker_type) == defender_type
    results["is_counter"] = is_counter
    
    if is_counter:
        step5_counter_dmg = current_dmg * (1 + attacker_counter_dmg_boost) * (1 - defender_counter_dmg_reduction)
    else:
        step5_counter_dmg = current_dmg
    results["step5_counter_dmg"] = step5_counter_dmg
    current_dmg = step5_counter_dmg
    
    morale_ratio = attacker_morale / defender_morale if defender_morale != 0 else 1
    step6_morale_dmg = current_dmg * max(1, morale_ratio)
    results["step6_morale_dmg"] = step6_morale_dmg
    current_dmg = step6_morale_dmg
    
    accumulated_coeff = attacker_accum_dmg_boost - defender_accum_dmg_reduction
    if accumulated_coeff > 0:
        step7_accum_dmg = current_dmg * (1 + accumulated_coeff)
    else:
        step7_accum_dmg = current_dmg / (1 + abs(accumulated_coeff)) if accumulated_coeff != -1 else current_dmg * 1000
    results["step7_accum_dmg"] = step7_accum_dmg
    current_dmg = step7_accum_dmg
    
    step8_dmg_boost_reduction = current_dmg * (1 + attacker_dmg_boost) * (1 - defender_dmg_reduction)
    results["step8_dmg_boost_reduction"] = step8_dmg_boost_reduction
    current_dmg = step8_dmg_boost_reduction
    
    step9_vulnerable_dmg = current_dmg * (1 + defender_vulnerable)
    results["step9_vulnerable_dmg"] = step9_vulnerable_dmg
    current_dmg = step9_vulnerable_dmg
    
    if is_pvp:
        step10_pvp_pve_dmg = current_dmg * (1 + attacker_pvp_boost - defender_pvp_reduction)
    else:
        step10_pvp_pve_dmg = current_dmg * (1 + pve_dmg_boost)
    results["step10_pvp_pve_dmg"] = step10_pvp_pve_dmg
    current_dmg = step10_pvp_pve_dmg
    
    if attacker_command > defender_command:
        step11_final_dmg = current_dmg * 1.05
    else:
        step11_final_dmg = current_dmg
    results["step11_final_dmg"] = step11_final_dmg
    
    results["final_damage"] = int(step11_final_dmg)
    
    return results

def calculate_damage_summary(
    attacker_atk=0,
    defender_def=0,
    attacker_skill_coeff=1.0,
    attacker_normal_dmg_boost=0,
    defender_normal_dmg_reduction=0,
    attacker_skill_dmg_boost=0,
    defender_skill_dmg_reduction=0,
    attacker_crit_rate=0,
    defender_crit_resist=0,
    attacker_crit_dmg=0,
    defender_crit_dmg_reduction=0,
    attacker_type="统御",
    defender_type="统御",
    attacker_counter_dmg_boost=0,
    defender_counter_dmg_reduction=0,
    attacker_morale=1,
    defender_morale=1,
    attacker_accum_dmg_boost=0,
    defender_accum_dmg_reduction=0,
    attacker_dmg_boost=0,
    defender_dmg_reduction=0,
    defender_vulnerable=0,
    is_pvp=False,
    attacker_pvp_boost=0,
    defender_pvp_reduction=0,
    pve_dmg_boost=0,
    attacker_command=0,
    defender_command=0,
    attacker_hit_rate=1.0,
    defender_dodge_rate=0
):
    normal_result = calculate_battle_damage(
        attacker_atk=attacker_atk,
        defender_def=defender_def,
        attacker_skill_coeff=attacker_skill_coeff,
        attacker_normal_dmg_boost=attacker_normal_dmg_boost,
        defender_normal_dmg_reduction=defender_normal_dmg_reduction,
        attacker_skill_dmg_boost=attacker_skill_dmg_boost,
        defender_skill_dmg_reduction=defender_skill_dmg_reduction,
        attacker_crit_rate=attacker_crit_rate,
        defender_crit_resist=defender_crit_resist,
        attacker_crit_dmg=attacker_crit_dmg,
        defender_crit_dmg_reduction=defender_crit_dmg_reduction,
        attacker_type=attacker_type,
        defender_type=defender_type,
        attacker_counter_dmg_boost=attacker_counter_dmg_boost,
        defender_counter_dmg_reduction=defender_counter_dmg_reduction,
        attacker_morale=attacker_morale,
        defender_morale=defender_morale,
        attacker_accum_dmg_boost=attacker_accum_dmg_boost,
        defender_accum_dmg_reduction=defender_accum_dmg_reduction,
        attacker_dmg_boost=attacker_dmg_boost,
        defender_dmg_reduction=defender_dmg_reduction,
        defender_vulnerable=defender_vulnerable,
        is_pvp=is_pvp,
        attacker_pvp_boost=attacker_pvp_boost,
        defender_pvp_reduction=defender_pvp_reduction,
        pve_dmg_boost=pve_dmg_boost,
        attacker_command=attacker_command,
        defender_command=defender_command,
        attacker_hit_rate=attacker_hit_rate,
        defender_dodge_rate=defender_dodge_rate,
        is_skill=False,
        simulate=False
    )
    
    skill_result = calculate_battle_damage(
        attacker_atk=attacker_atk,
        defender_def=defender_def,
        attacker_skill_coeff=attacker_skill_coeff,
        attacker_normal_dmg_boost=attacker_normal_dmg_boost,
        defender_normal_dmg_reduction=defender_normal_dmg_reduction,
        attacker_skill_dmg_boost=attacker_skill_dmg_boost,
        defender_skill_dmg_reduction=defender_skill_dmg_reduction,
        attacker_crit_rate=attacker_crit_rate,
        defender_crit_resist=defender_crit_resist,
        attacker_crit_dmg=attacker_crit_dmg,
        defender_crit_dmg_reduction=defender_crit_dmg_reduction,
        attacker_type=attacker_type,
        defender_type=defender_type,
        attacker_counter_dmg_boost=attacker_counter_dmg_boost,
        defender_counter_dmg_reduction=defender_counter_dmg_reduction,
        attacker_morale=attacker_morale,
        defender_morale=defender_morale,
        attacker_accum_dmg_boost=attacker_accum_dmg_boost,
        defender_accum_dmg_reduction=defender_accum_dmg_reduction,
        attacker_dmg_boost=attacker_dmg_boost,
        defender_dmg_reduction=defender_dmg_reduction,
        defender_vulnerable=defender_vulnerable,
        is_pvp=is_pvp,
        attacker_pvp_boost=attacker_pvp_boost,
        defender_pvp_reduction=defender_pvp_reduction,
        pve_dmg_boost=pve_dmg_boost,
        attacker_command=attacker_command,
        defender_command=defender_command,
        attacker_hit_rate=attacker_hit_rate,
        defender_dodge_rate=defender_dodge_rate,
        is_skill=True,
        simulate=False
    )
    
    crit_result = calculate_battle_damage(
        attacker_atk=attacker_atk,
        defender_def=defender_def,
        attacker_skill_coeff=attacker_skill_coeff,
        attacker_normal_dmg_boost=attacker_normal_dmg_boost,
        defender_normal_dmg_reduction=defender_normal_dmg_reduction,
        attacker_skill_dmg_boost=attacker_skill_dmg_boost,
        defender_skill_dmg_reduction=defender_skill_dmg_reduction,
        attacker_crit_rate=attacker_crit_rate,
        defender_crit_resist=defender_crit_resist,
        attacker_crit_dmg=attacker_crit_dmg,
        defender_crit_dmg_reduction=defender_crit_dmg_reduction,
        attacker_type=attacker_type,
        defender_type=defender_type,
        attacker_counter_dmg_boost=attacker_counter_dmg_boost,
        defender_counter_dmg_reduction=defender_counter_dmg_reduction,
        attacker_morale=attacker_morale,
        defender_morale=defender_morale,
        attacker_accum_dmg_boost=attacker_accum_dmg_boost,
        defender_accum_dmg_reduction=defender_accum_dmg_reduction,
        attacker_dmg_boost=attacker_dmg_boost,
        defender_dmg_reduction=defender_dmg_reduction,
        defender_vulnerable=defender_vulnerable,
        is_pvp=is_pvp,
        attacker_pvp_boost=attacker_pvp_boost,
        defender_pvp_reduction=defender_pvp_reduction,
        pve_dmg_boost=pve_dmg_boost,
        attacker_command=attacker_command,
        defender_command=defender_command,
        attacker_hit_rate=attacker_hit_rate,
        defender_dodge_rate=defender_dodge_rate,
        is_skill=True,
        simulate=False
    )
    crit_result["is_crit"] = True
    crit_multiplier = 1 + max(0, attacker_crit_dmg - defender_crit_dmg_reduction)
    crit_result["step4_crit_dmg"] = crit_result["step3_skill_or_normal_dmg"] * crit_multiplier
    current_dmg = crit_result["step4_crit_dmg"]
    
    if crit_result["is_counter"]:
        crit_result["step5_counter_dmg"] = current_dmg * (1 + attacker_counter_dmg_boost) * (1 - defender_counter_dmg_reduction)
    else:
        crit_result["step5_counter_dmg"] = current_dmg
    current_dmg = crit_result["step5_counter_dmg"]
    
    crit_result["step6_morale_dmg"] = current_dmg * max(1, attacker_morale / defender_morale if defender_morale != 0 else 1)
    current_dmg = crit_result["step6_morale_dmg"]
    
    accumulated_coeff = attacker_accum_dmg_boost - defender_accum_dmg_reduction
    if accumulated_coeff > 0:
        crit_result["step7_accum_dmg"] = current_dmg * (1 + accumulated_coeff)
    else:
        crit_result["step7_accum_dmg"] = current_dmg / (1 + abs(accumulated_coeff)) if accumulated_coeff != -1 else current_dmg * 1000
    current_dmg = crit_result["step7_accum_dmg"]
    
    crit_result["step8_dmg_boost_reduction"] = current_dmg * (1 + attacker_dmg_boost) * (1 - defender_dmg_reduction)
    current_dmg = crit_result["step8_dmg_boost_reduction"]
    
    crit_result["step9_vulnerable_dmg"] = current_dmg * (1 + defender_vulnerable)
    current_dmg = crit_result["step9_vulnerable_dmg"]
    
    if is_pvp:
        crit_result["step10_pvp_pve_dmg"] = current_dmg * (1 + attacker_pvp_boost - defender_pvp_reduction)
    else:
        crit_result["step10_pvp_pve_dmg"] = current_dmg * (1 + pve_dmg_boost)
    current_dmg = crit_result["step10_pvp_pve_dmg"]
    
    if attacker_command > defender_command:
        crit_result["step11_final_dmg"] = current_dmg * 1.05
    else:
        crit_result["step11_final_dmg"] = current_dmg
    crit_result["final_damage"] = int(crit_result["step11_final_dmg"])
    
    return {
        "普攻伤害": normal_result["final_damage"],
        "技能伤害": skill_result["final_damage"],
        "暴击伤害": crit_result["final_damage"]
    }

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="战斗伤害计算器")
    parser.add_argument("--attacker_atk", type=float, default=0, help="攻击方英雄总攻击")
    parser.add_argument("--defender_def", type=float, default=0, help="受击方英雄总防御")
    parser.add_argument("--attacker_skill_coeff", type=float, default=1.0, help="攻方技能伤害系数")
    parser.add_argument("--attacker_normal_dmg_boost", type=float, default=0, help="攻方普攻伤害增加")
    parser.add_argument("--defender_normal_dmg_reduction", type=float, default=0, help="守方普攻伤害减少")
    parser.add_argument("--attacker_skill_dmg_boost", type=float, default=0, help="攻方技能伤害增加")
    parser.add_argument("--defender_skill_dmg_reduction", type=float, default=0, help="守方技能伤害减少")
    parser.add_argument("--attacker_crit_rate", type=float, default=0, help="攻方暴击率")
    parser.add_argument("--defender_crit_resist", type=float, default=0, help="守方抗暴率")
    parser.add_argument("--attacker_crit_dmg", type=float, default=0, help="攻方暴击伤害加成")
    parser.add_argument("--defender_crit_dmg_reduction", type=float, default=0, help="守方暴击伤害减免")
    parser.add_argument("--attacker_type", type=str, default="统御", choices=["统御", "战斗", "谋略"], help="攻击方类型")
    parser.add_argument("--defender_type", type=str, default="统御", choices=["统御", "战斗", "谋略"], help="防守方类型")
    parser.add_argument("--attacker_counter_dmg_boost", type=float, default=0, help="攻方克制伤害增加")
    parser.add_argument("--defender_counter_dmg_reduction", type=float, default=0, help="守方克制伤害减免")
    parser.add_argument("--attacker_morale", type=float, default=1, help="攻方士气")
    parser.add_argument("--defender_morale", type=float, default=1, help="守方士气")
    parser.add_argument("--attacker_accum_dmg_boost", type=float, default=0, help="攻方累加型伤害增加")
    parser.add_argument("--defender_accum_dmg_reduction", type=float, default=0, help="守方累加型伤害减免")
    parser.add_argument("--attacker_dmg_boost", type=float, default=0, help="攻方伤害加深")
    parser.add_argument("--defender_dmg_reduction", type=float, default=0, help="守方伤害减免")
    parser.add_argument("--defender_vulnerable", type=float, default=0, help="守方易伤伤害加成")
    parser.add_argument("--is_pvp", action="store_true", help="是否PVP模式")
    parser.add_argument("--attacker_pvp_boost", type=float, default=0, help="攻方PVP伤害加成")
    parser.add_argument("--defender_pvp_reduction", type=float, default=0, help="守方PVP伤害减免")
    parser.add_argument("--pve_dmg_boost", type=float, default=0, help="PVE伤害增加")
    parser.add_argument("--attacker_command", type=float, default=0, help="攻击方指挥")
    parser.add_argument("--defender_command", type=float, default=0, help="防守方指挥")
    parser.add_argument("--attacker_hit_rate", type=float, default=1.0, help="攻方命中率")
    parser.add_argument("--defender_dodge_rate", type=float, default=0, help="守方闪避率")
    
    args = parser.parse_args()
    
    results = calculate_damage_summary(
        attacker_atk=args.attacker_atk,
        defender_def=args.defender_def,
        attacker_skill_coeff=args.attacker_skill_coeff,
        attacker_normal_dmg_boost=args.attacker_normal_dmg_boost,
        defender_normal_dmg_reduction=args.defender_normal_dmg_reduction,
        attacker_skill_dmg_boost=args.attacker_skill_dmg_boost,
        defender_skill_dmg_reduction=args.defender_skill_dmg_reduction,
        attacker_crit_rate=args.attacker_crit_rate,
        defender_crit_resist=args.defender_crit_resist,
        attacker_crit_dmg=args.attacker_crit_dmg,
        defender_crit_dmg_reduction=args.defender_crit_dmg_reduction,
        attacker_type=args.attacker_type,
        defender_type=args.defender_type,
        attacker_counter_dmg_boost=args.attacker_counter_dmg_boost,
        defender_counter_dmg_reduction=args.defender_counter_dmg_reduction,
        attacker_morale=args.attacker_morale,
        defender_morale=args.defender_morale,
        attacker_accum_dmg_boost=args.attacker_accum_dmg_boost,
        defender_accum_dmg_reduction=args.defender_accum_dmg_reduction,
        attacker_dmg_boost=args.attacker_dmg_boost,
        defender_dmg_reduction=args.defender_dmg_reduction,
        defender_vulnerable=args.defender_vulnerable,
        is_pvp=args.is_pvp,
        attacker_pvp_boost=args.attacker_pvp_boost,
        defender_pvp_reduction=args.defender_pvp_reduction,
        pve_dmg_boost=args.pve_dmg_boost,
        attacker_command=args.attacker_command,
        defender_command=args.defender_command,
        attacker_hit_rate=args.attacker_hit_rate,
        defender_dodge_rate=args.defender_dodge_rate
    )
    
    print("=== 伤害计算结果 ===")
    for damage_type, value in results.items():
        print(f"{damage_type}: {value:.3f}")