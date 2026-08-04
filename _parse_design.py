import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 300)
pd.set_option('display.max_colwidth', 100)

df = pd.read_excel(r'd:\Client\design\系统文档\Y-英雄系统-赵锴坤.xlsx', sheet_name='英雄系统', header=None)
print('=== Sheet1: 英雄系统 === Shape:', df.shape)
for i in range(25):
    row_vals = []
    for j in range(df.shape[1]):
        v = df.iloc[i, j]
        row_vals.append(str(v) if pd.notna(v) else '')
    print(f'R{i}: {row_vals}')