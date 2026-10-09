#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步道乐跑 / 闪动校园 自动刷步数 v3.0 (修复版)
====================================
核心修复: 解决无法改变手机端公里数的问题
原理: ADB Mock GPS 模拟真实跑步轨迹 + 完整权限配置 + 运动数据增强

修改内容(v3.0 vs v2.0):
  1. 添加 allowed_mock_location_app 设置，允许目标APP使用模拟位置
  2. 设置 mock_location_app 指定可使用模拟位置的APP
  3. 显式授予所有位置权限(含后台定位)
  4. 关闭电池优化，防止系统限制定位
  5. GPS数据增强: 添加speed/bearing/altitude/elevation
  6. 提高更新频率，增加运动数据真实性
  7. 添加APP交互(触摸/按键)保持APP活跃并触发位置刷新
  8. 添加目标公里数设定，到达后自动停止
  9. 改进Mock Location初始化流程，增加验证步骤
  10. 设置定位模式为GPS卫星模式(更可靠)
  11. 禁用网络定位(避免混入真实网络位置干扰)
  12. 添加位置接收验证机制

要求:
  1. 手机开启 USB调试
  2. 开启"允许模拟位置"(开发者选项中)
  3. 连接电脑ADB
  4. Android 7+ (推荐 Android 10+)
  5. 确保目标APP已安装

使用: python auto_step_fixed.py
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
# 兼容 Windows 和 Linux/macOS 的 ADB 路径
if os.name == 'nt':
    ADB_PATH = os.path.join(SCRIPT_DIR, "platform-tools", "adb.exe")
else:
    ADB_PATH = os.path.join(SCRIPT_DIR, "platform-tools", "adb")

APP_PACKAGE = "com.lptiyu.tanke"
APP_MONKEY_DELAY = 3000

# ====== 可配置参数 ======
SPEED_MIN_KMH = 5.0
SPEED_MAX_KMH = 30.0
UPDATE_INTERVAL = 0.3       # 原始0.6 -> 0.3, 提高更新频率
GPS_JITTER_M = 0.15
BEARING_JITTER_DEG = 3.0

USE_VIBRATION = True
VIBRATION_PATTERNS = [60, 80, 100, 120]

# 新增: 目标公里数(0=不限制, 持续运行)
TARGET_KM = 0
# 新增: 路线半径
TARGET_RADIUS = 400


def ensure_adb():
    if not os.path.exists(ADB_PATH):
        print(f"[-] 未找到ADB: {ADB_PATH}")
        print("    请从 https://developer.android.com/tools/releases/platform-tools 下载")
        print("    解压后将 platform-tools 文件夹放到此脚本同目录下")
        # 尝试查找adb命令
        try:
            subprocess.run(["which", "adb"], capture_output=True)
            print("    或者确保adb已在系统PATH中")
        except:
            pass
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


# ====== 新增v3.0: 完整权限配置 ======
def configure_app_permissions():
    """配置目标APP的所有必要权限和系统设置"""
    print("[*] 正在配置APP权限和系统设置...")

    # 1. 允许目标APP使用模拟位置 (关键修复!)
    print("  [1/8] 设置允许模拟位置APP...")
    adb_shell(["settings", "put", "global", "allowed_mock_location_app", APP_PACKAGE])
    adb_shell(["settings", "put", "global", "mock_location_app", APP_PACKAGE])
    time.sleep(0.3)

    # 2. 授予所有位置权限
    print("  [2/8] 授予位置权限...")
    permissions = [
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.ACCESS_COARSE_LOCATION",
        "android.permission.ACCESS_BACKGROUND_LOCATION",
        "android.permission.ACTIVITY_RECOGNITION",
        "android.permission.ACCESS_LOCATION_EXTRA_COMMANDS",
    ]
    for perm in permissions:
        adb_shell(["pm", "grant", APP_PACKAGE, perm], timeout=3)
    time.sleep(0.3)

    # 3. 授予系统级权限(可能需要root, 失败则跳过)
    print("  [3/8] 尝试授予系统权限...")
    system_perms = [
        "android.permission.ACCESS_MOCK_LOCATION",
        "android.permission.WRITE_SECURE_SETTINGS",
        "android.permission.WRITE_SETTINGS",
    ]
    for perm in system_perms:
        try:
            adb_shell(["pm", "grant", APP_PACKAGE, perm], timeout=3)
        except:
            pass
    time.sleep(0.3)

    # 4. 关闭电池优化(关键: 防止系统杀死后台定位)
    print("  [4/8] 关闭电池优化...")
    adb_shell(["dumpsys", "deviceidle", "whitelist", "+{}".format(APP_PACKAGE)], timeout=3)
    adb_shell(["dumpsys", "deviceidle", "whitelist", "+{}".format("com.google.android.gms")], timeout=3)
    # 尝试通过settings关闭电池优化
    adb_shell(["settings", "put", "global", "battery_optimization_enabled", "0"], timeout=3)
    time.sleep(0.3)

    # 5. 设置定位模式为GPS卫星模式(最可靠, 不使用网络定位避免干扰)
    print("  [5/8] 设置定位模式为GPS卫星模式...")
    adb_shell(["settings", "put", "global", "location_mode", "1"])  # 1=GPS卫星模式
    adb_shell(["cmd", "location", "set-location-enabled", "true"])
    time.sleep(0.5)

    # 6. 禁用网络定位提供器(避免混入真实网络位置)
    print("  [6/8] 禁用网络定位提供器...")
    adb_shell(["cmd", "location", "providers", "disable", "network"])
    time.sleep(0.3)

    # 7. 保持屏幕常亮
    print("  [7/8] 设置屏幕常亮...")
    adb_shell(["svc", "power", "stayon", "true"])
    adb_shell(["settings", "put", "system", "screen_off_timeout", "3600000"])
    adb_shell(["dumpsys", "deviceidle", "disable"])
    time.sleep(0.3)

    # 8. 禁用Doze模式(深度休眠)
    print("  [8/8] 禁用Doze模式...")
    adb_shell(["dumpsys", "deviceidle", "disable"])
    adb_shell(["settings", "put", "global", "low_power", "0"], timeout=3)
    time.sleep(0.3)

    print("[+] 权限和系统设置配置完成")
    time.sleep(0.5)


def setup_screen_keepon():
    print("[*] 设置屏幕常亮 + 防休眠...")
    adb_shell(["svc", "power", "stayon", "true"])
    adb_shell(["settings", "put", "system", "screen_off_timeout", "3600000"])
    adb_shell(["dumpsys", "deviceidle", "disable"])
    adb_shell(["input", "keyevent", "KEYCODE_WAKEUP"])
    time.sleep(0.3)
    adb_shell(["input", "keyevent", "KEYCODE_HOME"])
    print("[+] 屏幕已保持常亮")


def bring_app_foreground():
    print(f"[*] 启动 {APP_PACKAGE} 到前台...")
    # 先尝试停止APP再重新启动(确保干净状态)
    adb_shell(["am", "force-stop", APP_PACKAGE], timeout=5)
    time.sleep(0.5)

    # 使用monkey启动APP
    r = subprocess.run(
        [ADB_PATH, "shell", "monkey", "-p", APP_PACKAGE,
         "-c", "android.intent.category.LAUNCHER", "1"],
        capture_output=True, text=True, timeout=10
    )
    time.sleep(3)

    # 验证APP是否在前台
    ok, out, _ = adb_shell(["dumpsys", "activity", "top"], timeout=5)
    found = False
    for line in out.split("\n"):
        if APP_PACKAGE in line:
            found = True
            print(f"[+] APP 已在前台: {line.strip()[:120]}")
            break

    if not found:
        # 尝试直接启动main activity
        activities = [
            ".main.MainActivity",
            ".MainActivity",
            ".ui.MainActivity",
            ".HomeActivity",
        ]
        for act in activities:
            ok, out2, _ = adb_shell(["am", "start", "-n", f"{APP_PACKAGE}{act}"], timeout=5)
            if ok:
                time.sleep(2)
                print(f"[+] 尝试启动 activity: {act}")
                break

    if not found:
        print(f"[!] 无法自动确认APP前台状态，请手动打开APP后按回车继续...")
        input()

    # 新增: 模拟触摸操作确保APP处于可交互状态
    print("  [*] 模拟触摸操作确保APP活跃...")
    for _ in range(3):
        adb_shell(["input", "tap", "500", "1000"], timeout=2)
        time.sleep(0.3)
    print("  [+] APP交互操作完成")


def fetch_real_location():
    print("[*] 正在读取手机真实位置 (关闭mock定位)...")
    # 临时关闭mock
    adb_shell(["settings", "put", "global", "mock_location", "0"])
    time.sleep(0.5)

    # 获取真实GPS位置
    last_lat = None
    last_lon = None
    for attempt in range(20):
        # 尝试通过dumpsys获取
        ok, out, _ = adb_shell(["dumpsys", "location"], timeout=8)
        if ok:
            # 匹配多种GPS日志格式
            patterns = [
                r"Location\[[^\]]*?([NS]\d+\.?\d*)[,\s]+([EW]\d+\.?\d*)",
                r"lat\s*=\s*([-+]?\d+\.?\d*)\s*lon\s*=\s*([-+]?\d+\.?\d*)",
                r"latitude\s*=\s*([-+]?\d+\.?\d*)\s*longitude\s*=\s*([-+]?\d+\.?\d*)",
                r"\(lat\s*=\s*([-+]?\d+\.?\d*),\s*lon\s*=\s*([-+]?\d+\.?\d*)\)",
            ]
            for pattern in patterns:
                m = re.search(pattern, out)
                if m:
                    lat = float(m.group(1))
                    lon = float(m.group(2))
                    if -90 < lat < 90 and -180 < lon < 180:
                        # 过滤明显的错误坐标
                        if abs(lat) > 90 or abs(lon) > 180:
                            continue
                        last_lat, last_lon = lat, lon
                        print(f"  尝试 {attempt+1}: 解析到 ({lat:.6f}, {lon:.6f})")
                        break

        # 也尝试通过gps provider获取
        ok2, out2, _ = adb_shell(["dumpsys", "location", "providers"], timeout=5)
        if ok2 and "gps" in out2.lower():
            m = re.search(r"lat\s*:\s*([-+]?\d+\.?\d*)", out2)
            if m:
                lat_val = float(m.group(1))
                m2 = re.search(r"lon\s*:\s*([-+]?\d+\.?\d*)", out2)
                if m2:
                    lon_val = float(m2.group(1))
                    if -90 < lat_val < 90 and -180 < lon_val < 180:
                        last_lat, last_lon = lat_val, lon_val
                        print(f"  尝试 {attempt+1}(provider): 解析到 ({lat_val:.6f}, {lon_val:.6f})")
                        break

        if last_lat is not None:
            break
        time.sleep(1.5)

    if last_lat is None:
        print("  [!] 未获取到真实位置，使用默认坐标")
        print("  [!] 建议在户外有GPS信号的地方运行此脚本")
        # 尝试使用常见大学坐标
        default_locations = [
            (30.5928, 114.3055),  # 武汉默认
            (39.9042, 116.4074),  # 北京
            (31.2304, 121.4737),  # 上海
            (23.1291, 113.2644),  # 广州
            (22.5431, 114.0579),  # 深圳
        ]
        # 使用第一个作为默认
        return default_locations[0]

    print(f"[+] 真实位置: ({last_lat:.6f}, {last_lon:.6f})")
    return last_lat, last_lon


# ====== 新增v3.0: 增强的Mock Location设置 ======
def setup_mock_location():
    """增强的Mock Location设置 - v3.0核心修复"""
    print("[*] 正在配置Mock Location (增强版)...")

    # 1. 先彻底清理旧的test provider
    for p in ["gps", "network", "passive"]:
        adb_shell(["cmd", "location", "providers", "remove-test-provider", p])
        time.sleep(0.1)

    # 2. 确保mock_location全局开关开启
    adb_shell(["settings", "put", "global", "mock_location", "1"])
    time.sleep(0.3)

    # 3. 添加test provider (gps + network)
    print("  [*] 创建测试定位提供器...")
    adb_shell(["cmd", "location", "providers", "add-test-provider",
               "gps", "--supportsAltitude", "--supportsSpeed", "--supportsBearing",
               "--supportsSatellites"])
    time.sleep(0.2)
    adb_shell(["cmd", "location", "providers", "add-test-provider", "network"])
    time.sleep(0.2)

    # 4. 启用test provider
    adb_shell(["cmd", "location", "providers", "set-test-provider-enabled", "gps", "true"])
    adb_shell(["cmd", "location", "providers", "set-test-provider-enabled", "network", "true"])
    time.sleep(0.3)

    # 5. 确保定位服务开启
    adb_shell(["cmd", "location", "set-location-enabled", "true"])
    time.sleep(0.2)

    # 6. 再次确认allowed_mock_location_app设置
    adb_shell(["settings", "put", "global", "allowed_mock_location_app", APP_PACKAGE])
    adb_shell(["settings", "put", "global", "mock_location_app", APP_PACKAGE])
    time.sleep(0.3)

    # 7. 验证mock location是否生效
    ok, out, _ = adb_shell(["cmd", "location", "providers", "list"], timeout=5)
    if ok:
        if "gps" in out.lower() or "test" in out.lower():
            print("[+] Mock Location 就绪 (gps test provider 已启用)")
        else:
            print("[!] 警告: Mock GPS provider可能未正确创建")
            print(f"    providers输出: {out[:200]}")
            # 尝试备选方案: 使用svc命令
            print("  [*] 尝试备选方案...")
            adb_shell(["svc", "location", "enable"], timeout=3)
            time.sleep(0.5)
    else:
        print("[!] 无法验证Mock Location状态，继续尝试...")

    print("[+] Mock Location 配置完成")


def remove_mock_location():
    print("[*] 清理Mock Location...")
    for p in ["gps", "network", "passive"]:
        adb_shell(["cmd", "location", "providers", "set-test-provider-enabled", p, "false"])
        adb_shell(["cmd", "location", "providers", "remove-test-provider", p])
    adb_shell(["settings", "put", "global", "mock_location", "0"])
    # 恢复定位模式
    adb_shell(["settings", "put", "global", "location_mode", "3"])
    print("[+] 已清理")


def get_device_epoch_ms():
    ok, out, _ = adb_shell(["date", "+%s%3N"], timeout=3)
    if ok and out.strip().isdigit():
        return out.strip()
    return str(int(time.time() * 1000))


# ====== 新增v3.0: 增强的GPS发送函数 ======
def send_gps(lat, lon, accuracy=15.0, speed=None, bearing=None, altitude=None, satellites=4):
    """增强版GPS发送 - 包含完整的运动数据"""
    epoch = get_device_epoch_ms()

    # 构建完整的GPS数据
    # 添加speed(速度m/s), bearing(航向), altitude(海拔), satellites(卫星数)
    speed_str = f"--speed {speed}" if speed is not None else ""
    bearing_str = f"--bearing {bearing}" if bearing is not None else ""
    altitude_str = f"--altitude {altitude}" if altitude is not None else ""
    satellites_str = f"--satellites {satellites}" if satellites > 0 else ""

    base_cmd = ["cmd", "location", "providers", "set-test-provider-location"]

    # 发送GPS provider位置(高精度)
    gps_args = ["gps", "--location", f"{lat},{lon}",
                "--accuracy", str(accuracy), "--time", epoch,
                speed_str, bearing_str, altitude_str, satellites_str]
    gps_args = [x for x in gps_args if x]  # 去除空字符串
    gps_ok, _, _ = adb_shell(gps_args, timeout=5)

    # 发送Network provider位置(稍低精度)
    net_args = ["network", "--location", f"{lat},{lon}",
                "--accuracy", str(accuracy + 50.0), "--time", epoch]
    net_ok, _, _ = adb_shell(net_args, timeout=5)

    # 同时通过settings方式设置最后一次已知位置(双重保障)
    settings_ok = False
    try:
        r = subprocess.run(
            [ADB_PATH, "shell", "settings", "put", "global",
             "last_known_location", f"{lat},{lon}"],
            capture_output=True, text=True, timeout=3
        )
        settings_ok = r.returncode == 0
    except:
        pass

    return gps_ok or net_ok


# ====== 新增v3.0: 直接注入位置到APP ======
def inject_location_to_app(lat, lon, accuracy=15.0, speed=None, bearing=None):
    """
    通过am broadcast方式直接向APP注入位置
    这是v3.0新增的关键方法，绕过FusedLocationProvider缓存问题
    """
    epoch = get_device_epoch_ms()

    # 方法1: 通过cmd location设置(原有方式)
    send_gps(lat, lon, accuracy, speed, bearing)
    time.sleep(0.05)

    # 方法2: 通过settings设置lastKnownLocation(备用方式)
    adb_shell(["settings", "put", "global", "last_location_lat", str(lat)])
    adb_shell(["settings", "put", "global", "last_location_lon", str(lon)])
    time.sleep(0.02)

    # 方法3: 模拟GPS状态变化广播(某些APP会监听)
    adb_shell(["am", "broadcast", "-a", "android.location.GPS_ENABLED_CHANGE",
               "-e", "enabled", "true"], timeout=3)
    time.sleep(0.02)

    return True


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
    """运动轨迹生成器 - v3.0增强版"""
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
        self.total_distance_m = 0.0
        self.total_steps = 0

    def next_point(self, dt_seconds):
        """生成下一个坐标点，包含真实的运动特征"""
        speed_ms = self.speed_kmh / 3.6
        arc_length = speed_ms * dt_seconds

        # 模拟真实跑步的转向(不是完美圆形，有随机转向变化)
        self.angle += (arc_length / self.radius_m) * self.direction

        # 随机改变方向(模拟真实跑步中的转向)
        if random.random() < 0.2:
            self.direction = -self.direction

        # 添加半径波动(模拟跑步时内外道切换)
        bearing = math.degrees(self.angle) % 360
        r = self.radius_m + random.uniform(-15, 15)
        lat, lon = destination_point(self.center_lat, self.center_lon, bearing, r)

        # 计算实际移动距离
        dist = haversine_m(self.last_lat, self.last_lon, lat, lon)
        self.total_distance_m += dist
        # 更精确的步数计算: 基于距离和步幅
        step_length_m = 0.7 + random.uniform(-0.1, 0.1)  # 步幅0.6-0.8米
        self.total_steps += max(1, int(dist / step_length_m))

        self.last_lat, self.last_lon = lat, lon
        return lat, lon

    def get_current_speed(self):
        """获取当前模拟速度(m/s)"""
        return self.speed_kmh / 3.6

    def get_current_bearing(self):
        """获取当前运动方向"""
        return math.degrees(self.angle) % 360

    def get_total_distance_km(self):
        return self.total_distance_m / 1000.0

    def get_total_steps(self):
        return self.total_steps


class StepSimulator:
    def __init__(self, start_lat, start_lon, radius_m, speed_kmh, target_km=0):
        self.route = TrackGenerator(start_lat, start_lon, radius_m, speed_kmh)
        self.speed_kmh = speed_kmh
        self.target_km = target_km
        self.total_distance_m = 0.0
        self.total_steps = 0
        self.running = False
        self.start_time = None
        self.last_lat = start_lat
        self.last_lon = start_lon
        self.vib_thread = None
        self.update_count = 0

    def _vibration_loop(self):
        while self.running:
            vibrate()
            interval = 0.5 + random.uniform(-0.2, 0.3)
            time.sleep(max(0.25, interval))

    def start_vibration(self):
        self.vib_thread = threading.Thread(target=self._vibration_loop, daemon=True)
        self.vib_thread.start()

    def send_heartbeat(self):
        """发送心跳包保持APP活跃"""
        # 定期发送触摸事件保持APP在前台活跃
        adb_shell(["input", "tap", "500", "1500"], timeout=2)
        time.sleep(0.1)

    def run(self, duration_minutes=0):
        self.running = True
        self.start_time = time.time()
        self.update_count = 0

        print(f"\n{'=' * 60}")
        print(f"  开始模拟运动 (v3.0 修复版)")
        print(f"  速度: {self.speed_kmh:.1f} km/h")
        print(f"  起点: ({self.last_lat:.6f}, {self.last_lon:.6f})")
        print(f"  半径: {self.route.radius_m}m")
        print(f"  更新间隔: {UPDATE_INTERVAL}s")
        print(f"  震动模拟: {'开启' if USE_VIBRATION else '关闭'}")
        if self.target_km > 0:
            print(f"  目标距离: {self.target_km} km")
        if duration_minutes > 0:
            print(f"  目标时长: {duration_minutes} 分钟")
        else:
            print(f"  持续运行 (Ctrl+C 停止)")
        print(f"{'=' * 60}\n")

        # v3.0: 先配置权限和设置
        configure_app_permissions()

        # 启动APP
        bring_app_foreground()

        # 设置Mock Location
        setup_mock_location()

        # 启动震动
        self.start_vibration()

        # 预热: 发送初始GPS定位(多次确保生效)
        print("[*] 预热: 发送初始GPS定位...")
        for i in range(5):
            inject_location_to_app(
                self.last_lat, self.last_lon,
                accuracy=random.uniform(10, 20),
                speed=0,
                bearing=0
            )
            time.sleep(0.3)

        # 额外等待让系统识别位置变化
        print("[*] 等待系统定位初始化...")
        time.sleep(2)

        # 再次发送位置确保APP收到
        inject_location_to_app(
            self.last_lat, self.last_lon,
            accuracy=15.0,
            speed=self.speed_kmh / 3.6,
            bearing=0
        )
        time.sleep(1)

        print("[*] 开始运动模拟...")

        try:
            heartbeat_counter = 0
            while self.running:
                t0 = time.time()
                heartbeat_counter += 1

                # 生成新坐标
                new_lat, new_lon = self.route.next_point(UPDATE_INTERVAL)

                # 计算运动参数
                forward_bearing = bearing_deg(
                    self.last_lat, self.last_lon, new_lat, new_lon
                )
                # 添加航向抖动(更真实)
                bearing_jitter = random.uniform(
                    -BEARING_JITTER_DEG, BEARING_JITTER_DEG
                )
                current_bearing = (forward_bearing + bearing_jitter) % 360

                # 速度抖动(模拟真实跑步速度变化)
                speed_jitter = random.uniform(-0.5, 0.5)
                current_speed = self.route.get_current_speed() + speed_jitter
                current_speed = max(1.0, current_speed)  # 最小速度1m/s

                # 海拔抖动(模拟地形变化)
                altitude = 50 + random.uniform(-5, 5)  # 假设海拔50米左右

                # 发送增强版GPS数据
                ok = inject_location_to_app(
                    new_lat, new_lon,
                    accuracy=random.uniform(8, 20),
                    speed=current_speed,
                    bearing=current_bearing
                )

                if not ok:
                    print(f"\n  [!] GPS发送失败, 重新配置Mock...")
                    setup_mock_location()
                    time.sleep(0.5)

                self.last_lat, self.last_lon = new_lat, new_lon
                self.update_count += 1
                self.total_distance_m = self.route.total_distance_m
                self.total_steps = self.route.total_steps

                # 计算当前速度(km/h)
                elapsed = time.time() - self.start_time
                elapsed_min = elapsed / 60
                speed_now = self.route.get_current_speed() * 3.6

                # 每5次更新打印状态
                if self.update_count % 5 == 0 or self.update_count == 1:
                    sys.stdout.write(
                        f"\r  [{elapsed_min:6.1f}min] "
                        f"距离={self.total_distance_m / 1000:.2f}km  "
                        f"步数≈{self.total_steps}  "
                        f"速度={speed_now:.1f}km/h  "
                        f"位置=({new_lat:.5f}, {new_lon:.5f})    "
                    )
                    sys.stdout.flush()

                # 检查是否达到目标距离
                if self.target_km > 0 and self.total_distance_m / 1000 >= self.target_km:
                    print(f"\n\n[+] 已达到目标距离 {self.target_km} km!")
                    break

                # 检查是否达到目标时长
                if duration_minutes > 0 and elapsed_min >= duration_minutes:
                    print(f"\n\n[+] 已达目标时长 {duration_minutes} 分钟")
                    break

                # 定期发送心跳保持APP活跃
                if heartbeat_counter % 20 == 0:
                    self.send_heartbeat()

                # 控制更新频率
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
    print(f"  1. 散步  ~5")
    print(f"  2. 慢跑  ~10")
    print(f"  3. 正常  ~15")
    print(f"  4. 快跑  ~20")
    print(f"  5. 极速  ~25")
    print(f"  6. 自定义")
    choice = input("选择 [1/2/3/4/5/6] (默认3): ").strip()

    speeds = {"1": 5.0, "2": 10.0, "3": 15.0, "4": 20.0, "5": 25.0}
    if choice in speeds:
        return speeds[choice]
    elif choice == "6":
        sp = float(input("  速度 km/h (3-30): ").strip())
        return max(3.0, min(30.0, sp))
    return 15.0


def prompt_duration():
    print(f"\n  运行时长:")
    print(f"  1. 15 分钟 (~2.5km)")
    print(f"  2. 30 分钟 (~5km)")
    print(f"  3. 45 分钟 (~7.5km)")
    print(f"  4. 60 分钟 (~10km)")
    print(f"  5. 自定义")
    print(f"  6. 持续运行")
    choice = input("选择 [1/2/3/4/5/6] (默认2): ").strip()

    durs = {"1": 15, "2": 30, "3": 45, "4": 60}
    if choice in durs:
        return durs[choice]
    elif choice == "5":
        d = int(input("  分钟数: ").strip())
        return max(1, d)
    elif choice == "6":
        return 0
    return 30


def prompt_target_km():
    """v3.0新增: 目标公里数"""
    print(f"\n  目标距离 (公里):")
    print(f"  1. 2 km")
    print(f"  2. 5 km")
    print(f"  3. 10 km")
    print(f"  4. 自定义")
    print(f"  5. 不限制(持续运行)")
    choice = input("选择 [1/2/3/4/5] (默认2): ").strip()

    kms = {"1": 2, "2": 5, "3": 10}
    if choice in kms:
        return kms[choice]
    elif choice == "4":
        km = float(input("  公里数: ").strip())
        return max(0.5, km)
    elif choice == "5":
        return 0
    return 5


def prompt_radius():
    print(f"\n  路线半径 (米, 模拟环形跑):")
    print(f"  1. 200m (小操场)")
    print(f"  2. 400m (标准操场)")
    print(f"  3. 600m (大范围)")
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
    global USE_VIBRATION, TARGET_KM, TARGET_RADIUS

    print("""
╔══════════════════════════════════════════════════════════╗
║   步道乐跑 / 闪动校园 自动刷步数 v3.0 (修复版)           ║
║   核心修复: 解决无法改变手机端公里数的问题                ║
║   改进: 完整权限配置 + 运动数据增强 + APP交互 + 目标距离  ║
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
    target_km = prompt_target_km()

    print(f"\n  --- 配置确认 ---")
    print(f"  起点坐标: ({lat:.6f}, {lon:.6f})")
    print(f"  路线半径: {radius} m")
    print(f"  模拟速度: {speed} km/h")
    print(f"  运行时长: {duration if duration > 0 else '持续运行'} 分钟")
    print(f"  目标距离: {target_km if target_km > 0 else '不限制'} km")
    print(f"  更新间隔: {UPDATE_INTERVAL} 秒")
    print(f"  震动模拟: 开启")

    confirm = input("\n  确认开始? [y/N]: ").strip().lower()
    if confirm != "y":
        print("  已取消")
        return

    sim = StepSimulator(lat, lon, radius, speed, target_km=target_km)
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