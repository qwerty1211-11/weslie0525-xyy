import subprocess, sys, time

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEVICE = "10AD3P0298003QF"
PKG = "com.ninja.toolkit.pulse.fake.gps.pro"

def adb(*args, timeout=10):
    cmd = [ADB, "-s", DEVICE] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), -1

print("=" * 60)
print("  Vivo Android 13 · 配置 Mock 位置")
print("=" * 60)

# Android 13 content provider 路径
SECURE_URI = "content://settings/secure"
SECURE_PROJECTION = "name:value"

def get_secure(key):
    out, _, _ = adb("shell", "content", "query", "--uri", SECURE_URI,
                    "--where", f"name='{key}'", "--projection", SECURE_PROJECTION)
    for line in out.split("\n"):
        if key in line and "value=" in line:
            return line.split("value=")[-1].strip()
    return None

def put_secure(key, value):
    out, _, rc = adb("shell", "content", "insert", "--uri", SECURE_URI,
                     "--bind", f"name:s:{key}",
                     "--bind", f"value:s:{value}")
    if rc != 0:
        # 可能已存在，先 delete 再 insert
        adb("shell", "content", "delete", "--uri", SECURE_URI,
            "--where", f"name='{key}'")
        out, _, rc = adb("shell", "content", "insert", "--uri", SECURE_URI,
                         "--bind", f"name:s:{key}",
                         "--bind", f"value:s:{value}")
    return rc == 0

print("\n[1] 当前 secure settings 中的 location 相关项")
out, _, _ = adb("shell", "content", "query", "--uri", SECURE_URI,
                "--where", "name LIKE '%mock%' OR name LIKE '%location%'",
                "--projection", SECURE_PROJECTION)
print(out if out else "  (无)")

print("\n[2] 设置 mock_location_app = Ninja Fake GPS")
ok = put_secure("mock_location_app", PKG)
print(f"  content insert: {'✅' if ok else '❌'}")
val = get_secure("mock_location_app")
print(f"  验证: mock_location_app = {val}")

print("\n[3] 设置 mock_location = 1")
put_secure("mock_location", "1")
val = get_secure("mock_location")
print(f"  验证: mock_location = {val}")

print("\n[4] 设置 development_settings_enabled = 1 (保险)")
put_secure("development_settings_enabled", "1")

print("\n[5] 检查 global 设置里 location_mode")
out, _, _ = adb("shell", "content", "query",
                "--uri", "content://settings/global",
                "--where", "name='location_mode'",
                "--projection", SECURE_PROJECTION)
print(f"  location_mode: {out}")

print("\n[6] 授予 AppOps 权限")
for op in ["MOCK_LOCATION", "WRITE_SECURE_SETTINGS",
           "ACCESS_BACKGROUND_LOCATION", "ACTIVITY_RECOGNITION"]:
    adb("shell", "appops", "set", PKG, op, "allow")
out, _, _ = adb("shell", "appops", "get", PKG)
for line in out.split("\n"):
    if any(k in line.lower() for k in ["mock", "secure", "background_loc"]):
        print(f"  {line.strip()}")

print("\n[7] 强制打开 Ninja Fake GPS APP")
adb("shell", "am", "force-stop", PKG)
time.sleep(0.5)
adb("shell", "monkey", "-p", PKG,
    "-c", "android.intent.category.LAUNCHER", "1")
time.sleep(2.5)

print("\n[8] 最终验证 - secure 表里全部 mock 项")
out, _, _ = adb("shell", "content", "query", "--uri", SECURE_URI,
                "--where", "name LIKE '%mock%'",
                "--projection", SECURE_PROJECTION)
print(out if out else "  (无 mock_ 项)")

print("\n" + "=" * 60)
print("  ✅ 配置完成！")
print("  请确认手机上 Ninja Fake GPS PRO 已打开")
print("  如果弹出权限请求请全部允许")
print("  然后回到电脑跑主脚本:")
print("    python 步道乐跑极速版V3.py")
print("=" * 60)