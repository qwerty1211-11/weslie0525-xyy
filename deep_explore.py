import subprocess, time, re, os

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEV = "10AD3P0298003QF"
NINJA = "com.ninja.toolkit.pulse.fake.gps.pro"
OUT = r"C:\Users\lenovo\PycharmProjects\PythonProject\screens"
os.makedirs(OUT, exist_ok=True)

def adb(*a):
    r = subprocess.run([ADB,"-s",DEV]+list(a), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=10)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def tap(x,y): adb("shell","input","tap",str(x),str(y))
def launch(pkg):
    adb("shell","am","force-stop",pkg); time.sleep(0.3)
    adb("shell","monkey","-p",pkg,"-c","android.intent.category.LAUNCHER","1")
    time.sleep(2.5)

def dump(filename):
    adb("shell","uiautomator", "dump", f"/sdcard/{filename}")
    adb("pull", f"/sdcard/{filename}", f"{OUT}/{filename}")
    adb("shell","screencap","-p",f"/sdcard/{filename.replace('.xml','.png')}")
    adb("pull", f"/sdcard/{filename.replace('.xml','.png')}", f"{OUT}/{filename.replace('.xml','.png')}")

def parse_ui(filename):
    with open(f"{OUT}/{filename}", encoding="utf-8", errors="replace") as f:
        xml = f.read()
    texts = re.findall(r'text="([^"]*)".*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml)
    ids = re.findall(r'resource-id="([^"]*)"', xml)
    texts = [(str(int(x1)+int(x2)//2), str(int(y1)+int(y2)//2), t) for t,x1,y1,x2,y2 in texts if t]
    return texts, list(set(ids))

print("=== Ninja Fake GPS PRO 完整功能探索 ===")
print()

launch(NINJA)
dump("n1_main.xml")
texts, ids = parse_ui("n1_main.xml")
print("1. 主界面:")
for t in texts: print(f"   ({t[0]},{t[1]}) '{t[2][:25]}'")
print(f"   IDs: {ids[:8]}")

print("\n2. 点菜单 (656,115):")
tap(656, 115); time.sleep(1.5)
dump("n2_menu.xml")
texts, ids = parse_ui("n2_menu.xml")
for t in texts: print(f"   ({t[0]},{t[1]}) '{t[2][:30]}'")
print(f"   IDs: {ids[:10]}")

print("\n3. 返回主界面，点搜索 (顶部左边):")
tap(70, 100); time.sleep(1)
tap(360, 100); time.sleep(0.5)
# 看看会不会有搜索界面
dump("n3_search.xml")
texts, ids = parse_ui("n3_search.xml")
for t in texts: print(f"   ({t[0]},{t[1]}) '{t[2][:30]}'")

print("\n4. 返回主界面，看看底部或侧边有没有模式切换:")
tap(0, 0); time.sleep(0.3)
press_key = adb("shell","input","keyevent","4")  # BACK
time.sleep(0.5)
tap(360, 150); time.sleep(0.5)  # 底部中部可能有tab
dump("n4_bottom.xml")
texts, ids = parse_ui("n4_bottom.xml")
for t in texts: print(f"   ({t[0]},{t[1]}) '{t[2][:30]}'")

print("\n5. 点 play 前先看看有没有模式选项:")
tap(456, 1499); time.sleep(1)  # play
tap(456, 1499); time.sleep(1)  # 可能是 stop
tap(264, 1499); time.sleep(1)  # joystick
dump("n5_joystick.xml")
texts, ids = parse_ui("n5_joystick.xml")
for t in texts: print(f"   ({t[0]},{t[1]}) '{t[2][:30]}'")
print(f"   IDs: {ids}")

print("\n6. 长按 play 或 joystick 看有没有菜单:")
adb("shell","input","keyevent","4"); time.sleep(0.5)  # back
tap(656, 115); time.sleep(1)  # 再打开菜单
# 找更多选项
for i in range(800, 1400, 150):
    tap(360, i); time.sleep(0.3)
    out, _, _ = adb("shell", "dumpsys", "window", "windows")
    if "FakeGPS" in out or "Route" in out.lower() or "GPX" in out:
        print(f"   在 y={i} 可能有新界面!")

dump("n6_taps.xml")
texts, ids = parse_ui("n6_taps.xml")
print("   最终界面元素:")
for t in texts: print(f"   ({t[0]},{t[1]}) '{t[2][:30]}'")
print(f"   IDs: {ids[:12]}")

print("\n=== 最终 mock 状态 ===")
out, _, _ = adb("shell","dumpsys","location")
mock_lines = [l for l in out.split("\n") if "mock" in l.lower() or "M:" in l]
for l in mock_lines[-6:]: print("  ", l.strip())