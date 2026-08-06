"""搜索内存中所有可能的密钥 - 增强版"""
import ctypes, ctypes.wintypes as wt, struct, os, sys, hashlib, hmac, time, re, json

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
pid = get_pid()
h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
if not h: sys.exit(1)

# 枚举区域
regions = []
addr = 0; mbi = MBI()
while addr < 0x7FFFFFFFFFFF:
    if kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))==0: break
    if mbi.State==MEM_COMMIT and mbi.Protect in READABLE and 0<mbi.RegionSize<500*1024*1024:
        regions.append((mbi.BaseAddress, mbi.RegionSize))
    nxt = mbi.BaseAddress + mbi.RegionSize
    if nxt<=addr: break
    addr = nxt

print(f"可读区域: {len(regions)}")

# 搜索多种模式
key_map = {}
t0 = time.time()

# 模式1: x'<hex>' 其中 hex 长度在 64-192
hex_pat = re.compile(b"x'([0-9a-fA-F]{64,192})'")

for idx, (base, size) in enumerate(regions):
    data = read_mem(h, base, min(size, 2*1024*1024))
    if not data: continue
    for m in hex_pat.finditer(data):
        hs = m.group(1).decode()
        hl = len(hs)
        addr_f = base + m.start()
        
        if hl == 96:  # key + salt
            ek = hs[:64]; sk = hs[64:]
            for rel, salt, p1 in dbs:
                if sk == salt and salt not in key_map:
                    if verify_key(bytes.fromhex(ek), p1):
                        key_map[salt] = ek
                        print(f"  [96] {rel} enc_key={ek} @0x{addr_f:016X}")
                    break
        elif hl == 64:  # key only
            ek = bytes.fromhex(hs)
            for rel, salt, p1 in dbs:
                if salt not in key_map and verify_key(ek, p1):
                    key_map[salt] = hs
                    print(f"  [64] {rel} enc_key={hs} @0x{addr_f:016X}")
                    break
        elif hl > 96 and hl % 32 == 0:
            # 子串搜索
            for start in range(0, hl - 64 + 1, 2):
                sub = hs[start:start+64]
                ek = bytes.fromhex(sub)
                for rel, salt, p1 in dbs:
                    if salt not in key_map and verify_key(ek, p1):
                        key_map[salt] = sub
                        print(f"  [sub] {rel} enc_key={sub} @0x{addr_f:016X}")
                        break
                if len(key_map) > 0:
                    break
    if idx % 500 == 0:
        print(f"  [{idx}/{len(regions)}] {len(key_map)} keys, {time.time()-t0:.1f}s")

print(f"\n扫描完成: {len(key_map)}/{len(dbs)} 密钥, {time.time()-t0:.1f}s")

# 交叉验证
known_keys = list(key_map.values())
for rel, salt, p1 in dbs:
    if salt not in key_map:
        for ek_hex in known_keys:
            if verify_key(bytes.fromhex(ek_hex), p1):
                key_map[salt] = ek_hex
                print(f"  [CROSS] {rel} 可用已知密钥")
                break

for rel, salt, p1 in dbs:
    status = f"OK: {key_map[salt]}" if salt in key_map else "MISSING"
    print(f"  {rel}: {status}")

kernel32.CloseHandle(h)