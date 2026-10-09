import subprocess, time, sys

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEV = "10AD3P0298003QF"

def adb_cmd(args, timeout=10):
    r = subprocess.run([ADB,'-s',DEV] + args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def shell(cmd_str, timeout=10):
    return adb_cmd(["shell", cmd_str], timeout=timeout)

print("="*60, flush=True)
print("  Ninja Fake GPS 完整测试", flush=True)
print("="*60, flush=True)

# Step 1: 清理所有 test provider
print("\n[1] 关掉所有 test providers...", flush=True)
for p in ["gps","network","fused"]:
    shell(f"cmd location providers set-test-provider-enabled {p} false")
    shell(f"cmd location providers remove-test-provider {p}")

# Step 2: 强制重启 Ninja
print("\n[2] 强制重启 Ninja Fake GPS...", flush=True)
shell("am force-stop com.ninja.toolkit.pulse.fake.gps.pro")
time.sleep(1)
shell("am start -n com.ninja.toolkit.pulse.fake.gps.pro/com.ninja.toolkit.fake.pro.activity.MainActivity")
time.sleep(4)

# Step 3: 检查当前 location
print("\n[3] 当前 location:")
o,_,_ = shell("dumpsys location")
for l in o.splitlines():
    if "last location=Location[" in l and ("gps" in l or "fused" in l):
        print(f"  {l.strip()[:120]}")

# Step 4: 检查 appops
print("\n[4] Ninja appops:")
o,_,_ = shell("appops get com.ninja.toolkit.pulse.fake.gps.pro MOCK_LOCATION")
print(f"  MOCK_LOCATION: {o}")

# Step 5: 检查 MockLocationProvider service 是否在跑
print("\n[5] Ninja 服务状态:")
o,_,_ = shell("dumpsys activity services com.ninja.toolkit.pulse.fake.gps.pro 2>&1 | head -20")
print(o[:200])

# Step 6: 自动操作 Ninja UI - 用多点触摸先选位置再点 Play
print("\n[6] 自动操作 Ninja UI:", flush=True)
# 先 dump UI 看看现在有什么
shell("uiautomator dump /sdcard/ninja.xml")
o,_,_ = shell("cat /sdcard/ninja.xml")
import re
# 找到所有 clickable 元素
buttons = re.findall(r'text="([^"]*)".*?resource-id="([^"]*)".*?clickable="true".*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', o)
print(f"  找到 {len(buttons)} 个可点击元素")
for txt, rid, x1, y1, x2, y2 in buttons:
    cx, cy = (int(x1)+int(x2))//2, (int(y1)+int(y2))//2
    print(f"    text='{txt[:20]}' id={rid.split(':')[-1] if ':' in rid else rid} center=({cx},{cy})")

# Step 7: 点击 Play 按钮并监测
print("\n[7] 点击 Play 按钮 (456, 1499)...", flush=True)
shell("input tap 456 1499")
time.sleep(5)

# Step 8: 检查 location
print("\n[8] 点击 Play 后 location:")
o,_,_ = shell("dumpsys location")
for l in o.splitlines():
    if "last location=Location[" in l and ("gps" in l or "fused" in l):
        has_mock = "mock" in l.lower()
        marker = "❌ MOCK" if has_mock else "✅ REAL"
        print(f"  {marker} {l.strip()[:150]}")

# Step 9: 尝试用摇杆让它移动
print("\n[9] 尝试用摇杆 (从中心向上滑动 -> 向北移动)...", flush=True)
joystick_cx, joystick_cy = 264, 1499
shell(f"input swipe {joystick_cx} {joystick_cy} {joystick_cx} {joystick_cy-200} 500")
time.sleep(1)
shell("input tap 456 1499")  # 点 Play 开始
time.sleep(5)

print("\n[10] 摇杆操作后 location:")
o,_,_ = shell("dumpsys location")
for l in o.splitlines():
    if "last location=Location[" in l and ("gps" in l or "fused" in l):
        has_mock = "mock" in l.lower()
        marker = "❌ MOCK" if has_mock else "✅ REAL"
        print(f"  {marker} {l.strip()[:150]}")

print("\n完成!", flush=True)