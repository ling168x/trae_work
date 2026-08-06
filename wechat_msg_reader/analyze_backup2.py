"""分析备份元数据文件"""
import os, struct

backup_dir = r'D:\wechat\xwechat_files\Backup\LING827323180\ebc21d5d56a0a15e534c88e8f0132376\files\2'

# 分析 detail.dat
detail_path = os.path.join(backup_dir, 'detail.dat')
print(f"=== detail.dat ({os.path.getsize(detail_path)} bytes) ===")
with open(detail_path, 'rb') as f:
    data = f.read()
print(f"hex: {data.hex()}")
# 5 bytes: 可能是 1字节类型 + 4字节数据
type_byte = data[0]
val = struct.unpack('<I', data[1:5])[0] if len(data) >= 5 else 0
print(f"type={type_byte}, val={val}")

# pkg_info.dat
pkg_path = os.path.join(backup_dir, 'pkg_info.dat')
print(f"\n=== pkg_info.dat ({os.path.getsize(pkg_path)} bytes) ===")
with open(pkg_path, 'rb') as f:
    data = f.read()
print(f"hex: {data.hex()}")
# 看起来是 protobuf 格式
# 尝试解码
try:
    import re
    # 提取可读文本
    text = data.decode('utf-8', errors='replace')
    readable = re.findall(r'[\w@.]+', text)
    print(f"可读字段: {readable}")
except:
    pass

# phone_history.dat
ph_path = os.path.join(backup_dir, 'phone_history.dat')
print(f"\n=== phone_history.dat ({os.path.getsize(ph_path)} bytes) ===")
with open(ph_path, 'rb') as f:
    data = f.read(500)
print(f"hex: {data.hex()}")

# tar_index.dat
ti_path = os.path.join(backup_dir, 'tar_index.dat')
print(f"\n=== tar_index.dat ({os.path.getsize(ti_path)} bytes) ===")
with open(ti_path, 'rb') as f:
    data = f.read(500)
print(f"hex: {data.hex()}")

# backup_time.dat
bt_path = os.path.join(backup_dir, 'backup_time.dat')
print(f"\n=== backup_time.dat ({os.path.getsize(bt_path)} bytes) ===")
with open(bt_path, 'rb') as f:
    data = f.read(500)
print(f"hex: {data.hex()}")

# 检查 backup.attr
attr_path = r'D:\wechat\xwechat_files\Backup\LING827323180\ebc21d5d56a0a15e534c88e8f0132376\backup.attr'
print(f"\n=== backup.attr ({os.path.getsize(attr_path)} bytes) ===")
with open(attr_path, 'rb') as f:
    data = f.read(500)
print(f"hex: {data.hex()}")

# 检查 alt_name.dat
alt_path = r'D:\wechat\xwechat_files\Backup\LING827323180\ebc21d5d56a0a15e534c88e8f0132376\alt_name.dat'
print(f"\n=== alt_name.dat ({os.path.getsize(alt_path)} bytes) ===")
with open(alt_path, 'rb') as f:
    data = f.read(500)
print(f"hex: {data.hex()}")