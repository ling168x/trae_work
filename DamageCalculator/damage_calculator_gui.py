import tkinter as tk
from tkinter import ttk
import ast
from damage_calculator import calculate_damage_summary

def parse_formula(text):
    text = text.strip()
    if not text:
        return 0.0
    if text.startswith('='):
        text = text[1:]
    try:
        return float(ast.literal_eval(text))
    except:
        try:
            return float(eval(text))
        except:
            try:
                return float(text)
            except:
                return 0.0

class HeroCalculator:
    def __init__(self, name=""):
        self.name = name
        self.atk = 0
        self.defense = 0
        self.skill_coeff = 1.0
        self.type = "统御"
        self.morale = 1.0
        self.command = 0
        self.crit_rate = 0
        self.crit_resist = 0
        self.crit_dmg = 0
        self.crit_reduction = 0
        self.normal_dmg_boost = 0
        self.normal_dmg_reduction = 0
        self.skill_dmg_boost = 0
        self.skill_dmg_reduction = 0
        self.dmg_boost = 0
        self.dmg_reduction = 0
        self.counter_boost = 0
        self.counter_reduction = 0
        self.accum_boost = 0
        self.accum_reduction = 0
        self.vulnerable = 0
        self.pvp_boost = 0
        self.pvp_reduction = 0
        self.hit_rate = 1.0
        self.dodge_rate = 0
        self.is_pvp = False

class DamageCalculatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("战斗伤害计算器")
        self.root.geometry("1100x670")
        self.root.resizable(True, True)
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        bg_color = '#e8e8e8'
        frame_bg = '#d8d8d8'
        inner_bg = '#c8c8c8'
        text_color = '#333333'
        label_color = '#555555'
        
        self.root.configure(bg=bg_color)
        
        self.style.configure('Main.TFrame', background=bg_color)
        self.style.configure('Panel.TFrame', background=frame_bg)
        self.style.configure('Inner.TFrame', background=inner_bg)
        
        self.style.configure('Title.TLabel', font=('Microsoft YaHei', 14, 'bold'), foreground='#2c3e50', background=bg_color)
        self.style.configure('PanelTitle.TLabel', font=('Microsoft YaHei', 11, 'bold'), foreground='#2c3e50', background=frame_bg)
        self.style.configure('SubTitle.TLabel', font=('Microsoft YaHei', 10, 'bold'), foreground=text_color, background=inner_bg)
        self.style.configure('Label.TLabel', font=('Microsoft YaHei', 9), foreground=label_color, background=inner_bg)
        self.style.configure('ResultTitle.TLabel', font=('Microsoft YaHei', 10), foreground=label_color, background=frame_bg)
        self.style.configure('ResultValue.TLabel', font=('Microsoft YaHei', 20, 'bold'), foreground='#dc2626', background='#fef2f2')
        self.style.configure('Hero.TButton', font=('Microsoft YaHei', 9), padding=4)
        self.style.configure('Calc.TButton', font=('Microsoft YaHei', 12, 'bold'), padding=8)
        
        main_frame = ttk.Frame(root, style='Main.TFrame', padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        header = ttk.Frame(main_frame, style='Main.TFrame')
        header.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header, text="战斗伤害计算器", style='Title.TLabel').pack(side=tk.LEFT)
        
        btn_frame = ttk.Frame(header, style='Main.TFrame')
        btn_frame.pack(side=tk.RIGHT)
        
        ttk.Button(btn_frame, text="+ 添加页签", style='Hero.TButton', command=self.add_hero).pack(side=tk.LEFT, padx=5)
        
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.heroes = []
        self.hero_frames = []
        self.hero_results = []
        
        self.add_hero("页签1")
        self.add_hero("页签2")
    
    def add_hero(self, name=""):
        hero = HeroCalculator(name if name else f"页签{len(self.heroes)+1}")
        self.heroes.append(hero)
        
        frame = ttk.Frame(self.notebook, padding=5)
        frame.pack(fill=tk.BOTH, expand=True)
        self.hero_frames.append(frame)
        
        self.create_hero_panel(frame, hero, len(self.heroes)-1)
        
        self.notebook.add(frame, text=hero.name)
    
    def create_hero_panel(self, parent, hero, index):
        main_inner = ttk.Frame(parent)
        main_inner.pack(fill=tk.BOTH, expand=True)
        
        left_panel = ttk.LabelFrame(main_inner, text=f"{hero.name}: 战斗基础", padding=8)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        left_inner = ttk.Frame(left_panel)
        left_inner.pack(fill=tk.BOTH, expand=True)
        
        attacker_frame = ttk.LabelFrame(left_inner, text="攻击方", padding=8)
        attacker_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        a_labels = ["总攻击", "技能系数", "攻击类型", "士气", "指挥"]
        hero.atk_var = tk.StringVar(value="961")
        hero.skill_var = tk.StringVar(value="0.63")
        hero.type_var = tk.StringVar(value="统御")
        hero.morale_var = tk.StringVar(value="1.0")
        hero.command_var = tk.StringVar(value="0")
        a_vars = [hero.atk_var, hero.skill_var, hero.type_var, hero.morale_var, hero.command_var]
        
        for i, (label, var) in enumerate(zip(a_labels, a_vars)):
            row_frame = ttk.Frame(attacker_frame)
            row_frame.pack(fill=tk.X, pady=3)
            
            ttk.Label(row_frame, text=label, width=10).pack(side=tk.LEFT)
            
            if label == "攻击类型":
                combo = ttk.Combobox(row_frame, values=['统御', '战斗', '谋略'], state='readonly', width=12, textvariable=var)
                combo.pack(side=tk.RIGHT)
            else:
                entry = ttk.Entry(row_frame, width=15, textvariable=var)
                entry.pack(side=tk.RIGHT)
        
        defender_frame = ttk.LabelFrame(left_inner, text="防御方", padding=8)
        defender_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        d_labels = ["总防御", "防御类型", "士气", "指挥", "伤害减免"]
        hero.def_var = tk.StringVar(value="1")
        hero.def_type_var = tk.StringVar(value="统御")
        hero.def_morale_var = tk.StringVar(value="1.0")
        hero.def_command_var = tk.StringVar(value="0")
        hero.def_dmg_red_var = tk.StringVar(value="0")
        d_vars = [hero.def_var, hero.def_type_var, hero.def_morale_var, hero.def_command_var, hero.def_dmg_red_var]
        
        for i, (label, var) in enumerate(zip(d_labels, d_vars)):
            row_frame = ttk.Frame(defender_frame)
            row_frame.pack(fill=tk.X, pady=3)
            
            ttk.Label(row_frame, text=label, width=10).pack(side=tk.LEFT)
            
            if label == "防御类型":
                combo = ttk.Combobox(row_frame, values=['统御', '战斗', '谋略'], state='readonly', width=12, textvariable=var)
                combo.pack(side=tk.RIGHT)
            else:
                entry = ttk.Entry(row_frame, width=15, textvariable=var)
                entry.pack(side=tk.RIGHT)
        
        right_panel = ttk.LabelFrame(main_inner, text="高级设定与修正", padding=8)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        right_inner = ttk.Frame(right_panel)
        right_inner.pack(fill=tk.BOTH, expand=True)
        
        crit_frame = ttk.LabelFrame(right_inner, text="暴击面板", padding=8)
        crit_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        hero.crit_rate_var = tk.StringVar(value="0")
        hero.crit_resist_var = tk.StringVar(value="0")
        hero.crit_dmg_var = tk.StringVar(value="0")
        hero.crit_red_var = tk.StringVar(value="0")
        
        crit_labels = ["暴击率", "抗暴率", "暴击伤害", "暴击减免"]
        crit_vars = [hero.crit_rate_var, hero.crit_resist_var, hero.crit_dmg_var, hero.crit_red_var]
        
        for i, (label, var) in enumerate(zip(crit_labels, crit_vars)):
            row_frame = ttk.Frame(crit_frame)
            row_frame.pack(fill=tk.X, pady=3)
            
            ttk.Label(row_frame, text=label, width=10).pack(side=tk.LEFT)
            entry = ttk.Entry(row_frame, width=15, textvariable=var)
            entry.pack(side=tk.RIGHT)
        
        damage_frame = ttk.LabelFrame(right_inner, text="伤害修正", padding=8)
        damage_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        damage_inner = ttk.Frame(damage_frame)
        damage_inner.pack(fill=tk.BOTH, expand=True)
        
        attack_correct_frame = ttk.LabelFrame(damage_inner, text="攻击修正", padding=5)
        attack_correct_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        hero.norm_boost_var = tk.StringVar(value="0")
        hero.skill_boost_var = tk.StringVar(value="0")
        hero.dmg_boost_var = tk.StringVar(value="0")
        hero.vulnerable_var = tk.StringVar(value="0")
        
        attack_labels = ["普攻增伤", "技能增伤", "伤害加深", "伤害加成"]
        attack_vars = [hero.norm_boost_var, hero.skill_boost_var, hero.dmg_boost_var, hero.vulnerable_var]
        
        for i, (label, var) in enumerate(zip(attack_labels, attack_vars)):
            row_frame = ttk.Frame(attack_correct_frame)
            row_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(row_frame, text=label, width=10).pack(side=tk.LEFT)
            entry = ttk.Entry(row_frame, width=10, textvariable=var)
            entry.pack(side=tk.RIGHT)
        
        defense_correct_frame = ttk.LabelFrame(damage_inner, text="防御修正", padding=5)
        defense_correct_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        hero.norm_red_var = tk.StringVar(value="0")
        hero.skill_red_var = tk.StringVar(value="0")
        hero.dmg_red_var = tk.StringVar(value="0")
        
        defense_labels = ["普攻减伤", "技能减伤", "伤害减免"]
        defense_vars = [hero.norm_red_var, hero.skill_red_var, hero.dmg_red_var]
        
        for i, (label, var) in enumerate(zip(defense_labels, defense_vars)):
            row_frame = ttk.Frame(defense_correct_frame)
            row_frame.pack(fill=tk.X, pady=2)
            
            ttk.Label(row_frame, text=label, width=10).pack(side=tk.LEFT)
            entry = ttk.Entry(row_frame, width=10, textvariable=var)
            entry.pack(side=tk.RIGHT)
        
        tactic_frame = ttk.LabelFrame(right_panel, text="战术设置", padding=8)
        tactic_frame.pack(fill=tk.X, pady=5)
        
        tactic_inner = ttk.Frame(tactic_frame)
        tactic_inner.pack(fill=tk.X)
        
        hero.counter_boost_var = tk.StringVar(value="0")
        hero.counter_red_var = tk.StringVar(value="0")
        hero.accum_boost_var = tk.StringVar(value="0")
        hero.accum_red_var = tk.StringVar(value="0")
        
        tactic_labels = ["克制增伤", "克制减伤", "累加增伤", "累加减伤"]
        tactic_vars = [hero.counter_boost_var, hero.counter_red_var, hero.accum_boost_var, hero.accum_red_var]
        
        for i, (label, var) in enumerate(zip(tactic_labels, tactic_vars)):
            row_frame = ttk.Frame(tactic_inner)
            row_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            ttk.Label(row_frame, text=label, width=10).pack(side=tk.LEFT)
            entry = ttk.Entry(row_frame, width=8, textvariable=var)
            entry.pack(side=tk.RIGHT)
        
        pvp_frame = ttk.Frame(tactic_frame)
        pvp_frame.pack(fill=tk.X, pady=5)
        
        hero.pvp_var = tk.BooleanVar(value=False)
        pvp_check = ttk.Checkbutton(pvp_frame, text="PVP模式", variable=hero.pvp_var)
        pvp_check.pack(side=tk.LEFT, padx=5)
        
        hero.pvp_boost_var = tk.StringVar(value="0")
        hero.pvp_red_var = tk.StringVar(value="0")
        
        pvp_boost_frame = ttk.Frame(pvp_frame)
        pvp_boost_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(pvp_boost_frame, text="PVP增伤", width=8).pack(side=tk.LEFT)
        entry = ttk.Entry(pvp_boost_frame, width=8, textvariable=hero.pvp_boost_var)
        entry.pack(side=tk.RIGHT)
        
        pvp_red_frame = ttk.Frame(pvp_frame)
        pvp_red_frame.pack(side=tk.LEFT, padx=10)
        ttk.Label(pvp_red_frame, text="PVP减伤", width=8).pack(side=tk.LEFT)
        entry = ttk.Entry(pvp_red_frame, width=8, textvariable=hero.pvp_red_var)
        entry.pack(side=tk.RIGHT)
        
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(button_frame, text="计算伤害", style='Calc.TButton', command=lambda idx=index: self.calculate(idx)).pack(pady=5)
        
        result_frame = ttk.LabelFrame(parent, text="计算结果", padding=10)
        result_frame.pack(fill=tk.X, pady=5)
        
        result_inner = ttk.Frame(result_frame)
        result_inner.pack(fill=tk.X)
        
        result_labels = {}
        result_names = ["普通攻击伤害", "技能攻击伤害", "暴击伤害"]
        
        for i, name in enumerate(result_names):
            r_frame = ttk.Frame(result_inner)
            r_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)
            
            ttk.Label(r_frame, text=name, style='ResultTitle.TLabel').pack()
            lbl = ttk.Label(r_frame, text="--", style='ResultValue.TLabel')
            lbl.pack(pady=5)
            result_labels[name] = lbl
        
        self.hero_results.append(result_labels)
    
    def calculate(self, index):
        if index >= len(self.heroes):
            return
        
        attacker = self.heroes[index]
        
        try:
            atk = parse_formula(attacker.atk_var.get())
            skill_coeff = parse_formula(attacker.skill_var.get())
            morale = parse_formula(attacker.morale_var.get())
            command = parse_formula(attacker.command_var.get())
            attacker_type = attacker.type_var.get()
            
            defender_def = parse_formula(attacker.def_var.get())
            defender_morale = parse_formula(attacker.def_morale_var.get())
            defender_command = parse_formula(attacker.def_command_var.get())
            defender_type = attacker.def_type_var.get()
            defender_dmg_red = parse_formula(attacker.def_dmg_red_var.get())
            
            crit_rate = parse_formula(attacker.crit_rate_var.get())
            crit_resist = parse_formula(attacker.crit_resist_var.get())
            crit_dmg = parse_formula(attacker.crit_dmg_var.get())
            crit_red = parse_formula(attacker.crit_red_var.get())
            
            norm_boost = parse_formula(attacker.norm_boost_var.get())
            norm_red = parse_formula(attacker.norm_red_var.get())
            skill_boost = parse_formula(attacker.skill_boost_var.get())
            skill_red = parse_formula(attacker.skill_red_var.get())
            dmg_boost = parse_formula(attacker.dmg_boost_var.get())
            dmg_red = parse_formula(attacker.dmg_red_var.get())
            
            counter_boost = parse_formula(attacker.counter_boost_var.get())
            counter_red = parse_formula(attacker.counter_red_var.get())
            accum_boost = parse_formula(attacker.accum_boost_var.get())
            accum_red = parse_formula(attacker.accum_red_var.get())
            vulnerable = parse_formula(attacker.vulnerable_var.get())
            
            pvp_boost = parse_formula(attacker.pvp_boost_var.get())
            pvp_red = parse_formula(attacker.pvp_red_var.get())
            is_pvp = attacker.pvp_var.get()
            
        except Exception as e:
            atk = 0
            skill_coeff = 1.0
            morale = 1.0
            command = 0
            attacker_type = "统御"
            defender_def = 1
            defender_morale = 1.0
            defender_command = 0
            defender_type = "统御"
            defender_dmg_red = 0
            crit_rate = 0
            crit_resist = 0
            crit_dmg = 0
            crit_red = 0
            norm_boost = 0
            norm_red = 0
            skill_boost = 0
            skill_red = 0
            dmg_boost = 0
            dmg_red = 0
            counter_boost = 0
            counter_red = 0
            accum_boost = 0
            accum_red = 0
            vulnerable = 0
            pvp_boost = 0
            pvp_red = 0
            is_pvp = False
        
        results = calculate_damage_summary(
            attacker_atk=atk,
            defender_def=defender_def,
            attacker_skill_coeff=skill_coeff,
            attacker_normal_dmg_boost=norm_boost,
            defender_normal_dmg_reduction=norm_red,
            attacker_skill_dmg_boost=skill_boost,
            defender_skill_dmg_reduction=skill_red,
            attacker_crit_rate=crit_rate,
            defender_crit_resist=crit_resist,
            attacker_crit_dmg=crit_dmg,
            defender_crit_dmg_reduction=crit_red,
            attacker_type=attacker_type,
            defender_type=defender_type,
            attacker_counter_dmg_boost=counter_boost,
            defender_counter_dmg_reduction=counter_red,
            attacker_morale=morale,
            defender_morale=defender_morale,
            attacker_accum_dmg_boost=accum_boost,
            defender_accum_dmg_reduction=accum_red,
            attacker_dmg_boost=dmg_boost,
            defender_dmg_reduction=defender_dmg_red,
            defender_vulnerable=vulnerable,
            is_pvp=is_pvp,
            attacker_pvp_boost=pvp_boost,
            defender_pvp_reduction=pvp_red,
            pve_dmg_boost=0,
            attacker_command=command,
            defender_command=defender_command,
            attacker_hit_rate=1.0,
            defender_dodge_rate=0
        )
        
        if index < len(self.hero_results):
            self.hero_results[index]["普通攻击伤害"].config(text=f"{results['普攻伤害']:.3f}")
            self.hero_results[index]["技能攻击伤害"].config(text=f"{results['技能伤害']:.3f}")
            self.hero_results[index]["暴击伤害"].config(text=f"{results['暴击伤害']:.3f}")

if __name__ == '__main__':
    root = tk.Tk()
    app = DamageCalculatorGUI(root)
    root.mainloop()