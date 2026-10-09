import subprocess, time, random, re, sys

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEV = "10AD3P0298003QF"

def sh(args, timeout=6):
    r = subprocess.run([ADB,'-s',DEV,'shell'] + args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    return r.stdout.strip(), r.returncode

def get_counter():
    o,_ = sh(["dumpsys","location"])
    m = re.findall(r'locations = (\d+)', o)
    return max(int(x) for x in m) if m else 0

def get_last_location():
    o,_ = sh(["dumpsys","location"])
    for l in o.splitlines():
        if "last location=Location[" in l.lower() and ("gps" in l.lower() or "fused" in l.lower()):
            return l.strip()
    return "NOT FOUND"

print("=" * 60, flush=True)
print("  方案: 清空 mock_location_app + 传统 mock 模式", flush=True)
print("=" * 60, flush=True)

# 先关掉所有 test provider
for p in ["gps","network","fused"]:
    sh(["cmd","location","providers","set-test-provider-enabled",p,"false"])
time.sleep(0.5)

# 关键！清空 mock_location_app
print("  --- 关键步骤: 清空 mock_location_app ---", flush=True)
sh(["settings","put","secure","mock_location_app",""])
sh(["settings","put","secure","allow_mock_location","1"])
sh(["settings","put","secure","mock_location","1"])
o,_ = sh(["settings","get","secure","mock_location_app"])
print(f"  mock_location_app = '{o}'", flush=True)

# 重新 setup test provider
print("  --- Setup test providers ---", flush=True)
for p in ["gps","network","fused"]:
    sh(["cmd","location","providers","set-test-provider-enabled",p,"false"])
    sh(["cmd","location","providers","remove-test-provider",p])
for name, flags in [
    ("gps", ["--supportsAltitude","--supportsSpeed","--supportsBearing","--requiresSatellite"]),
    ("network", ["--requiresNetwork"]),
    ("fused", ["--supportsAltitude","--supportsSpeed","--supportsBearing"]),
]:
    o,rc = sh(["cmd","location","providers","add-test-provider",name] + flags)
    print(f"  add {name}: rc={rc}", flush=True)
    sh(["cmd","location","providers","set-test-provider-enabled",name,"true"])
time.sleep(0.5)

c0 = get_counter()
print(f"\n  初始 counter = {c0}", flush=True)

lat, lng = 41.6872, 123.6306
t0 = time.time()
last_check = 0
last_loc = None
mock_count = 0
total_checks = 0

while time.time() - t0 < 15:
    lat += 0.000012 + random.gauss(0, 0.000002)
    lng += 0.000020 + random.gauss(0, 0.000003)
    now_ms = str(int(time.time()*1000))
    for prov in ["gps","network","fused"]:
        sh(["cmd","location","providers","set-test-provider-location",prov,
            "--location",f"{lat:.7f},{lng:.7f}","--accuracy","4.0","--time",now_ms])
    time.sleep(0.5)
    if time.time() - last_check >= 3:
        last_check = time.time()
        c_now = get_counter()
        loc = get_last_location()
        is_mock = "mock" in loc.lower()
        if is_mock: mock_count += 1
        total_checks += 1
        print(f"  [{int(time.time()-t0)}s] counter={c_now} d={c_now-c0:+d} mock={is_mock}  📍({lat:.5f},{lng:.5f})", flush=True)
        if loc != last_loc:
            print(f"    -> {loc[:120]}", flush=True)
            last_loc = loc

c1 = get_counter()
print(f"\n  总结:", flush=True)
print(f"  乐跑 counter 增量: {c1-c0}", flush=True)
print(f"  mock 标记出现率: {mock_count}/{total_checks}", flush=True)
if c1 - c0 > 0 and mock_count < total_checks:
    print(f"  ✅✅✅ 可能有突破！位置增加且部分没有 mock 标记！", flush=True)
elif c1 - c0 > 0:
    print(f"  ⚠️ counter 增加了但全部带 mock 标记", flush=True)
else:
    print(f"  ❌ counter 没增加", flush=True)