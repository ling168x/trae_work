"""尝试解析 WeChat 备份文件 (RMFH 格式)"""
import os, struct, json

backup_dir = r'D:\wechat\xwechat_files\Backup\LING827323180\ebc21d5d56a0a15e534c88e8f0132376\files\2'

# 分析 RMFH 文件头
with open(os.path.join(backup_dir, 'data_0'), 'rb') as f:
    data = f.read(1024)

print(f"data_0 前 1KB:")
print(f"  魔数: {data[:4]}")
print(f"  hex: {data[:64].hex()}")
print(f"  text: {data[:64].decode('latin-1', errors='replace')}")

# RMFH 格式分析
# 通常 RMFH 文件结构:
# - 4 bytes: magic "RMFH"
# - 4 bytes: version
# - 4 bytes: header_size
# - N bytes: header data
# - M bytes: encrypted data

magic = data[:4]
if magic == b'RMFH':
    version = struct.unpack('<I', data[4:8])[0]
    header_size = struct.unpack('<I', data[8:12])[0]
    print(f"\nRMFH 格式:")
    print(f"  版本: {version}")
    print(f"  头部大小: {header_size}")
    
    header = data[12:12+header_size]
    print(f"  头部 hex: {header[:128].hex()}")
    
    # 加密数据开始位置
    data_start = 12 + header_size
    enc_data = data[data_start:data_start+64]
    print(f"  加密数据起始 ({data_start}): {enc_data.hex()}")

# 也检查 pkg_info.dat
with open(os.path.join(backup_dir, 'pkg_info.dat'), 'rb') as f:
    pkg_data = f.read()

print(f"\npkg_info.dat ({len(pkg_data)} bytes):")
print(f"  hex: {pkg_data.hex()}")

# 尝试 protobuf 解析
import struct
pos = 0
while pos < len(pkg_data):
    tag = pkg_data[pos]
    field_num = tag >> 3
    wire_type = tag & 0x07
    pos += 1
    if wire_type == 0:
        val = 0; shift = 0
        while pos < len(pkg_data) and pkg_data[pos] & 0x80:
            val |= (pkg_data[pos] & 0x7f) << shift
            shift += 7; pos += 1
        if pos < len(pkg_data):
            val |= (pkg_data[pos] & 0x7f) << shift; pos += 1
        print(f"  field {field_num} (varint): {val}")
    elif wire_type == 2:
        if pos >= len(pkg_data): break
        length = pkg_data[pos]; pos += 1
        chunk = pkg_data[pos:pos+length]; pos += length
        try:
            text = chunk.decode('utf-8')
            print(f"  field {field_num} (string): {text}")
        except:
            if len(chunk) <= 64:
                print(f"  field {field_num} ({len(chunk)} bytes): {chunk.hex()}")
            else:
                print(f"  field {field_num} ({len(chunk)} bytes): {chunk[:40].hex()}...")
    elif wire_type == 5:
        chunk = pkg_data[pos:pos+4]; pos += 4
        val = struct.unpack('<f', chunk)[0]
        print(f"  field {field_num} (float): {val}")
    else:
        print(f"  field {field_num} (wire_type={wire_type}): unknown")
        break