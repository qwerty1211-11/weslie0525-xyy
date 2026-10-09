import subprocess, time, re

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEV = "10AD3P0298003QF"
NINJA = "com.ninja.toolkit.pulse.fake.gps.pro"
LEPAO = "com.lptiyu.tanke"

def adb(*a):
    r = subprocess.run([ADB,"-s",DEV]+list(a), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=15)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def sh(cmd):
    return adb("shell", cmd)

def tap(x,y): adb("shell","input","tap",str(x),str(y))
def launch(pkg):
    adb("shell","am","force-stop",pkg); time.sleep(0.3)
    adb("shell","monkey","-p",pkg,"-c","android.intent.category.LAUNCHER","1")

print("=== 1. Mock 设置确认 ===")
out,_,_ = adb("shell","content","query","--uri","content://settings/secure/mock_location_app")
print("  mock_location_app:", out)
out,_,_ = adb("shell","content","query","--uri","content://settings/secure/mock_location")
print("  mock_location:", out)

print("\n=== 2. 重启 Ninja + play ===")
launch(NINJA)
time.sleep(3)
tap(456, 1499)
time.sleep(1)
tap(360, 828)
time.sleep(0.5)
tap(456, 1499)
time.sleep(2)

print("\n=== 3. dumpsys location grep mock ===")
out,_,_ = sh("dumpsys location")
mock_lines = [l for l in out.split("\n") if "mock" in l.lower() or "override" in l.lower()]
for l in mock_lines[-15:]:
    print(" ", l.strip())

print("\n=== 4. 各 provider 状态 ===")
for prov in ["network", "gps", "fused"]:
    prov_lines = [l for l in out.split("\n") if prov in l.lower()]
    for l in prov_lines[:3]:
        print(f"  [{prov}] {l.strip()}")

print("\n=== 5. 启动乐跑 ===")
launch(LEPAO)
time.sleep(4)

out2,_,_ = sh("dumpsys location")
lepao_lines = [l for l in out2.split("\n") if LEPAO in l]
for l in lepao_lines[-8:]:
    print(" ", l.strip())

print("\n=== 6. 最新 last location ===")
loc_lines = [l for l in out2.split("\n") if "last location=" in l]
for l in loc_lines[:8]:
    print(" ", l.strip())
    if "mock" in l:
        print("   ✅ MOCK 标记已出现!")