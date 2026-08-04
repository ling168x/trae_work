import tkinter as tk
from tkinter import ttk, scrolledtext
from formula_calculator import (
    parse_attrs_json, calculate_all_formulas, ATTR_NAME_MAP, ATTR_WAN_MAP,
    FORMULA_CATEGORIES
)


class FormulaCalculatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("属性公式计算器")
        self.root.geometry("1400x800")
        self.root.resizable(True, True)
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        bg_color = '#f5f5f5'
        frame_bg = '#ffffff'
        inner_bg = '#f8f9fa'
        
        self.root.configure(bg=bg_color)
        
        self.style.configure('Main.TFrame', background=bg_color)
        self.style.configure('Panel.TFrame', background=frame_bg)
        self.style.configure('Inner.TFrame', background=inner_bg)
        
        self.style.configure('Title.TLabel', font=('Microsoft YaHei', 14, 'bold'), foreground='#2c3e50', background=bg_color)
        self.style.configure('PanelTitle.TLabel', font=('Microsoft YaHei', 11, 'bold'), foreground='#2c3e50', background=frame_bg)
        self.style.configure('SubTitle.TLabel', font=('Microsoft YaHei', 10, 'bold'), foreground='#333', background=inner_bg)
        self.style.configure('Label.TLabel', font=('Microsoft YaHei', 9), foreground='#555', background=inner_bg)
        self.style.configure('ResultTitle.TLabel', font=('Microsoft YaHei', 10), foreground='#666', background=frame_bg)
        self.style.configure('ResultValue.TLabel', font=('Microsoft YaHei', 14, 'bold'), foreground='#2563eb')
        self.style.configure('Calc.TButton', font=('Microsoft YaHei', 11, 'bold'), padding=8)
        self.style.configure('Var.TEntry', font=('Microsoft YaHei', 9))
        
        main_frame = ttk.Frame(root, style='Main.TFrame', padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        header = ttk.Frame(main_frame, style='Main.TFrame')
        header.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header, text="属性公式计算器", style='Title.TLabel').pack(side=tk.LEFT)
        
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        formula_tab = ttk.Frame(notebook, padding=5)
        formula_tab.pack(fill=tk.BOTH, expand=True)
        notebook.add(formula_tab, text="公式计算")
        
        attrs_tab = ttk.Frame(notebook, padding=5)
        attrs_tab.pack(fill=tk.BOTH, expand=True)
        notebook.add(attrs_tab, text="属性查看")
        
        self.create_formula_panel(formula_tab)
        self.create_attrs_panel(attrs_tab)
    
    def create_formula_panel(self, parent):
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.X, pady=(0, 5))
        
        json_frame = ttk.LabelFrame(top_frame, text="属性JSON输入", padding=5)
        json_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.json_text = scrolledtext.ScrolledText(json_frame, width=45, height=8, font=('Consolas', 9))
        self.json_text.pack(fill=tk.X, expand=True)
        
        default_json = '''{
    "subType": 1,
    "attrs": [
        {"attrId": 3001, "value": "600"},
        {"attrId": 3002, "value": "500"},
        {"attrId": 3022, "value": "360"},
        {"attrId": 3024, "value": "270"},
        {"attrId": 3025, "value": "54"},
        {"attrId": 3036, "value": "100"},
        {"attrId": 3040, "value": "32400"}
    ]
}'''
        self.json_text.insert(tk.END, default_json)
        
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(btn_frame, text="计算", style='Calc.TButton', command=self.calculate).pack(pady=5)
        
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill=tk.BOTH, expand=True)
        
        left_panel = ttk.LabelFrame(bottom_frame, text="输入参数", padding=5)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        left_panel.config(width=300)
        
        self.variables = {}
        
        param_rows = [
            ["剩余工作量", 10000],
            ["工作人口", 100],
            ["标准工作人口", 100],
            ["生产人口", 100],
            ["工作量", 10000],
            ["立即加速工作量", 0],
            ["单士兵训练工作量", 1000],
            ["训练数量", 100],
            ["单士兵治疗工作量", 1000],
            ["治疗数量", 100]
        ]
        
        for i, (name, default) in enumerate(param_rows):
            row_frame = ttk.Frame(left_panel)
            row_frame.pack(fill=tk.X, pady=3)
            
            ttk.Label(row_frame, text=name, width=16, font=('Microsoft YaHei', 9)).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(default))
            self.variables[name] = var
            entry = ttk.Entry(row_frame, width=12, textvariable=var, font=('Microsoft YaHei', 9))
            entry.pack(side=tk.RIGHT)
        
        middle_panel = ttk.LabelFrame(bottom_frame, text="属性值预览", padding=5)
        middle_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        middle_inner = ttk.Frame(middle_panel)
        middle_inner.pack(fill=tk.BOTH, expand=True)
        
        columns = ('id', 'name', 'value')
        self.attrs_tree = ttk.Treeview(middle_inner, columns=columns, show='headings', height=15)
        
        self.attrs_tree.heading('id', text='属性ID')
        self.attrs_tree.heading('name', text='属性名称')
        self.attrs_tree.heading('value', text='属性值')
        
        self.attrs_tree.column('id', width=80, anchor='center')
        self.attrs_tree.column('name', width=150, anchor='w')
        self.attrs_tree.column('value', width=100, anchor='e')
        
        scrollbar = ttk.Scrollbar(middle_inner, orient=tk.VERTICAL, command=self.attrs_tree.yview)
        self.attrs_tree.configure(yscroll=scrollbar.set)
        
        self.attrs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        right_panel = ttk.LabelFrame(bottom_frame, text="计算结果", padding=5)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        result_inner = ttk.Frame(right_panel)
        result_inner.pack(fill=tk.BOTH, expand=True)
        
        columns = 2
        formula_names = list(FORMULA_CATEGORIES.keys())
        
        self.result_labels = {}
        
        for i, formula_name in enumerate(formula_names):
            col = i % columns
            row = i // columns
            
            r_frame = ttk.Frame(result_inner)
            r_frame.grid(row=row, column=col, sticky='nsew', padx=5, pady=3)
            
            ttk.Label(r_frame, text=formula_name, style='ResultTitle.TLabel').pack()
            lbl = ttk.Label(r_frame, text="--", style='ResultValue.TLabel')
            lbl.pack(pady=2)
            self.result_labels[formula_name] = lbl
        
        result_inner.grid_columnconfigure(0, weight=1)
        result_inner.grid_columnconfigure(1, weight=1)
    
    def create_attrs_panel(self, parent):
        main_frame = ttk.Frame(parent)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="搜索属性：", font=('Microsoft YaHei', 9)).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, width=30, textvariable=self.search_var)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind('<KeyRelease>', self.filter_attrs)
        
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ('id', 'name', 'wan')
        self.all_attrs_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
        
        self.all_attrs_tree.heading('id', text='属性ID')
        self.all_attrs_tree.heading('name', text='属性名称')
        self.all_attrs_tree.heading('wan', text='万分比')
        
        self.all_attrs_tree.column('id', width=100, anchor='center')
        self.all_attrs_tree.column('name', width=200, anchor='w')
        self.all_attrs_tree.column('wan', width=80, anchor='center')
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.all_attrs_tree.yview)
        self.all_attrs_tree.configure(yscroll=scrollbar.set)
        
        self.all_attrs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.load_all_attrs_data()
    
    def load_all_attrs_data(self):
        for item in self.all_attrs_tree.get_children():
            self.all_attrs_tree.delete(item)
        
        for attr_def in sorted(ATTR_NAME_MAP.keys()):
            name = ATTR_NAME_MAP[attr_def]
            wan = "是" if ATTR_WAN_MAP.get(attr_def, 0) == 1 else "否"
            self.all_attrs_tree.insert('', tk.END, values=(attr_def, name, wan))
        
        self.all_attrs_list = [(k, ATTR_NAME_MAP[k], "是" if ATTR_WAN_MAP.get(k, 0) == 1 else "否") for k in sorted(ATTR_NAME_MAP.keys())]
    
    def filter_attrs(self, event):
        search_text = self.search_var.get().lower()
        
        for item in self.all_attrs_tree.get_children():
            self.all_attrs_tree.delete(item)
        
        for attr_id, name, wan in self.all_attrs_list:
            if search_text in str(attr_id).lower() or search_text in name.lower():
                self.all_attrs_tree.insert('', tk.END, values=(attr_id, name, wan))
    
    def format_time(self, hours):
        total_seconds = round(hours * 3600)
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    
    def update_attrs_display(self, attrs_dict):
        for item in self.attrs_tree.get_children():
            self.attrs_tree.delete(item)
        
        for attr_id in sorted(attrs_dict.keys()):
            value = attrs_dict[attr_id]
            name = ATTR_NAME_MAP.get(attr_id, f"未知属性({attr_id})")
            
            if ATTR_WAN_MAP.get(attr_id, 0) == 1:
                display_value = f"{value * 100:.2f}%"
            else:
                display_value = f"{value}"
            
            self.attrs_tree.insert('', tk.END, values=(attr_id, name, display_value))
    
    def calculate(self):
        json_text = self.json_text.get('1.0', tk.END).strip()
        
        if not json_text:
            return
        
        attrs_dict = parse_attrs_json(json_text)
        
        self.update_attrs_display(attrs_dict)
        
        variables = {}
        for name, var in self.variables.items():
            try:
                variables[name] = float(var.get())
            except ValueError:
                variables[name] = 0
        
        results = calculate_all_formulas(attrs_dict, variables)
        
        time_formulas = {"建造时间", "科研时间", "治疗时间", "训练时间", "事件时间", "事件工作时间"}
        
        for formula_name, value in results.items():
            if formula_name in self.result_labels:
                if formula_name in time_formulas:
                    self.result_labels[formula_name].config(text=self.format_time(value))
                elif value >= 0 and value < 10000:
                    self.result_labels[formula_name].config(text=f"{value:.4f}")
                else:
                    self.result_labels[formula_name].config(text=f"{value:.2f}")


if __name__ == '__main__':
    root = tk.Tk()
    app = FormulaCalculatorGUI(root)
    root.mainloop()