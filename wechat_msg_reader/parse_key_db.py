"""尝试从 key_info.db 中提取数据库密钥"""
import sqlite3
import struct

db_path = r'D:\wechat\xwechat_files\all_users\login\LING827323180\key_info.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT key_info_data FROM LoginKeyInfoTable")
rows = c.fetchall()

for i, (data,) in enumerate(rows):
    print(f"\n=== Row {i} ({len(data)} bytes) ===")
    print(f"hex: {data.hex()}")
    
    # 尝试解析 protobuf
    # 常见 field: 0x0a (field 1, length-delimited), 0x12 (field 2), etc.
    pos = 0
    while pos < len(data):
        tag = data[pos]
        field_num = tag >> 3
        wire_type = tag & 0x07
        pos += 1
        
        if wire_type == 0:  # varint
            val = 0
            shift = 0
            while pos < len(data) and data[pos] & 0x80:
                val |= (data[pos] & 0x7f) << shift
                shift += 7
                pos += 1
            if pos < len(data):
                val |= (data[pos] & 0x7f) << shift
                pos += 1
            print(f"  field {field_num} (varint): {val}")
        elif wire_type == 2:  # length-delimited
            if pos >= len(data):
                break
            length = data[pos]
            pos += 1
            if length & 0x80:  # multi-byte length
                len_bytes = []
                while pos < len(data) and data[pos-1] & 0x80:
                    len_bytes.append(data[pos-1] & 0x7f)
                    pos += 1
                # simplified, just use the last byte
            chunk = data[pos:pos+length]
            pos += length
            # 尝试显示为 hex 或文本
            if len(chunk) == 32:
                print(f"  field {field_num} (32 bytes): {chunk.hex()}")
            elif len(chunk) == 16:
                print(f"  field {field_num} (16 bytes): {chunk.hex()}")
            elif len(chunk) <= 20:
                # 可能是时间戳
                if len(chunk) >= 4:
                    val = struct.unpack('<I', chunk[:4])[0]
                    print(f"  field {field_num} ({len(chunk)} bytes): {chunk.hex()} (le32={val})")
                else:
                    print(f"  field {field_num} ({len(chunk)} bytes): {chunk.hex()}")
            else:
                print(f"  field {field_num} ({len(chunk)} bytes): {chunk[:50].hex()}...")
        else:
            print(f"  field {field_num} (wire_type={wire_type}): {data[pos:pos+10].hex()}")
            break

conn.close()