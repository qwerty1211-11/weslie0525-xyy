#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步道乐跑 / 闪动校园 自动刷步数 v2.0
====================================
原理: ADB Mock GPS 模拟真实跑步轨迹
特点: 无需手机端安装任何第三方软件
要求:
  1. 手机开启 USB调试
  2. 连接电脑ADB
  3. Android 11+ (已测试 Android 13)

使用: python auto_step.py
"""

import time
import math
import random
import subprocess
import sys
import os
import re
import threading

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADB_PATH = os.path.join(SCRIPT_DIR, "platform-tools", "adb.exe")

APP_PACKAGE = "com.lptiyu.tanke"
APP_MONKEY_DELAY = 3000

SPEED_MIN_KMH = 5.0
SPEED_MAX_KMH = 30.0
UPDATE_INTERVAL = 0.6

GPS_JITTER_M = 0.15
BEARING_JITTER_DEG = 3.0

USE_VIBRATION = True
VIBRATION_PATTERNS = [60, 80, 100, 120]


def ensure_adb():
    if not os.path.exists(ADB_PATH):
        print(f"[-] 未找到ADB: {ADB_PATH}")
        print("    请从 https://developer.android.com/tools/releases/platform-tools 下载")
        print("    解压后将 platform-tools 文件夹放到此脚本同目录下")
        return False
    try:
        subprocess.run([ADB_PATH, "start-server"], capture_output=True, timeout=10)
        time.sleep(0.5)
        r = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True, timeout=5)
        lines = [l.strip() for l in r.stdout.split("\n") if l.strip() and "List" not in l]
        devices = [l for l in lines if "device" in l and "unauthorized" not in l]
        if not devices:
            print("[-] 未检测到可用设备")
            print("    请检查: 1.USB连接  2.开启USB调试  3.授权此电脑")
            return False
        print(f"[+] 已连接设备: {devices[0].split()[0]}")
        return True
    except Exception as e:
        print(f"[-] ADB初始化失败: {e}")
        return False


def adb_shell(args, timeout=5):
    cmd = [ADB_PATH, "shell"] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout.strip(), r.stderr.strip()
    except Exception:
        return False, "", ""


def setup_screen_keepon():
    print("[*] 设置屏幕常亮 + 防休眠...")
    adb_shell(["svc", "power", "stayon", "true"])
    adb_shell(["settings", "put", "system", "screen_off_timeout", "1800000"])
    adb_shell(["dumpsys", "deviceidle", "disable"])
    adb_shell(["input", "keyevent", "KEYCODE_WAKEUP"])
    adb_shell(["input", "keyevent", "KEYCODE_MENU"])
    time.sleep(0.3)
    adb_shell(["input", "keyevent", "KEYCODE_WAKEUP"])
    adb_shell(["input", "keyevent", "KEYCODE_HOME"])
    print("[+] 屏幕已保持常亮")


def bring_app_foreground():
    print(f"[*] 启动 {APP_PACKAGE} 到前台...")
    r = subprocess.run(
        [ADB_PATH, "shell", "monkey", "-p", APP_PACKAGE,
         "-c", "android.intent.category.LAUNCHER", "1"],
        capture_output=True, text=True, timeout=10
    )
    time.sleep(2.5)

    ok, out, _ = adb_shell(["dumpsys", "activity", "top"], timeout=5)
    found = False
    for line in out.split("\n"):
        if APP_PACKAGE in line and ("mResumedActivity" in line or "mFocusedActivity" in line or "topResumedActivity" in line):
            found = True
            print(f"[+] APP 已在前台: {line.strip()[:100]}")
            break

    if not found:
        ok, out2, _ = adb_shell(["am", "start", "-n", f"{APP_PACKAGE}/.main.MainActivity"], timeout=5)
        if ok:
            time.sleep(2)
        else:
            print(f"[!] 无法自动启动APP，请手动打开后按回车继续...")
            input()


def fetch_real_location():
    print("[*] 正在读取手机真实位置 (关闭mock定位)...")
    for p in ["gps", "network"]:
        adb_shell(["cmd", "location", "providers", "remove-test-provider", p])
    time.sleep(0.5)

    adb_shell(["cmd", "location", "set-location-enabled", "true"])
    adb_shell(["settings", "put", "location_mode", "3"])
    adb_shell(["dumpsys", "deviceidle", "disable"])
    adb_shell(["input", "keyevent", "KEYCODE_WAKEUP"])
    time.sleep(0.3)

    last_lat = None
    last_lon = None
    for attempt in range(15):
        ok, out, _ = adb_shell(["dumpsys", "location"], timeout=8)
        if ok:
            for line in out.split("\n"):
                if "last location=Location[" in line and "mock]" not in line and "null" not in line:
                    m = re.search(r"Location\[[^\]]*?([NS]\d+\.?\d*)[,\s]+([EW]\d+\.?\d*)", line)
                    if m:
                        lat_str, lon_str = m.group(1), m.group(2)
                        lat = float(lat_str) if lat_str.startswith("N") else -float(lat_str)
                        lon = float(lon_str) if lon_str.startswith("E") else -float(lon_str)
                        if -90 < lat < 90 and -180 < lon < 180:
                            last_lat, last_lon = lat, lon
                            print(f"  尝试 {attempt+1}: 解析到 ({lat:.6f}, {lon:.6f})")
                    else:
                        m2 = re.search(r"([-+]?\d+\.?\d*)\s*[, ]\s*([-+]?\d+\.?\d*)", line)
                        if m2:
                            lat, lon = float(m2.group(1)), float(m2.group(2))
                            if -90 < lat < 90 and -180 < lon < 180:
                                last_lat, last_lon = lat, lon

        if last_lat is not None:
            break
        time.sleep(1.5)

    if last_lat is None:
        print("  [!] 未获取到真实位置，使用默认坐标 (请手动在有GPS的地方重试)")
        return 30.5928, 114.3055

    print(f"[+] 真实位置: ({last_lat:.6f}, {last_lon:.6f})")
    return last_lat, last_lon


def setup_mock_location():
    print("[*] 正在配置Mock Location...")
    for p in ["gps", "network"]:
        adb_shell(["cmd", "location", "providers", "remove-test-provider", p])
        adb_shell(["cmd", "location", "providers", "set-test-provider-enabled", p, "false"])

    adb_shell(["cmd", "location", "providers", "add-test-provider",
               "gps", "--supportsAltitude", "--supportsSpeed", "--supportsBearing"])
    adb_shell(["cmd", "location", "providers", "add-test-provider", "network"])

    adb_shell(["cmd", "location", "providers", "set-test-provider-enabled", "gps", "true"])
    adb_shell(["cmd", "location", "providers", "set-test-provider-enabled", "network", "true"])

    adb_shell(["cmd", "location", "set-location-enabled", "true"])
    adb_shell(["settings", "put", "global", "mock_location", "1"])

    print("[+] Mock Location 就绪 (gps + network)")


def remove_mock_location():
    print("[*] 清理Mock Location...")
    for p in ["gps", "network"]:
        adb_shell(["cmd", "location", "providers", "set-test-provider-enabled", p, "false"])
        adb_shell(["cmd", "location", "providers", "remove-test-provider", p])
    adb_shell(["settings", "put", "global", "mock_location", "0"])
    print("[+] 已清理")


def get_device_epoch_ms():
    ok, out, _ = adb_shell(["date", "+%s%3N"], timeout=3)
    if ok and out.strip().isdigit():
        return out.strip()
    return str(int(time.time() * 1000))


def send_gps(lat, lon, accuracy=18.0):
    epoch = get_device_epoch_ms()
    base = ["cmd", "location", "providers", "set-test-provider-location"]
    gps_ok, _, _ = adb_shell(
        base + ["gps", "--location", f"{lat},{lon}", "--accuracy", str(accuracy), "--time", epoch],
        timeout=5
    )
    net_ok, _, _ = adb_shell(
        base + ["network", "--location", f"{lat},{lon}", "--accuracy", str(accuracy + 35.0), "--time", epoch],
        timeout=5
    )
    return gps_ok or net_ok


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def bearing_deg(lat1, lon1, lat2, lon2):
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(rlat2)
    y = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    brng = math.degrees(math.atan2(x, y))
    return (brng + 360) % 360


def destination_point(lat, lon, bearing_deg, distance_m):
    R = 6371000.0
    rlat = math.radians(lat)
    rlon = math.radians(lon)
    rb = math.radians(bearing_deg)
    lat2 = math.asin(math.sin(rlat) * math.cos(distance_m / R) +
                     math.cos(rlat) * math.sin(distance_m / R) * math.cos(rb))
    lon2 = rlon + math.atan2(math.sin(rb) * math.sin(distance_m / R) * math.cos(rlat),
                             math.cos(distance_m / R) - math.sin(rlat) * math.sin(lat2))
    return math.degrees(lat2), math.degrees(lon2)


def vibrate():
    if not USE_VIBRATION:
        return
    dur = random.choice(VIBRATION_PATTERNS)
    for cmd in [
        ["vibrate", str(dur)],
        ["service", "call", "vibrator_manager", "2", "i32", "1", "i32", str(dur)]
    ]:
        ok, _, _ = adb_shell(cmd, timeout=2)
        if ok:
            break


class TrackGenerator:
    def __init__(self, start_lat, start_lon, radius_m, speed_kmh):
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.radius_m = max(200, min(radius_m, 1000))
        self.speed_kmh = speed_kmh
        self.center_lat = start_lat
        self.center_lon = start_lon
        self.angle = random.uniform(0, 2 * math.pi)
        self.direction = 1 if random.random() > 0.5 else -1
        self.last_lat = start_lat
        self.last_lon = start_lon
        self.straight_count = 0

    def next_point(self, dt_seconds):
        speed_ms = self.speed_kmh / 3.6
        arc_length = speed_ms * dt_seconds

        self.angle += (arc_length / self.radius_m) * self.direction

        if random.random() < 0.3:
            self.direction = -self.direction

        bearing = math.degrees(self.angle) % 360
        r = self.radius_m + random.uniform(-8, 8)
        lat, lon = destination_point(self.center_lat, self.center_lon, bearing, r)

        return lat, lon

    def jitter(self, lat, lon, forward_bearing):
        perp = (forward_bearing + 90) % 360
        offset_m = random.uniform(-GPS_JITTER_M, GPS_JITTER_M)
        return destination_point(lat, lon, perp, offset_m)


class StepSimulator:
    def __init__(self, start_lat, start_lon, radius_m, speed_kmh):
        self.route = TrackGenerator(start_lat, start_lon, radius_m, speed_kmh)
        self.speed_kmh = speed_kmh
        self.total_distance_m = 0.0
        self.total_steps = 0
        self.running = False
        self.start_time = None
        self.last_lat = start_lat
        self.last_lon = start_lon
        self.vib_thread = None

    def _vibration_loop(self):
        while self.running:
            vibrate()
            interval = 0.5 + random.uniform(-0.2, 0.3)
            time.sleep(max(0.25, interval))

    def start_vibration(self):
        self.vib_thread = threading.Thread(target=self._vibration_loop, daemon=True)
        self.vib_thread.start()

    def run(self, duration_minutes=0):
        self.running = True
        self.start_time = time.time()
        print(f"\n{'=' * 60}")
        print(f"  开始模拟运动")
        print(f"  速度: {self.speed_kmh:.1f} km/h")
        print(f"  起点: ({self.last_lat:.6f}, {self.last_lon:.6f})")
        print(f"  半径: {self.route.radius_m}m")
        print(f"  更新间隔: {UPDATE_INTERVAL}s")
        print(f"  震动模拟: {'开启' if USE_VIBRATION else '关闭'}")
        if duration_minutes > 0:
            print(f"  目标时长: {duration_minutes} 分钟")
        else:
            print(f"  持续运行 (Ctrl+C 停止)")
        print(f"{'=' * 60}\n")

        setup_screen_keepon()
        bring_app_foreground()
        setup_mock_location()
        self.start_vibration()

        print("[*] 预热: 发送初始GPS定位...")
        for _ in range(3):
            send_gps(self.last_lat, self.last_lon, accuracy=random.uniform(15, 25))
            time.sleep(0.3)

        update_count = 0
        try:
            while self.running:
                t0 = time.time()

                new_lat, new_lon = self.route.next_point(UPDATE_INTERVAL)

                forward_bearing = bearing_deg(self.last_lat, self.last_lon, new_lat, new_lon)
                new_lat, new_lon = self.route.jitter(new_lat, new_lon, forward_bearing)

                dist = haversine_m(self.last_lat, self.last_lon, new_lat, new_lon)
                self.total_distance_m += dist
                self.total_steps += int(dist / 0.7)

                ok = send_gps(new_lat, new_lon, accuracy=random.uniform(15, 25))

                if not ok:
                    print(f"  [!] GPS发送失败, 尝试重连...")
                    setup_mock_location()

                self.last_lat, self.last_lon = new_lat, new_lon
                update_count += 1

                elapsed = time.time() - self.start_time
                elapsed_min = elapsed / 60
                speed_now = dist / UPDATE_INTERVAL * 3.6

                if update_count % 5 == 0 or update_count == 1:
                    sys.stdout.write(
                        f"\r  [{elapsed_min:6.1f}min] "
                        f"距离={self.total_distance_m / 1000:.2f}km  "
                        f"步数≈{self.total_steps}  "
                        f"当前速度={speed_now:.1f}km/h  "
                        f"位置=({new_lat:.5f}, {new_lon:.5f})    "
                    )
                    sys.stdout.flush()

                if duration_minutes > 0 and elapsed_min >= duration_minutes:
                    print(f"\n\n[+] 已达目标时长 {duration_minutes} 分钟")
                    break

                actual_dt = time.time() - t0
                sleep_time = max(0.05, UPDATE_INTERVAL - actual_dt)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print(f"\n\n[!] 用户中断")
        finally:
            self.running = False
            total_time = time.time() - self.start_time
            print(f"\n{'=' * 60}")
            print(f"  运行结束")
            print(f"  总时长: {total_time / 60:.1f} 分钟")
            print(f"  总距离: {self.total_distance_m / 1000:.2f} km")
            print(f"  估算步数: ~{self.total_steps} 步")
            print(f"  平均速度: {self.total_distance_m / max(total_time, 0.1) * 3.6:.1f} km/h")
            print(f"{'=' * 60}")


def prompt_location():
    print(f"\n  起点位置:")
    print(f"  1. 自动读取手机真实GPS (推荐)")
    print(f"  2. 手动输入坐标")
    choice = input("选择 [1/2] (默认1): ").strip()
    if choice == "2":
        lat = float(input("  纬度 (如 30.5928): ").strip())
        lon = float(input("  经度 (如 114.3055): ").strip())
        return lat, lon
    return fetch_real_location()


def prompt_speed():
    print(f"\n  模拟速度 (km/h):")
    print(f"  1. 慢跑  ~10")
    print(f"  2. 正常  ~15")
    print(f"  3. 快跑  ~20")
    print(f"  4. 极速  ~25")
    print(f"  5. 自定义")
    choice = input("选择 [1/2/3/4/5] (默认3): ").strip()

    speeds = {"1": 10.0, "2": 15.0, "3": 20.0, "4": 25.0}
    if choice in speeds:
        return speeds[choice]
    elif choice == "5":
        sp = float(input("  速度 km/h (3-30): ").strip())
        return max(3.0, min(30.0, sp))
    return 20.0


def prompt_duration():
    print(f"\n  运行时长:")
    print(f"  1. 30 分钟 (~5km)")
    print(f"  2. 45 分钟 (~7.5km)")
    print(f"  3. 60 分钟 (~10km)")
    print(f"  4. 自定义")
    print(f"  5. 持续运行")
    choice = input("选择 [1/2/3/4/5] (默认2): ").strip()

    durs = {"1": 30, "2": 45, "3": 60}
    if choice in durs:
        return durs[choice]
    elif choice == "4":
        d = int(input("  分钟数: ").strip())
        return max(1, d)
    elif choice == "5":
        return 0
    return 45


def prompt_radius():
    print(f"\n  路线半径 (米, 模拟环形跑):")
    print(f"  1. 200m (操场跑道)")
    print(f"  2. 400m (标准操场)")
    print(f"  3. 600m")
    print(f"  4. 自定义")
    choice = input("选择 [1/2/3/4] (默认2): ").strip()

    radii = {"1": 200, "2": 400, "3": 600}
    if choice in radii:
        return radii[choice]
    elif choice == "4":
        r = int(input("  半径 (米, 200-800): ").strip())
        return max(200, min(800, r))
    return 400


def main():
    global USE_VIBRATION

    print("""
╔══════════════════════════════════════════════════════════╗
║   步道乐跑 / 闪动校园 自动刷步数 v2.0                    ║
║   核心改进: 从真实GPS位置出发 + 强制APP前台 + 震动模拟   ║
║   特点: 无需手机端安装任何第三方软件                      ║
╚══════════════════════════════════════════════════════════╝
""")

    if not ensure_adb():
        return

    print("\n  --- 基本配置 ---")
    lat, lon = prompt_location()
    print(f"  起点: ({lat:.6f}, {lon:.6f})")

    radius = prompt_radius()
    speed = prompt_speed()
    duration = prompt_duration()

    print(f"\n  --- 配置确认 ---")
    print(f"  起点坐标: ({lat:.6f}, {lon:.6f})")
    print(f"  路线半径: {radius} m")
    print(f"  模拟速度: {speed} km/h")
    print(f"  运行时长: {duration if duration > 0 else '持续运行'} 分钟")
    print(f"  更新间隔: {UPDATE_INTERVAL} 秒")
    print(f"  震动模拟: 开启")

    confirm = input("\n  确认开始? [y/N]: ").strip().lower()
    if confirm != "y":
        print("  已取消")
        return

    sim = StepSimulator(lat, lon, radius, speed)
    try:
        sim.run(duration)
    except Exception as e:
        print(f"\n[-] 异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            remove_mock_location()
        except Exception:
            pass

    print("\n  清理完成，手机位置应已恢复正常")
    print("  建议打开地图APP确认GPS定位恢复正常")
if __name__ == "__main__":
    main()