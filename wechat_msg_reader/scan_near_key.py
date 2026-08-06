"""扫描内存中已知密钥附近区域，寻找其他密钥"""
import ctypes, ctypes.wintypes as wt, struct, os, sys, hashlib, hmac, time, re

kernel32 = ctypes.windll.kernel32
MEM_COMMIT, PAGE_SZ = 0x1000, 4096
READABLE = {0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}

class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_uint64), ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD), ("_pad1", wt.DWORD),
        ("RegionSize", ctypes.c_uint64), ("State", wt.DWORD),
        ("Protect", wt.DWORD), ("Type", wt.DWORD), ("_pad2", wt.DWORD)]

def get_pid():
    import subprocess
    r = subprocess.run(["tasklist","/FI","IMAGENAME eq Weixin.exe","/FO","CSV","/NH"], capture_output=True, text=True)
    best = (0,0)
    for line in r.stdout.strip().split('\n'):
        if not line.strip(): continue
        p = line.strip('"').split('","')
        if len(p)>=5:
            pid=int(p[1]); mem=int(p[4].replace(',','').replace(' K','').strip() or '0')
            if mem>best[1]: best=(pid,mem)
    if not best[0]: print("[ERROR] 未运行"); sys.exit(1)
    return best[0]

def read_mem(h, addr, sz):
    buf = ctypes.create_string_buffer(sz)
    n = ctypes.c_size_t(0)
    if kernel32.ReadProcessMemory(h, ctypes.c_uint64(addr), buf, sz, ctypes.byref(n)):
        return buf.raw[:n.value]

def verify_key(enc_key, page1):
    salt = page1[:16]
    ms = bytes(b ^ 0x3a for b in salt)
    mk = hashlib.pbkdf2_hmac("sha512", enc_key, ms, 2, dklen=32)
    hd = page1[16:PAGE_SZ-80+16]
    ss = page1[PAGE_SZ-64:PAGE_SZ]
    h = hmac.new(mk, hd, hashlib.sha512)
    h.update(struct.pack('<I', 1))
    return h.digest() == ss

DB_DIR = r"D:\wechat\xwechat_files\LING827323180_96c1\db_storage"
dbs = []
for root, dirs, files in os.walk(DB_DIR):
    for f in files:
        if f.endswith('.db') and '-wal' not in f and '-shm' not in f:
            path = os.path.join(root, f)
            if os.path.getsize(path) < PAGE_SZ: continue
            with open(path, 'rb') as fh:
                p1 = fh.read(PAGE_SZ)
            dbs.append((os.path.relpath(path, DB_DIR), p1[:16].hex(), p1))

print(f"目标: {len(dbs)} 个DB")

# 已知 key
known_key = bytes.fromhex('4c64d04ecd632d43eaf1cccecd944c98388da266521f19ce855e07126f7d09e7')
known_salt = hex_str = '5341ee5e55eca8c3395bc3d7e37a1571'

pid = get_pid()
h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
if not h: sys.exit(1)

# 查找已知密钥的二进制
print("搜索已知密钥二进制...")
found_positions = []

# 枚举所有区域
regions = []
addr = 0; mbi = MBI()
while addr < 0x7FFFFFFFFFFF:
    if kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))==0: break
    if mbi.State==MEM_COMMIT and mbi.Protect in READABLE and 0<mbi.RegionSize<500*1024*1024:
        regions.append((mbi.BaseAddress, mbi.RegionSize))
    nxt = mbi.BaseAddress + mbi.RegionSize
    if nxt<=addr: break
    addr = nxt

for idx, (base, size) in enumerate(regions):
    data = read_mem(h, base, min(size, 2*1024*1024))
    if not data: continue
    pos = 0
    while True:
        pos = data.find(known_key, pos)
        if pos < 0: break
        found_positions.append(base + pos)
        pos += 1
    if idx % 500 == 0:
        print(f"  [{idx}/{len(regions)}] {len(found_positions)} found")

print(f"找到 {len(found_positions)} 个已知密钥位置")

# 在每个已知密钥位置附近搜索其他可能的密钥
found_keys = {}
for addr_key in found_positions:
    # 读取前后 1MB
    for offset in range(-1024*1024, 1024*1024, 512):
        data = read_mem(h, addr_key + offset, 256)
        if not data: continue
        # 尝试每 32 字节作为一个候选密钥
        for i in range(0, len(data) - 32 + 1, 1):
            candidate = data[i:i+32]
            if candidate == b'\x00' * 32 or len(set(candidate)) < 12:
                continue
            for rel, salt, p1 in dbs:
                if salt not in found_keys and verify_key(candidate, p1):
                    found_keys[salt] = candidate.hex()
                    print(f"  [FOUND] {rel}: {candidate.hex()} @0x{addr_key+offset+i:016X}")

print(f"\n找到 {len(found_keys)} 个密钥")
for rel, salt, p1 in dbs:
    if salt in found_keys:
        print(f"  OK: {rel}")
    else:
        print(f"  MISSING: {rel}")

kernel32.CloseHandle(h)