import subprocess, time, random, re, sys

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEV = "10AD3P0298003QF"

def direct(args, timeout=6):
    r = subprocess.run([ADB,'-s',DEV,'shell'] + args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def cmd_loc(*args, timeout=5):
    return direct(["cmd","location","providers"] + list(args), timeout=timeout)

def inject_all(lat, lng, acc=4.0):
    now_ms = str(int(time.time()*1000))
    lat_s = f"{lat:.7f}"
    lng_s = f"{lng:.7f}"
    for prov in ["gps", "network", "fused"]:
        cmd_loc("set-test-provider-location", prov,
                "--location", f"{lat_s},{lng_s}",
                "--accuracy", str(acc + (3 if prov == "network" else 0)),
                "--time", now_ms)

def get_counter():
    o,_,_ = direct(["dumpsys","location"], timeout=6)
    m = re.findall(r'locations = (\d+)', o)
    if m:
        return max(int(x) for x in m)
    return 0

def check_mock_active():
    o,_,_ = direct(["dumpsys","location"], timeout=6)
    mock_lines = [l for l in o.splitlines() if "mock" in l.lower() and "last location" in l and "M:" in l]
    return len(mock_lines) > 0, mock_lines[:3]

print("=" * 60, flush=True)
print("  STEP 1: 当前状态检查", flush=True)
print("=" * 60, flush=True)
mock_ok, mock_lines = check_mock_active()
print(f"  mock 活跃: {mock_ok}", flush=True)
for l in mock_lines:
    print(f"    {l[:120]}", flush=True)

print("\n" + "=" * 60, flush=True)
print("  STEP 2: 重新 Setup 注入环境", flush=True)
print("=" * 60, flush=True)

# Clean
for p in ["gps","network","fused"]:
    cmd_loc("set-test-provider-enabled", p, "false")
    cmd_loc("remove-test-provider", p)

# Add fresh
for name, flags in [
    ("gps", ["--supportsAltitude","--supportsSpeed","--supportsBearing","--requiresSatellite"]),
    ("network", ["--requiresNetwork"]),
    ("fused", ["--supportsAltitude","--supportsSpeed","--supportsBearing"]),
]:
    o,_,rc = cmd_loc("add-test-provider", name, *flags)
    print(f"  add {name}: rc={rc} {o[:50]}", flush=True)
    o,_,rc = cmd_loc("set-test-provider-enabled", name, "true")
    print(f"  enable {name}: rc={rc} {o[:50]}", flush=True)

time.sleep(0.5)
mock_ok, mock_lines = check_mock_active()
print(f"\n  setup后 mock 活跃: {mock_ok}", flush=True)

print("\n" + "=" * 60, flush=True)
print("  STEP 3: 记录乐跑初始 counter", flush=True)
print("=" * 60, flush=True)
c0 = get_counter()
print(f"  初始 locations counter = {c0}", flush=True)

print("\n" + "=" * 60, flush=True)
print("  STEP 4: 连续注入 20s + 实时监控 counter", flush=True)
print("=" * 60, flush=True)

lat, lng = 41.6872, 123.6306
t0 = time.time()
last_check = 0
check_interval = 3
checks = 0

while time.time() - t0 < 20:
    lat += 0.000012 + random.gauss(0, 0.000002)
    lng += 0.000020 + random.gauss(0, 0.000003)
    inject_all(lat, lng, acc=random.uniform(3.5, 7.0))
    time.sleep(0.5)
    
    elapsed = time.time() - t0
    if elapsed - last_check >= check_interval:
        last_check = elapsed
        c_now = get_counter()
        delta = c_now - c0
        checks += 1
        mock_ok, _ = check_mock_active()
        print(f"  [{int(elapsed)}s] counter={c_now}  Δ={delta:+4d}  mock={'ON' if mock_ok else 'OFF'}  📍({lat:.5f},{lng:.5f})", flush=True)

print("\n" + "=" * 60, flush=True)
print("  STEP 5: 最终状态", flush=True)
print("=" * 60, flush=True)

c_final = get_counter()
total_delta = c_final - c0
print(f"  初始 counter = {c0}", flush=True)
print(f"  最终 counter = {c_final}", flush=True)
print(f"  增量 = {total_delta}", flush=True)

if total_delta > 0:
    print(f"\n  ✅ 成功! 乐跑收到了 {total_delta} 个新位置!", flush=True)
else:
    print(f"\n  ❌ 失败! 乐跑没有收到任何新位置", flush=True)

print("\n  --- 检查乐跑的 location registration ---", flush=True)
o,_,_ = direct(["dumpsys","location"], timeout=6)
for l in o.splitlines():
    if "lptiyu" in l.lower() and ("registration" in l or "locations" in l or "Request" in l):
        if "passive" not in l.lower() and "min/max" not in l:
            print(f"    {l[:140]}", flush=True)

print("\n  --- 检查 LocationListener lptiyu ---", flush=True)
for l in o.splitlines():
    if "lptiyu" in l.lower() and "LocationListener" in l:
        print(f"    {l[:140]}", flush=True)