import subprocess, time, random, re

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEV = "10AD3P0298003QF"

def sh(args, timeout=6):
    r = subprocess.run([ADB,'-s',DEV,'shell'] + args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    return r.stdout.strip(), r.returncode

def get_counter():
    o,_ = sh(["dumpsys","location"])
    m = re.findall(r'locations = (\d+)', o)
    return max(int(x) for x in m) if m else 0

def check_mock_loc_flag():
    """检查最后一条 location 是否带 M: (mock 标记)"""
    o,_ = sh(["dumpsys","location"])
    lines = [l for l in o.splitlines() if "last location=" in l.lower() and "mock" in l.lower()]
    return lines[:5]

print("=" * 60, flush=True)
print("  TEST A: 先关掉 test provider, 只靠 settings mock_gps_location", flush=True)
print("=" * 60, flush=True)

for p in ["gps","network","fused"]:
    sh(["cmd","location","providers","set-test-provider-enabled",p,"false"])

# 开启传统 mock 模式
sh(["settings","put","secure","mock_location","1"])
sh(["settings","put","secure","allow_mock_location","1"])
sh(["settings","put","secure","mock_location_app","com.lptiyu.tanke"])

c0 = get_counter()
print(f"  初始 counter = {c0}", flush=True)

lat, lng = 41.6872, 123.6306
t0 = time.time()
last_check = 0
while time.time() - t0 < 15:
    lat += 0.000012 + random.gauss(0, 0.000002)
    lng += 0.000020 + random.gauss(0, 0.000003)
    
    # 用 VIVO 的 mock_gps_location 设置注入!
    sh(["settings","put","secure","mock_gps_location",f"{lat:.6f},{lng:.6f}"])
    
    time.sleep(0.5)
    if time.time() - last_check >= 3:
        last_check = time.time()
        c_now = get_counter()
        print(f"  [{int(time.time()-t0)}s] counter={c_now}  Δ={c_now-c0:+d}  📍({lat:.5f},{lng:.5f})", flush=True)

c1 = get_counter()
print(f"\n  TEST A 结束: {c1-c0:+d}", flush=True)

print("\n" + "=" * 60, flush=True)
print("  TEST B: 恢复 test provider + 同时用 settings", flush=True)
print("=" * 60, flush=True)

# 重新开启 test provider
for p in ["gps","network","fused"]:
    sh(["cmd","location","providers","set-test-provider-enabled",p,"true"])

# 先记录当前 counter + 最后一条 mock 位置
c2_before = get_counter()
print(f"  当前 counter = {c2_before}", flush=True)

t0 = time.time()
last_check = 0
while time.time() - t0 < 15:
    lat += 0.000012 + random.gauss(0, 0.000002)
    lng += 0.000020 + random.gauss(0, 0.000003)
    now_ms = str(int(time.time()*1000))
    for prov in ["gps","network","fused"]:
        sh(["cmd","location","providers","set-test-provider-location",prov,
            "--location",f"{lat:.7f},{lng:.7f}","--accuracy","4.0","--time",now_ms])
    sh(["settings","put","secure","mock_gps_location",f"{lat:.6f},{lng:.6f}"])
    time.sleep(0.5)
    if time.time() - last_check >= 3:
        last_check = time.time()
        c_now = get_counter()
        print(f"  [{int(time.time()-t0)}s] counter={c_now}  Δ={c_now-c2_before:+d}  📍({lat:.5f},{lng:.5f})", flush=True)

c2 = get_counter()
print(f"\n  TEST B 结束: {c2-c2_before:+d}", flush=True)

print("\n" + "=" * 60, flush=True)
print("  最终检查: last location 是否带 mock flag", flush=True)
print("=" * 60, flush=True)
lines = check_mock_loc_flag()
for l in lines:
    print(f"  {l[:150]}", flush=True)

o,_ = sh(["dumpsys","location"])
for l in o.splitlines():
    if "last location=" in l.lower() and ("gps" in l.lower() or "fused" in l.lower()):
        marker = "❌ MOCK" if "mock" in l.lower() else "✅ REAL"
        print(f"  {marker} {l.strip()[:150]}", flush=True)