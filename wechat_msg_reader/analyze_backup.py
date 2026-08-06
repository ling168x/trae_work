"""分析备份 ChatPackage 文件结构"""
import os, struct, re

bp = r'D:\wechat\xwechat_files\Backup\LING827323180\ebc21d5d56a0a15e534c88e8f0132376\files\2\f844dccf27218b0011d9ef9b3c38d002abeb6245391f83b42b1a78cfd98e33f3\ChatPackage\1760528080000-1761799259000'

with open(bp, 'rb') as f:
    data = f.read()

print(f"文件大小: {len(data)} bytes")

# 文件头: RMFH
# 格式分析
header = data[:32]
print(f"Header: {header.hex()}")

# 尝试识别结构
# 可能是: 4字节魔数 + 4字节时间戳 + 4字节时间戳 + 4字节版本 + ...
magic = data[:4]  # RMFH
ts1 = struct.unpack('<I', data[4:8])[0]  # 小端序
ts2 = struct.unpack('<I', data[8:12])[0]
ver = struct.unpack('<I', data[12:16])[0]
print(f"Magic: {magic}")
print(f"Field1: {ts1} (0x{ts1:08X})")
print(f"Field2: {ts2} (0x{ts2:08X})")
print(f"Field3: {ver} (0x{ver:08X})")

# 尝试不同的格式
# 可能是大端序
ts1_be = struct.unpack('>I', data[4:8])[0]
ts2_be = struct.unpack('>I', data[8:12])[0]
print(f"Field1(BE): {ts1_be} (0x{ts1_be:08X})")
print(f"Field2(BE): {ts2_be} (0x{ts2_be:08X})")

# 文件名的两个时间戳
from datetime import datetime
start_ts = 1760528080000
end_ts = 1761799259000
print(f"\n文件名时间范围: {datetime.fromtimestamp(start_ts/1000)} ~ {datetime.fromtimestamp(end_ts/1000)}")

# 在文件中搜索已知的时间戳模式
print(f"\n查找时间戳模式...")
# 搜索 1760528080 (秒级)
pattern = struct.pack('<I', 1760528080)
pos = data.find(pattern)
if pos >= 0:
    print(f"  找到 1760528080 (BE) 在 offset {pos}")

# 搜索 1760528080 大端
pattern = struct.pack('>I', 1760528080)
pos = data.find(pattern)
if pos >= 0:
    print(f"  找到 1760528080 (LE) 在 offset {pos}")

# 搜索可读文本
text = data.decode('utf-8', errors='ignore')
# 找出连续的可读文本
import re
readable = re.findall(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\w\s@.:/\-\(\)\[\]{}<>,;!?]+', text)
long_texts = [r for r in readable if len(r) > 10]
print(f"\n长文本片段 ({len(long_texts)}):")
for r in long_texts[:20]:
    print(f"  [{len(r)}]: {r[:100]}")

# 查找 message_content 格式
msg_texts = re.findall(r'[^:\x00-\x08\x0b\x0c\x0e-\x1f]{3,}:\n[\s\S]{1,100}', data.decode('utf-8', errors='ignore'))
print(f"\n消息格式片段 ({len(msg_texts)}):")
for m in msg_texts[:20]:
    print(f"  {m[:120]}")