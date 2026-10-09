import subprocess, time

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEV = "10AD3P0298003QF"

def sh(cmd):
    r = subprocess.run([ADB,'-s',DEV,'shell',cmd], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
    return r.stdout.strip()

def adb(*args):
    r = subprocess.run([ADB,'-s',DEV] + list(args), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10)
    return r.stdout.strip()

print("[1] 关 test providers...")
for p in ["gps","network","fused"]:
    adb("shell","cmd","location","providers","set-test-provider-enabled",p,"false")

print("[2] 重启 Ninja...")
adb("shell","am","force-stop","com.ninja.toolkit.pulse.fake.gps.pro")
time.sleep(1)
adb("shell","am","start","-n","com.ninja.toolkit.pulse.fake.gps.pro/com.ninja.toolkit.fake.pro.activity.MainActivity")
time.sleep(4)

print("[3] 在地图上选一个点 (360, 600) -> (360, 800)...")
adb("shell","input","tap","360","600")
time.sleep(1)

print("[4] 用摇杆向北滑动...")
adb("shell","input","swipe","264","1499","264","1299","800")
time.sleep(1)

print("[5] 点 Play...")
adb("shell","input","tap","456","1499")
time.sleep(3)

print("[6] 检查 MockLocationProvider service...")
svc = adb("shell","dumpsys","activity","services","com.ninja.toolkit.pulse.fake.gps.pro")
if "MockLocationProvider" in svc:
    print("  ✅ MockLocationProvider 已启动!")
else:
    print("  ❌ MockLocationProvider 未启动")
    print(f"  当前服务: {[l for l in svc.splitlines() if 'ServiceRecord' in l]}")

print("[7] 检查 location...")
loc = sh("dumpsys location 2>/dev/null | grep 'last location' | head -6")
for l in loc.splitlines():
    has_mock = "mock" in l.lower()
    marker = "❌ MOCK" if has_mock else "✅ REAL"
    print(f"  {marker} {l.strip()[:150]}")

print("[8] 如果没 mock，注入 10s 测试乐跑 counter...")
if loc.strip():
    import re
    def get_counter():
        o = sh("dumpsys location")
        m = re.findall(r'locations = (\d+)', o)
        return max(int(x) for x in m) if m else 0
    
    c0 = get_counter()
    print(f"  初始 counter = {c0}")
    t0 = time.time()
    while time.time() - t0 < 10:
        time.sleep(1)
    c1 = get_counter()
    print(f"  10s 后 counter = {c1}  增量 = {c1-c0}")

print("\n完成!")