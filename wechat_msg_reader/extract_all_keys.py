"""直接搜索已知密钥在内存中的位置"""
import ctypes
import ctypes.wintypes as wt
import struct, os, sys, hashlib, hmac as hmac_mod, time, re, json

kernel32 = ctypes.windll.kernel32
MEM_COMMIT = 0x1000
READABLE = {0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}
PAGE_SZ = 4096

class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64), ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD), ("_pad1", wt.DWORD),
        ("RegionSize", ctypes.c_uint64), ("State", wt.DWORD),
        ("Protect", wt.DWORD), ("Type", wt.DWORD), ("_pad2", wt.DWORD),
    ]

def get_pid():
    import subprocess
    r = subprocess.run(["tasklist","/FI","IMAGENAME eq Weixin.exe","/FO","CSV","/NH"],
                       capture_output=True, text=True)
    best = (0,0)
    for line in r.stdout.strip().split('\n'):
        if not line.strip(): continue
        p = line.strip('"').split('","')
        if len(p)>=5:
            pid=int(p[1]); mem=int(p[4].replace(',','').replace(' K','').strip() or '0')
            if mem>best[1]: best=(pid,mem)
    if not best[0]: print("[ERROR] Weixin.exe 未运行"); sys.exit(1)
    print(f"[+] Weixin.exe PID={best[0]} ({best[1]//1024}MB)")
    return best[0]

def read_mem(h, addr, sz):
    buf = ctypes.create_string_buffer(sz)
    n = ctypes.c_size_t(0)
    if kernel32.ReadProcessMemory(h, ctypes.c_uint64(addr), buf, sz, ctypes.byref(n)):
        return buf.raw[:n.value]
    return None

def enum_regions(h):
    regs = []
    addr = 0
    mbi = MBI()
    while addr < 0x7FFFFFFFFFFF:
        if kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))==0: break
        if mbi.State==MEM_COMMIT and mbi.Protect in READABLE and 0<mbi.RegionSize<500*1024*1024:
            regs.append((mbi.BaseAddress, mbi.RegionSize))
        nxt = mbi.BaseAddress + mbi.RegionSize
        if nxt<=addr: break
        addr = nxt
    return regs

def verify_key_for_db(enc_key, db_page1):
    salt = db_page1[:16]
    iv = db_page1[PAGE_SZ - 80 : PAGE_SZ - 64]
    encrypted = db_page1[16 : PAGE_SZ - 80]
    mac_salt = bytes(b ^ 0x3a for b in salt)
    mac_key = hashlib.pbkdf2_hmac("sha512", enc_key, mac_salt, 2, dklen=32)
    hmac_data = db_page1[16 : PAGE_SZ - 80 + 16]
    stored_hmac = db_page1[PAGE_SZ - 64 : PAGE_SZ]
    h = hmac_mod.new(mac_key, hmac_data, hashlib.sha512)
    h.update(struct.pack('<I', 1))
    return h.digest() == stored_hmac

# 已知密钥
known_key = bytes.fromhex('4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7')

# 收集所有DB文件
DB_DIR = r"D:\wechat\xwechat_files\LING827323180_96c1\db_storage"
db_files = []
for root, dirs, files in os.walk(DB_DIR):
    for f in files:
        if f.endswith('.db') and not f.endswith('-wal') and not f.endswith('-shm'):
            path = os.path.join(root, f)
            rel = os.path.relpath(path, DB_DIR)
            sz = os.path.getsize(path)
            if sz < PAGE_SZ: continue
            with open(path, 'rb') as fh:
                page1 = fh.read(PAGE_SZ)
            salt = page1[:16].hex()
            db_files.append((rel, path, sz, salt, page1))

salt_to_dbs = {}
for rel, path, sz, salt, page1 in db_files:
    if salt not in salt_to_dbs:
        salt_to_dbs[salt] = []
    salt_to_dbs[salt].append(rel)

print(f"找到 {len(db_files)} 个数据库, {len(salt_to_dbs)} 个不同的salt")

# 先验证已知密钥是否还能用
for rel, path, sz, salt, page1 in db_files:
    if verify_key_for_db(known_key, page1):
        print(f"  [OK] {rel} 可用已知密钥解密")

# 打开进程
pid = get_pid()
h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
if not h: print("[ERROR] 无法打开进程"); sys.exit(1)

regions = enum_regions(h)
total_mb = sum(s for _,s in regions)/1024/1024
print(f"[+] 可读内存: {len(regions)} 区域, {total_mb:.0f}MB")

# 方法1: 搜索 x'<hex>' 格式
print("\n方法1: 搜索 x'<hex>' 格式...")
hex_re = re.compile(b"x'([0-9a-fA-F]{64,192})'")
key_map = {}
t0 = time.time()

for reg_idx, (base, size) in enumerate(regions):
    data = read_mem(h, base, size)
    if not data: continue
    for m in hex_re.finditer(data):
        hex_str = m.group(1).decode()
        hex_len = len(hex_str)
        if hex_len == 96:
            enc_key_hex = hex_str[:64]
            salt_hex = hex_str[64:]
            if salt_hex in salt_to_dbs and salt_hex not in key_map:
                enc_key = bytes.fromhex(enc_key_hex)
                for rel, path, sz, s, page1 in db_files:
                    if s == salt_hex:
                        if verify_key_for_db(enc_key, page1):
                            key_map[salt_hex] = enc_key_hex
                            print(f"  [FOUND] salt={salt_hex}, key={enc_key_hex}, DB={rel}")
                        break
        elif hex_len == 64:
            enc_key_hex = hex_str
            enc_key = bytes.fromhex(enc_key_hex)
            for rel, path, sz, salt_hex_db, page1 in db_files:
                if salt_hex_db not in key_map:
                    if verify_key_for_db(enc_key, page1):
                        key_map[salt_hex_db] = enc_key_hex
                        print(f"  [FOUND] salt={salt_hex_db}, key={enc_key_hex}, DB={rel}")
                        break
    if (reg_idx + 1) % 500 == 0:
        elapsed = time.time() - t0
        print(f"  [{len(key_map)}/{len(salt_to_dbs)}] {elapsed:.1f}s")

elapsed = time.time() - t0
print(f"方法1完成: {elapsed:.1f}s, 找到 {len(key_map)} 个密钥")

# 方法2: 直接用已知密钥验证所有DB
print("\n方法2: 交叉验证已知密钥...")
for rel, path, sz, salt, page1 in db_files:
    if salt not in key_map:
        if verify_key_for_db(known_key, page1):
            key_map[salt] = '4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7'
            print(f"  [CROSS] {rel} 可用已知密钥")

# 方法3: 搜索 WCDB 特有的密钥结构
# WCDB 在内存中可能存储 raw key + salt
print("\n方法3: 搜索可能的密钥结构...")
found_any = False
for reg_idx, (base, size) in enumerate(regions):
    data = read_mem(h, base, size)
    if not data: continue
    # 搜索已知密钥的二进制
    pos = data.find(known_key)
    if pos >= 0:
        addr = base + pos
        print(f"  找到已知密钥在 0x{addr:016X}")
        # 查看周围的数据
        ctx = data[max(0,pos-16):pos+64]
        print(f"  上下文: {ctx.hex()}")
        found_any = True
    if (reg_idx + 1) % 500 == 0:
        print(f"  [{reg_idx}/{len(regions)}]")

if not found_any:
    print("  未找到已知密钥的二进制数据")

# 输出结果
print(f"\n{'='*60}")
print(f"最终结果: {len(key_map)}/{len(salt_to_dbs)} 密钥")

result = {}
for rel, path, sz, salt, page1 in db_files:
    if salt in key_map:
        result[rel] = {"enc_key": key_map[salt], "salt": salt, "size_mb": round(sz/1024/1024, 1)}
        print(f"  OK: {rel}")
    else:
        print(f"  MISSING: {rel}")

with open(r'd:\traework\wechat-decrypt\wechat-decrypt-main\all_keys.json', 'w') as f:
    json.dump(result, f, indent=2)
print(f"\n密钥保存到: all_keys.json")

kernel32.CloseHandle(h)