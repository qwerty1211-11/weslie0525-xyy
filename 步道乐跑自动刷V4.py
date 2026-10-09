#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步道乐跑自动刷步数 V4.00
  - 自动配置 Ninja Fake GPS PRO 为 Mock 位置应用
  - 自动启动乐跑 APP (com.lptiyu.tanke)
  - 用 Ninja 的摇杆/搜索模拟 GPS 移动
  - 支持圆周绕圈 + 直走两种轨迹
  - 速度可调 (5-15 km/h 真实跑步区间)

前提条件:
  1. 手机已装 Ninja Fake GPS PRO (com.ninja.toolkit.pulse.fake.gps.pro)
  2. 手机已装步道乐跑 (com.lptiyu.tanke)
  3. USB 调试已开启
"""

import subprocess, sys, time, math, os, re, random
from datetime import datetime

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEVICE = "10AD3P0298003QF"
NINJA_PKG = "com.ninja.toolkit.pulse.fake.gps.pro"
LEPAO_PKG = "com.lptiyu.tanke"
SCREEN = "C:\\Users\\lenovo\\PycharmProjects\\PythonProject\\screens"

W, H = 720, 1600

JOYSTICK = (264, 1499)
PLAY = (456, 1499)
FAV = (296, 228)
CENTRE = (360, 828)
MENU = (656, 115)
LAT_LABEL = (421, 207)
LNG_LABEL = (421, 248)

LAT = 41.6872
LNG = 123.6306
STEP_LEN = 0.70

def adb(*args, timeout=10):
    cmd = [ADB, "-s", DEVICE] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), -1

def sh(cmd, timeout=10):
    return adb("shell", "sh", "-c", cmd, timeout=timeout)

def tap(x, y):
    adb("shell", "input", "tap", str(x), str(y))

def swipe(x1, y1, x2, y2, dur=300):
    adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(dur))

def text(s):
    escaped = s.replace(" ", "%s").replace(",", ",")
    adb("shell", "input", "text", escaped)

def press(key):
    adb("shell", "input", "keyevent", str(key))

def pkg_exists(pkg):
    out, _, _ = adb("shell", "pm", "list", "packages", pkg)
    return pkg in out

def get_secure(key):
    out, _, rc = adb("shell", "content", "query",
                     "--uri", f"content://settings/secure/{key}")
    if rc == 0 and f"value=" in out:
        for line in out.split("\n"):
            if f"name={key}" in line:
                m = re.search(r'value=([^,\s]+)', line)
                if m: return m.group(1)
    return None

def put_secure(key, value):
    adb("shell", "content", "delete", "--uri", "content://settings/secure",
        "--where", f"name='{key}'")
    out, _, rc = adb("shell", "content", "insert",
                     "--uri", "content://settings/secure",
                     "--bind", f"name:s:{key}",
                     "--bind", f"value:s:{value}")
    return rc == 0

def pkg_running(pkg):
    out, _, _ = adb("shell", "pidof", pkg)
    return bool(out.strip())

def launch(pkg):
    adb("shell", "am", "force-stop", pkg)
    time.sleep(0.3)
    adb("shell", "monkey", "-p", pkg,
        "-c", "android.intent.category.LAUNCHER", "1")

def grant_appops(pkg, op):
    adb("shell", "appops", "set", pkg, op, "allow")

def check_mock_status():
    app = get_secure("mock_location_app")
    mock = get_secure("mock_location")
    print(f"  mock_location_app = {app}")
    print(f"  mock_location     = {mock}")
    return app == NINJA_PKG and mock == "1"

# ========== 防检测模块 ==========

SPEED_FLUCTUATION = 0.18
GPS_JITTER_M = 4.5
PAUSE_CHANCE = 0.02
PAUSE_MIN_SEC = 2
PAUSE_MAX_SEC = 8

def jitter_coordinates(lat, lng):
    lat_jitter = (random.random() - 0.5) * 2 * GPS_JITTER_M / 111000
    lng_jitter = (random.random() - 0.5) * 2 * GPS_JITTER_M / (111000 * math.cos(math.radians(lat)))
    return lat + lat_jitter, lng + lng_jitter

def fluctuate_speed(base_speed):
    factor = 1 + (random.random() - 0.5) * 2 * SPEED_FLUCTUATION
    return max(base_speed * 0.5, base_speed * factor)

def anti_emulator_props():
    print("\n[防检测] 反模拟器属性检测")
    props_to_fake = {
        "ro.product.model": "V2230A",
        "ro.product.brand": "vivo",
        "ro.product.manufacturer": "vivo",
        "ro.product.device": "pd2230a",
        "ro.hardware": "mt6891",
        "ro.product.cpu.abi": "arm64-v8a",
        "ro.build.fingerprint": "vivo/pd2230a/pd2230a:13/TP1A.220624.014/compiler03161220:user/release-keys",
    }
    out, _, _ = adb("shell", "getprop", "ro.hardware")
    emulator_keywords = ["goldfish", "qemu", "ranchu", "sdk", "generic", "emulator", "bluestacks", "nox"]
    if any(k in out.lower() for k in emulator_keywords):
        print(f"  ⚠ 检测到模拟器硬件: {out.strip()}")
        print("  正在应用属性伪装...")
        for k, v in props_to_fake.items():
            adb("shell", "setprop", k, v)
        print("  ✅ 已伪装为 vivo V2230A 真机")
    else:
        print(f"  ✅ 硬件属性正常: {out.strip()}")

def anti_root_detect():
    print("\n[防检测] 反 Root 检测")
    root_paths = [
        "/system/bin/su", "/system/xbin/su", "/sbin/su",
        "/system/bin/.su", "/data/local/xbin/su",
        "/system/app/Superuser.apk", "/system/bin/.magisk",
        "/data/adb/magisk", "/system/etc/init.d/99SuperSUDaemon",
    ]
    found = []
    for p in root_paths:
        out, _, _ = adb("shell", "ls", p)
        if "No such file" not in out and "cannot access" not in out and out.strip():
            found.append(p)
    if found:
        print(f"  ⚠ 发现 Root 痕迹: {found}")
        print("  建议: Magisk 设置中对乐跑启用 DenyList + Zygisk")
    else:
        print("  ✅ Root 痕迹干净")

def anti_frida_xposed():
    print("\n[防检测] 反 Frida / Xposed 检测")
    frida_ports = [27042, 27043, 37277]
    for port in frida_ports:
        out, _, _ = adb("shell", "sh", "-c", f"cat /proc/net/tcp /proc/net/udp 2>/dev/null | grep -i {port:x}")
        if out.strip():
            print(f"  ⚠ Frida 端口 {port} 已打开")
        else:
            print(f"  ✅ Frida 端口 {port} 关闭")
    xposed_paths = [
        "/data/app/de.robv.android.xposed.installer*",
        "/system/bin/Xposed", "/system/framework/XposedBridge.jar",
    ]
    for p in xposed_paths:
        out, _, _ = adb("shell", "ls", p)
        if "No such file" not in out and "cannot access" not in out:
            print(f"  ⚠ 检测到 Xposed: {p}")
    out2, _, _ = adb("shell", "sh", "-c", "ps -A | grep -i xposed")
    if not out2.strip():
        print("  ✅ Xposed 进程未运行")

def clear_mock_trace():
    print("\n[防检测] 清除 Mock Location 痕迹")
    adb("shell", "settings", "delete", "secure", "mock_location_app")
    adb("shell", "settings", "delete", "secure", "mock_location")
    adb("shell", "content", "delete", "--uri", "content://settings/secure",
        "--where", "name='mock_location_app'")
    adb("shell", "content", "delete", "--uri", "content://settings/secure",
        "--where", "name='mock_location'")
    out, _, _ = sh("dumpsys location | grep -c 'mock provider override'")
    print(f"  当前 mock provider override 数: {out.strip()}")
    print("  ✅ Mock 系统标记已清除")

def set_gps_satellite_sim():
    print("\n[防检测] 模拟 GPS 卫星信号")
    gps_props = {
        "persist.sys.gps.satellites": str(random.randint(8, 12)),
        "persist.sys.gps.accuracy": str(random.uniform(3.0, 8.0)),
        "persist.sys.gps.speed": str(random.uniform(2.0, 4.0)),
        "persist.sys.gps.bearing": str(random.uniform(0, 360)),
    }
    for k, v in gps_props.items():
        adb("shell", "setprop", k, v)
    print(f"  ✅ 已模拟 {gps_props['persist.sys.gps.satellites']} 颗卫星")

def spoof_step_sensor():
    print("\n[防检测] 步数传感器校准")
    out, _, _ = adb("shell", "dumpsys", "sensorservice")
    has_step = "step" in out.lower()
    if has_step:
        print("  ✅ 设备有物理步进传感器")
    else:
        print("  ⚠ 未检测到步进传感器，乐跑可能用计步器替代")
    adb("shell", "dumpsys", "activity", "provider", "com.android.providers.settings.SettingsProvider")

def full_antidetect_setup():
    print("\n" + "=" * 60)
    print("  🛡️  防检测系统初始化")
    print("=" * 60)
    anti_emulator_props()
    anti_root_detect()
    anti_frida_xposed()
    spoof_step_sensor()
    print("\n✅ 防检测系统就绪")

def hide_mock_after_launch():
    print("\n[防检测] 乐跑启动后清除 Mock 痕迹")
    clear_mock_trace()
    set_gps_satellite_sim()
    print("  ✅ Mock 痕迹已清除，GPS 信号已模拟")

def setup_ninja_mock():
    print("\n[1/5] 配置 Ninja Fake GPS 为 Mock 位置应用")
    if pkg_exists(NINJA_PKG):
        print(f"  ✅ Ninja Fake GPS PRO 已安装")
    else:
        print(f"  ❌ 未找到 Ninja! 请先安装")
        return False

    put_secure("mock_location_app", NINJA_PKG)
    put_secure("mock_location", "1")
    grant_appops(NINJA_PKG, "MOCK_LOCATION")
    grant_appops(NINJA_PKG, "WRITE_SECURE_SETTINGS")
    grant_appops(NINJA_PKG, "ACCESS_BACKGROUND_LOCATION")

    if check_mock_status():
        print("  ✅ Mock 设置已正确配置")
    else:
        print("  ❌ Mock 设置失败")
        return False
    return True

def start_ninja_mock():
    print("\n[2/5] 启动 Ninja 并开启 Mock")
    launch(NINJA_PKG)
    time.sleep(3)
    print("  点 play 按钮启动 Mock...")
    tap(*PLAY)
    time.sleep(1.5)
    tap(*CENTRE)
    time.sleep(0.5)
    tap(*PLAY)
    time.sleep(1.5)

    out, _, _ = sh("dumpsys location | grep 'mock provider override' | tail -1")
    print(f"  最新 mock override: {out}")
    if "added" in out:
        print("  ✅ Ninja Mock 已激活")
    else:
        print("  ⚠ 未检测到 mock override，继续尝试...")
    return True

def setup_ninja_location(lat, lng):
    print(f"\n[3/5] 设置 Ninja 目标位置 ({lat}, {lng})")
    tap(*FAV)
    time.sleep(0.5)
    tap(*LAT_LABEL)
    time.sleep(0.3)
    press(67)
    text(f"{lat:.4f}")
    press(66)
    time.sleep(0.3)
    tap(*LNG_LABEL)
    press(67)
    text(f"{lng:.4f}")
    press(66)
    time.sleep(0.3)
    tap(*FAV)
    time.sleep(0.5)
    tap(*PLAY)
    print("  ✅ 位置已设")

def launch_lepao():
    print("\n[4/5] 启动步道乐跑")
    if pkg_exists(LEPAO_PKG):
        launch(LEPAO_PKG)
        time.sleep(4)
        print("  ✅ 乐跑已启动")
        return True
    else:
        print(f"  ❌ 未找到乐跑 APP (com.lptiyu.tanke)")
        return False

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlng/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def move_joystick(dx_ratio, dy_ratio, hold_ms=200):
    base_x, base_y = JOYSTICK
    max_off = 80
    target_x = int(base_x + dx_ratio * max_off)
    target_y = int(base_y + dy_ratio * max_off)
    swipe(base_x, base_y, target_x, target_y, hold_ms)

def get_last_location():
    out, _, _ = sh("dumpsys location | grep 'last location=' | head -1")
    m = re.search(r'Location\[gps?\s+M:(-?\d+),(-?\d+)', out)
    if m:
        return float(m.group(1))/10000000, float(m.group(2))/10000000
    m2 = re.search(r'(\d+\.?\d*),(\d+\.?\d*)', out)
    if m2:
        return float(m2.group(1)), float(m2.group(2))
    return None, None

def run_circle(speed_kmh=10, radius_m=300, duration_sec=600):
    print(f"\n[5/5] 开始刷跑 (🛡️ 防检测已启用)")
    print(f"  基础速度: {speed_kmh} km/h (±{int(SPEED_FLUCTUATION*100)}% 波动)")
    print(f"  轨迹: 圆周绕圈 (r={radius_m}m)")
    print(f"  时长: {duration_sec} 秒")
    est_steps = int(speed_kmh * 1000 / 3600 * duration_sec / STEP_LEN)
    print(f"  预计步数 ≈ {est_steps}")

    step_count = 0
    dist_total = 0.0
    start_time = time.time()
    pause_log = []

    for t in range(duration_sec):
        current_speed = fluctuate_speed(speed_kmh)
        step_per_move = max(1, int(current_speed * 1000 / 3600))
        angles_per_sec = current_speed * 1000 / 3600 / radius_m

        accumulated = angles_per_sec * t
        bearing_rad = math.radians(math.degrees(accumulated) + 90)
        dx = math.cos(bearing_rad)
        dy = math.sin(bearing_rad)
        move_joystick(dx, dy, hold_ms=random.randint(200, 320))
        step_count += step_per_move
        dist_total += step_per_move * STEP_LEN

        if PAUSE_CHANCE > 0 and random.random() < PAUSE_CHANCE and t > 20:
            pause_dur = random.randint(PAUSE_MIN_SEC, PAUSE_MAX_SEC)
            print(f"  🛑 暂停 {pause_dur}s (模拟等红灯/喝水)")
            pause_log.append(pause_dur)
            time.sleep(pause_dur)

        if t % 10 == 0 and t > 0:
            elapsed = int(time.time() - start_time)
            print(f"  运行 {elapsed}s | 步数 ≈ {step_count} | 距离 ≈ {dist_total:.0f}m | 当前 {current_speed:.1f}km/h")

        time.sleep(random.uniform(0.85, 1.15))

    elapsed = int(time.time() - start_time)
    print(f"\n  🏁 跑完! 耗时 {elapsed}s | 步数 ≈ {step_count} | 距离 ≈ {dist_total/1000:.2f}km")
    if pause_log:
        print(f"  ℹ 共暂停 {len(pause_log)} 次, 累计 {sum(pause_log)}s")
    return step_count, dist_total

def run_straight(speed_kmh=10, direction="forward", duration_sec=600):
    print(f"\n[5/5] 开始刷跑 (直线, 🛡️ 防检测已启用)")
    print(f"  基础速度: {speed_kmh} km/h (±{int(SPEED_FLUCTUATION*100)}% 波动) | 方向: {direction} | 时长: {duration_sec}s")

    step_count = 0
    dist_total = 0.0
    start_time = time.time()
    pause_log = []

    dx, dy = 0, -1
    if direction == "left": dx = -1; dy = 0
    elif direction == "right": dx = 1; dy = 0
    elif direction == "back": dx = 0; dy = 1

    for t in range(duration_sec):
        current_speed = fluctuate_speed(speed_kmh)
        step_per_move = max(1, int(current_speed * 1000 / 3600))

        jitter_dx = dx + (random.random() - 0.5) * 0.15
        jitter_dy = dy + (random.random() - 0.5) * 0.15
        jitter_len = math.sqrt(jitter_dx**2 + jitter_dy**2)
        jitter_dx /= jitter_len
        jitter_dy /= jitter_len
        move_joystick(jitter_dx, jitter_dy, hold_ms=random.randint(200, 320))
        step_count += step_per_move
        dist_total += step_per_move * STEP_LEN

        if PAUSE_CHANCE > 0 and random.random() < PAUSE_CHANCE and t > 20:
            pause_dur = random.randint(PAUSE_MIN_SEC, PAUSE_MAX_SEC)
            print(f"  🛑 暂停 {pause_dur}s (模拟休息)")
            pause_log.append(pause_dur)
            time.sleep(pause_dur)

        if t % 10 == 0 and t > 0:
            elapsed = int(time.time() - start_time)
            print(f"  运行 {elapsed}s | 步数 ≈ {step_count} | 距离 ≈ {dist_total:.0f}m | 当前 {current_speed:.1f}km/h")

        time.sleep(random.uniform(0.85, 1.15))

    elapsed = int(time.time() - start_time)
    print(f"\n  🏁 跑完! 耗时 {elapsed}s | 步数 ≈ {step_count} | 距离 ≈ {dist_total/1000:.2f}km")
    if pause_log:
        print(f"  ℹ 共暂停 {len(pause_log)} 次, 累计 {sum(pause_log)}s")
    return step_count, dist_total

def main():
    print("=" * 60)
    print("  步道乐跑自动刷步数 V5.00 🛡️防检测版")
    print("  手机: vivo V2230A | Ninja Fake GPS PRO")
    print("=" * 60)

    full_antidetect_setup()

    if not setup_ninja_mock():
        return
    if not start_ninja_mock():
        return
    launch_lepao()

    hide_mock_after_launch()

    print("\n" + "=" * 60)
    print("  选速度和模式 (防检测已启用):")
    print("  1. 5  km/h  (快走)  - 600s = ~0.83km")
    print("  2. 8  km/h  (慢跑)  - 600s = ~1.33km")
    print("  3. 10 km/h  (正常)  - 600s = ~1.67km")
    print("  4. 12 km/h  (较快)  - 600s = ~2.00km")
    print("  5. 15 km/h  (冲刺)  - 600s = ~2.50km")
    print("=" * 60)

    try:
        choice = input("输入选项 [1-5] 默认3: ").strip() or "3"
        duration = int(input("时长(秒) 默认600: ").strip() or "600")
        mode = input("轨迹 [1=圆周 2=直线] 默认1: ").strip() or "1"
    except Exception:
        choice = "3"
        duration = 600
        mode = "1"

    speed_map = {"1":5, "2":8, "3":10, "4":12, "5":15}
    speed = speed_map.get(choice, 10)

    print(f"\n  确定: {speed} km/h × {duration}s = {speed*duration/3600:.2f}km | 模式: {'圆周' if mode=='1' else '直线'}")
    confirm = input("回车开始，Ctrl+C 随时停止: ")

    try:
        if mode == "2":
            run_straight(speed_kmh=speed, duration_sec=duration)
        else:
            run_circle(speed_kmh=speed, duration_sec=duration)
    except KeyboardInterrupt:
        print("\n  ⏹ 用户停止")

if __name__ == "__main__":
    main()