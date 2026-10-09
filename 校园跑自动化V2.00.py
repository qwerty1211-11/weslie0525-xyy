#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校园跑自动化 V2.00 — 步道乐跑专项版
针对步道乐跑防作弊机制深度优化
核心对抗: 分段配速检测 / 轨迹合理性 / 速度异常检测 / Mock Location检测
"""

import time
import math
import random
import threading
import sys
import os
import subprocess
import zipfile
import urllib.request
import json
from collections import defaultdict

try:
    from ppadb.client import Client as AdbClient
except ImportError:
    print("[!] 缺少依赖 ppadb，正在安装...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pure-python-adb"])
    from ppadb.client import Client as AdbClient

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADB_PATH = os.path.join(SCRIPT_DIR, "platform-tools", "adb.exe")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "run_config.json")

# ==================== 默认配置（步道乐跑专项） ====================
DEFAULT_CONFIG = {
    "adb": {
        "host": "127.0.0.1",
        "port": 5037
    },
    "run": {
        "target_km": 2.0,
        "base_speed_kmh": 7.5,
        "min_speed_kmh": 4.5,
        "max_speed_kmh": 11.0,
        "speed_variance": 1.2,
        "gps_interval": 2.0,
        "segment_distance_m": 200,
        "min_pause_seconds": 3,
        "max_pause_seconds": 15,
        "pause_probability": 0.06,
        "simulate_sensor": True,
        "human_like": True,
        "step_length_m": 0.70,
        "anti_detection": True
    },
    "location": {
        "start_lat": 41.6872,
        "start_lng": 123.6306,
        "track_mode": "oval",
        "lat_offset": 0.0020,
        "lng_offset": 0.0020,
        "random_walk_amount": 0.0003,
        "bearing_smooth": True
    },
    "touch": {
        "enabled": True,
        "start_btn": {"x": 540, "y": 1820},
        "end_btn": {"x": 540, "y": 1820},
        "confirm_btn": {"x": 540, "y": 1400},
        "action_delay": 3
    }
}


def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            for key, val in saved.items():
                if key in merged and isinstance(merged[key], dict):
                    merged[key].update(val)
                else:
                    merged[key] = val
            return merged
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


CFG = load_config()


def ensure_adb():
    if os.path.exists(ADB_PATH):
        print(f"[+] ADB已存在: {ADB_PATH}")
    else:
        print("[*] 首次运行，下载ADB工具...")
        zip_path = os.path.join(SCRIPT_DIR, "platform-tools.zip")
        url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
        try:
            urllib.request.urlretrieve(url, zip_path)
            print("[+] 下载完成，解压中...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(SCRIPT_DIR)
            os.remove(zip_path)
            print("[+] ADB准备完成")
        except Exception as e:
            print(f"[-] 下载失败: {e}")
            return False

    try:
        subprocess.run([ADB_PATH, "kill-server"], capture_output=True, timeout=5)
        time.sleep(0.5)
        subprocess.run([ADB_PATH, "start-server"], capture_output=True, timeout=10)
        time.sleep(1)
        print("[+] ADB Server已启动")
        return True
    except Exception as e:
        print(f"[-] ADB启动失败: {e}")
        return False


def haversine_distance(lat1, lng1, lat2, lng2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calc_bearing(lat1, lng1, lat2, lng2):
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlng = math.radians(lng2 - lng1)
    x = math.sin(dlng) * math.cos(lat2)
    y = (math.cos(lat1) * math.sin(lat2) -
         math.sin(lat1) * math.cos(lat2) * math.cos(dlng))
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


class RouteGenerator:
    """轨迹生成器"""

    @staticmethod
    def generate_oval(start_lat, start_lng, lat_offset, lng_offset, total_distance_m,
                      speed_mps, interval):
        perimeter_approx = haversine_distance(
            start_lat, start_lng,
            start_lat + lat_offset, start_lng + lng_offset
        ) * 2
        if perimeter_approx < 1:
            perimeter_approx = 500

        total_points = int(total_distance_m / (speed_mps * interval))
        loop_count = max(1, total_distance_m / perimeter_approx)
        points_per_loop = total_points / loop_count

        cx = start_lat + lat_offset / 2
        cy = start_lng + lng_offset / 2
        rx = lat_offset / 2
        ry = lng_offset / 2

        points = []
        for i in range(total_points):
            angle = 2 * math.pi * (i / points_per_loop)
            lat = cx + rx * math.cos(angle)
            lng = cy + ry * math.sin(angle)
            points.append((lat, lng))
        return points

    @staticmethod
    def generate_rectangle(start_lat, start_lng, lat_offset, lng_offset, total_distance_m,
                           speed_mps, interval):
        total_points = int(total_distance_m / (speed_mps * interval))
        points_per_side = total_points // 4

        points = []
        for i in range(points_per_side):
            ratio = i / max(points_per_side - 1, 1)
            points.append((start_lat, start_lng + lng_offset * ratio))
        for i in range(points_per_side):
            ratio = i / max(points_per_side - 1, 1)
            points.append((start_lat + lat_offset * ratio, start_lng + lng_offset))
        for i in range(points_per_side):
            ratio = i / max(points_per_side - 1, 1)
            points.append((start_lat + lat_offset, start_lng + lng_offset * (1 - ratio)))
        for i in range(points_per_side):
            ratio = i / max(points_per_side - 1, 1)
            points.append((start_lat + lat_offset * (1 - ratio), start_lng))
        return points

    @staticmethod
    def generate_loop(start_lat, start_lng, lat_offset, lng_offset, total_distance_m,
                      speed_mps, interval):
        total_points = int(total_distance_m / (speed_mps * interval))
        half = total_points // 2

        points = []
        for i in range(half):
            ratio = i / max(half - 1, 1)
            points.append((start_lat + lat_offset * ratio, start_lng + lng_offset * ratio))
        for i in range(half):
            ratio = i / max(half - 1, 1)
            points.append((start_lat + lat_offset * (1 - ratio), start_lng + lng_offset * (1 - ratio)))
        return points

    @staticmethod
    def apply_natural_noise(points, walk_amount=0.0003, step_length_idx=0):
        result = []
        for i, (lat, lng) in enumerate(points):
            phase = step_length_idx + i * 0.3
            lat_jitter = (
                random.gauss(0, walk_amount * 0.3)
                + math.sin(phase * 0.7) * walk_amount * 0.15
                + math.cos(phase * 1.3) * walk_amount * 0.1
            )
            lng_jitter = (
                random.gauss(0, walk_amount * 0.3)
                + math.cos(phase * 0.7) * walk_amount * 0.15
                + math.sin(phase * 1.1) * walk_amount * 0.1
            )
            result.append((lat + lat_jitter, lng + lng_jitter))
        return result


class PaceController:
    """
    分段配速控制器 — 步道乐跑核心对抗
    步道乐跑后台按时间段/距离段分析配速是否异常
    每个分段的配速必须在合理范围 (5~12 km/h)
    分段之间配速应有自然波动 (不超过±3km/h突变)
    """

    def __init__(self, base_kmh, min_kmh=4.5, max_kmh=11.0, variance=1.2,
                 segment_distance_m=200, human_like=True):
        self.base = base_kmh
        self.min_speed = min_kmh
        self.max_speed = max_kmh
        self.variance = variance
        self.segment_distance = segment_distance_m
        self.human_like = human_like

        self.current_speed = base_kmh
        self.current_segment = 0
        self.segment_speed_target = base_kmh
        self.segment_distance_accum = 0.0
        self.prev_segment_pace = base_kmh

    def new_segment(self):
        self.current_segment += 1
        self.segment_distance_accum = 0.0

        if self.human_like:
            self.segment_speed_target = self.base + random.gauss(0, self.variance)
            delta = self.segment_speed_target - self.prev_segment_pace
            max_change = 2.5
            if abs(delta) > max_change:
                self.segment_speed_target = (
                    self.prev_segment_pace + max_change * (1 if delta > 0 else -1)
                )
        else:
            self.segment_speed_target = self.base

        self.segment_speed_target = max(
            self.min_speed, min(self.max_speed, self.segment_speed_target)
        )
        self.prev_segment_pace = self.segment_speed_target

    def get_speed_kmh(self, delta_distance_m):
        """返回当前应该使用的速度，并累计分段距离"""
        self.segment_distance_accum += delta_distance_m
        if self.segment_distance_accum >= self.segment_distance:
            self.new_segment()

        self.current_speed += (self.segment_speed_target - self.current_speed) * 0.12
        self.current_speed += random.gauss(0, self.variance * 0.08)
        self.current_speed = max(self.min_speed * 0.9,
                                  min(self.max_speed * 1.05, self.current_speed))
        return self.current_speed


class SensorSimulator:
    """传感器模拟器"""

    @staticmethod
    def simulate_accelerometer(timestep, running=True):
        if not running:
            return 9.8 + random.gauss(0, 0.05)
        base = 9.8
        step_freq = 2.5
        t = timestep * 0.1
        vertical = math.sin(2 * math.pi * step_freq * t) * 1.5
        noise = random.gauss(0, 0.1)
        return base + vertical + noise

    @staticmethod
    def simulate_heart_rate(speed_kmh, elapsed_minutes):
        if speed_kmh < 5:
            base_hr = random.randint(85, 100)
        elif speed_kmh < 8:
            base_hr = random.randint(110, 130)
        elif speed_kmh < 11:
            base_hr = random.randint(130, 150)
        else:
            base_hr = random.randint(150, 170)

        if elapsed_minutes > 5:
            base_hr += random.randint(0, 10)
        return base_hr + random.gauss(0, 3)


class DirectionSmoother:
    """方向平滑器 — 避免瞬间大转弯"""

    def __init__(self, max_turn_deg_per_sec=30.0, interval=2.0):
        self.max_turn = max_turn_deg_per_sec * interval
        self.current_bearing = None

    def smooth(self, target_bearing):
        if self.current_bearing is None:
            self.current_bearing = target_bearing
            return target_bearing

        diff = target_bearing - self.current_bearing
        diff = (diff + 180) % 360 - 180

        if abs(diff) > self.max_turn:
            diff = self.max_turn * (1 if diff > 0 else -1)

        self.current_bearing = (self.current_bearing + diff + 360) % 360
        return self.current_bearing


class CampusRunV2:
    """步道乐跑自动化 V2.0"""

    def __init__(self):
        self.device = None
        self.running = False
        self.paused = False
        self.gps_thread = None

        cfg = CFG
        self.target_distance = cfg["run"]["target_km"] * 1000
        self.base_speed = cfg["run"]["base_speed_kmh"]
        self.min_speed = cfg["run"]["min_speed_kmh"]
        self.max_speed = cfg["run"]["max_speed_kmh"]
        self.speed_var = cfg["run"]["speed_variance"]
        self.gps_interval = cfg["run"]["gps_interval"]
        self.segment_distance = cfg["run"]["segment_distance_m"]
        self.pause_probability = cfg["run"]["pause_probability"]
        self.min_pause = cfg["run"]["min_pause_seconds"]
        self.max_pause = cfg["run"]["max_pause_seconds"]
        self.step_length = cfg["run"]["step_length_m"]
        self.simulate_sensor = cfg["run"]["simulate_sensor"]
        self.human_like = cfg["run"]["human_like"]
        self.bearing_smooth = cfg["location"]["bearing_smooth"]

        self.start_lat = cfg["location"]["start_lat"]
        self.start_lng = cfg["location"]["start_lng"]
        self.track_mode = cfg["location"]["track_mode"]
        self.lat_offset = cfg["location"]["lat_offset"]
        self.lng_offset = cfg["location"]["lng_offset"]
        self.walk_amount = cfg["location"]["random_walk_amount"]

        self.pace = PaceController(
            self.base_speed, self.min_speed, self.max_speed,
            self.speed_var, self.segment_distance, self.human_like
        )
        self.direction = DirectionSmoother()

        self.total_distance = 0.0
        self.gps_points = []
        self.step_counter = 0
        self.start_time = None
        self.history = []
        self.segment_data = defaultdict(list)

        self._LEPAO_PKG = None
        self._LEPAO_ACTIVITY = None

    def _find_lepao_app(self):
        """自动检测步道乐跑APP的包名和主Activity"""
        if self._LEPAO_PKG:
            return self._LEPAO_PKG

        candidates = [
            "com.lebao.lepaozu",
            "com.lebu.lepaozu",
            "com.campus.lepao",
            "com.sunshine.campusrun",
            "com.lebao.run",
            "com.lebu.run",
        ]

        for pkg in candidates:
            out, _ = self._exec(f"pm list packages {pkg}", use_root=False)
            if pkg in out:
                self._LEPAO_PKG = pkg
                print(f"  ✅ 发现乐跑APP: {pkg}")
                break

        if not self._LEPAO_PKG:
            all_pkgs, _ = self._exec("pm list packages", use_root=False)
            for line in all_pkgs.split("\n"):
                if "package:" in line:
                    pkg = line.split(":")[1].strip()
                    low = pkg.lower()
                    if any(k in low for k in ("lebao", "lebu", "lepao", "sunshine", "campusrun")):
                        self._LEPAO_PKG = pkg
                        print(f"  ✅ 模糊匹配到乐跑APP: {pkg}")
                        break

        if self._LEPAO_PKG:
            dumpsys, _ = self._exec(f"dumpsys package {self._LEPAO_PKG}", use_root=False)
            for line in dumpsys.split("\n"):
                if "android.intent.action.MAIN" in line and "android.intent.category.LAUNCHER" in line:
                    break
            for line in dumpsys.split("\n"):
                if "Activity" in line and "/" in line and self._LEPAO_PKG in line:
                    act = line.split("Activity")[0].strip() if "Activity" in line else ""
                    if not act:
                        for part in line.split():
                            if "/" in part and self._LEPAO_PKG in part:
                                self._LEPAO_ACTIVITY = part.strip()
                                break
                    break

            if not self._LEPAO_ACTIVITY:
                resolve, _ = self._exec(
                    f"cmd package resolve-activity --brief "
                    f"-a android.intent.action.MAIN "
                    f"-c android.intent.category.LAUNCHER {self._LEPAO_PKG}",
                    use_root=False
                )
                for line in resolve.split("\n"):
                    if "/" in line and self._LEPAO_PKG in line:
                        self._LEPAO_ACTIVITY = line.strip()
                        break

        if self._LEPAO_PKG and not self._LEPAO_ACTIVITY:
            self._LEPAO_ACTIVITY = f"{self._LEPAO_PKG}/.MainActivity"

        return self._LEPAO_PKG

    def _force_stop_lepao(self):
        if self._LEPAO_PKG:
            self._exec(f"am force-stop {self._LEPAO_PKG}")
            time.sleep(0.5)

    def _launch_lepao(self):
        if self._LEPAO_PKG and self._LEPAO_ACTIVITY:
            self._exec(f"am start -n {self._LEPAO_ACTIVITY}")
        elif self._LEPAO_PKG:
            self._exec(f"monkey -p {self._LEPAO_PKG} -c android.intent.category.LAUNCHER 1")
        time.sleep(2)

    # ========== 设备连接 ==========

    def connect_device(self):
        print("\n" + "=" * 55)
        print("  【第一步】连接设备")
        print("=" * 55)

        try:
            client = AdbClient(host=CFG["adb"]["host"], port=CFG["adb"]["port"])
            devices = [d for d in client.devices() if d.serial != "host"]
        except Exception as e:
            print(f"[-] ADB连接失败: {e}")
            print("[*] 尝试重启ADB...")
            subprocess.run([ADB_PATH, "kill-server"], capture_output=True)
            subprocess.run([ADB_PATH, "start-server"], capture_output=True)
            time.sleep(2)
            try:
                client = AdbClient(host=CFG["adb"]["host"], port=CFG["adb"]["port"])
                devices = [d for d in client.devices() if d.serial != "host"]
            except Exception as e2:
                print(f"[-] 重启后仍失败: {e2}")
                return False

        unauthorized = [d for d in devices if d.serial == "unauthorized"]
        authorized = [d for d in devices if d.serial != "unauthorized"]

        if unauthorized:
            for d in unauthorized:
                print(f"[-] 设备 {d.serial} 未授权！请在手机上点击'允许USB调试'")

        if not authorized:
            print("[-] 没有可用设备")
            print("\n📱 连接指南:")
            print("  1. 数据线连接手机+电脑")
            print("  2. 手机: 设置→开发者选项→USB调试")
            print("  3. 手机弹窗点'允许USB调试'")
            return False

        if len(authorized) > 1:
            print(f"\n[!] 检测到 {len(authorized)} 台设备：")
            for i, d in enumerate(authorized):
                try:
                    model = d.shell("getprop ro.product.model").strip()
                except Exception:
                    model = "未知"
                print(f"  [{i}] {model} ({d.serial})")
            choice = input(f"选择设备编号 [0-{len(authorized)-1}]: ").strip()
            try:
                idx = int(choice)
                self.device = authorized[idx]
            except (ValueError, IndexError):
                self.device = authorized[0]
        else:
            self.device = authorized[0]

        self._print_device_info()
        return True

    def _print_device_info(self):
        try:
            model = self.device.shell("getprop ro.product.model").strip()
            brand = self.device.shell("getprop ro.product.brand").strip()
            android_ver = self.device.shell("getprop ro.build.version.release").strip()
        except Exception:
            model = brand = android_ver = "未知"

        conn = "无线" if ":" in self.device.serial else "USB"
        print("\n┌───────────────────────────────────────┐")
        print("│         设备连接成功 ✓                │")
        print("├───────────────────────────────────────┤")
        print(f"│  型号    : {brand} {model}")
        print(f"│  系统    : Android {android_ver}")
        print(f"│  连接    : {conn}")
        print(f"│  序列号  : {self.device.serial[:20]}")
        print("└───────────────────────────────────────┘")

    # ========== Mock Location ==========

    USE_SHELL_CMD = True
    _SELINUX_OK = False
    _HAS_ROOT = False
    _ANDROID_SDK = 0
    _BOARD = ""
    _MANUFACTURER = ""
    _MOCK_METHOD = "none"

    def _shell(self, cmd, timeout=10):
        try:
            return self.device.shell(cmd, timeout=timeout).strip()
        except Exception:
            return ""

    def _adb_raw(self, *args, timeout=15):
        cmd = [ADB_PATH, "-s", self.device.serial] + list(args)
        try:
            p = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace"
            )
            return p.stdout.strip(), p.stderr.strip(), p.returncode
        except subprocess.TimeoutExpired:
            return "", "TIMEOUT", -1
        except Exception as e:
            return "", str(e), -1

    def _exec(self, shell_cmd, timeout=10, use_root=True):
        out, err, rc = self._adb_raw("shell", shell_cmd, timeout=timeout)
        if rc == 0 and not err:
            return out, True
        if use_root and self._HAS_ROOT:
            su_cmd = f"su -c '{shell_cmd}'"
            out2, err2, rc2 = self._adb_raw("shell", su_cmd, timeout=timeout)
            if rc2 == 0:
                return out2, True
        return out or err, False

    def _check_environment(self):
        print("\n" + "=" * 55)
        print("  🔍 检测手机环境")
        print("=" * 55)

        self._ANDROID_SDK = int(self._exec("getprop ro.build.version.sdk", use_root=False)[0] or "0")
        ver = self._exec("getprop ro.build.version.release", use_root=False)[0]
        self._BOARD = self._exec("getprop ro.product.board", use_root=False)[0]
        self._MANUFACTURER = self._exec("getprop ro.product.manufacturer", use_root=False)[0]
        model = self._exec("getprop ro.product.model", use_root=False)[0]
        en = self._exec("getenforce", use_root=False)[0]

        print(f"  品牌/型号  : {self._MANUFACTURER} {model}")
        print(f"  Android版本: {ver} (SDK {self._ANDROID_SDK})")
        print(f"  Board     : {self._BOARD}")
        print(f"  SELinux   : {en or '(unknown)'}")

        su_out, su_ok = self._exec("su -c 'id'", use_root=False)
        if su_ok and "uid=0" in su_out:
            self._HAS_ROOT = True
            print(f"  Root权限   : ✅ 可用")
        else:
            print(f"  Root权限   : ❌ 不可用")

        if "Enforcing" in en:
            _, ok = self._exec("setenforce 0", use_root=True)
            if ok:
                self._SELINUX_OK = True
                print(f"  SELinux    : ✅ setenforce 0 成功")
            else:
                print(f"  SELinux    : ❌ 无法关闭（需要root）")

        mock_out = self._exec("settings get secure mock_location", use_root=False)[0]
        mock_app = self._exec("settings get secure mock_location_app", use_root=False)[0]
        loc_mode = self._exec("settings get secure location_mode", use_root=False)[0]
        print(f"  mock_location: {mock_out or '(未设置)'}")
        print(f"  mock_app    : {mock_app or '(未指定)'}")
        print(f"  location_mode: {loc_mode} (1=高精度, 2=GPS, 3=网络)")

        self._exec("settings put secure location_mode 3")

        return True

    def _try_method1_cmd_location_providers(self):
        """方法1：cmd location providers（原生方式）"""
        print("\n[方法1] 尝试 cmd location providers ...")

        r1 = self._exec("settings put secure mock_location 1")
        r2 = self._exec("settings put secure mock_location_app com.android.settings")

        providers = ["gps", "network", "passive"]
        if self._ANDROID_SDK >= 30:
            providers.append("fused")

        success_count = 0
        for p in providers:
            self._exec(f"cmd location providers remove-test-provider {p}")
            out, ok = self._exec(f"cmd location providers add-test-provider {p}")
            if ok and not out.startswith("Error") and out != "":
                self._exec(f"cmd location providers set-test-provider-enabled {p} true")
                success_count += 1
                print(f"  ✅ {p} 已添加")
            else:
                print(f"  ❌ {p} 添加失败: [{out[:60]}]")

        check, _ = self._exec("cmd location providers list", use_root=False)
        if check:
            print(f"  provider列表: {check[:200]}")

        return success_count >= 2

    def _try_method2_content_provider(self):
        """方法2：直接往 content provider 写 test provider 数据"""
        print("\n[方法2] 尝试 content provider 写入 ...")

        self._exec("settings put secure mock_location 1")
        self._exec("settings put secure mock_location_app com.android.settings")

        lat = self.start_lat
        lng = self.start_lng
        t = int(time.time() * 1000)

        cmds = [
            f"content call --uri content://com.android.location.provider.settings "
            f"--method set_test_provider_location "
            f"--extra string provider:gps "
            f"--extra string location:{lat} {lng} {t} 3.0 50.0 3",
            f"content insert --uri content://settings/secure "
            f"--bind name:s:mock_gps_location "
            f"--bind value:s:{lat},{lng}",
        ]

        success = False
        for cmd in cmds:
            out, ok = self._exec(cmd)
            if ok and ("rows inserted" in out or "content://" in out or out == ""):
                print(f"  ✅ content命令成功: {cmd[:80]}")
                success = True
            else:
                print(f"  ⚠️  content命令: [{out[:60]}]")

        return success

    def _try_method3_su_am_broadcast(self):
        """方法3：root权限直接广播 + 写文件"""
        if not self._HAS_ROOT:
            return False

        print("\n[方法3] 尝试 root 直接写入 ...")

        self._exec("settings put secure mock_location 1")
        self._exec("settings put secure mock_location_app com.android.settings")

        lat = self.start_lat
        lng = self.start_lng
        t = int(time.time() * 1000)

        fake_xml = f"""<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<gps>
  <provider name="gps">
    <location latitude="{lat}" longitude="{lng}" altitude="50.0" accuracy="3.0" time="{t}"/>
    <status satellites="8" status="3"/>
  </provider>
</gps>"""

        self._exec(f"echo '{fake_xml}' > /data/system/gps.xml")
        self._exec(f"chmod 644 /data/system/gps.xml")

        self._exec(
            f"am broadcast -a android.location.LOCATION_CHANGED "
            f"--es latitude {lat} --es longitude {lng}"
        )

        print(f"  ✅ 已通过root写入 /data/system/gps.xml")
        return True

    FAKE_GPS_APPS = {
        "com.rosteam.gpsemulator": {
            "name": "GPS Emulator (RosTeam)",
            "start_intent": "am start -n com.rosteam.gpsemulator/.ActivityMain",
            "set_location": "am broadcast -a com.rosteam.gpsemulator.SET_LOCATION --es latitude {lat} --es longitude {lng} --es altitude 50 --es accuracy 3",
            "start_fake": "am broadcast -a com.rosteam.gpsemulator.START",
            "stop_fake": "am broadcast -a com.rosteam.gpsemulator.STOP",
        },
        "com.lexa.fakegps": {
            "name": "Fake GPS location (Lexa)",
            "start_intent": "am start -n com.lexa.fakegps/.MainActivity",
            "set_location": "am broadcast -a com.lexa.fakegps.SET --es latitude {lat} --es longitude {lng} --es altitude 50 --es accuracy 3",
            "start_fake": "am broadcast -a com.lexa.fakegps.START",
            "stop_fake": "am broadcast -a com.lexa.fakegps.STOP",
        },
    }

    def _setup_root_mock_engine(self):
        """Root下的无标记位置注入引擎 + 传感器Mock引擎"""
        if not self._HAS_ROOT:
            return False

        print("\n" + "-" * 55)
        print("  🚀 Root Mock 引擎（无标记注入）")
        print("-" * 55)

        self._exec("su -c 'setenforce 0'", use_root=False)

        self._detect_sensor_devices()

        self._exec("su -c 'settings put secure location_mode 3'")
        self._exec("su -c 'settings put secure location_providers_allowed gps,network'")
        self._exec("su -c 'settings put global development_settings_enabled 1'")

        print("  ✅ Root Mock 引擎就绪")
        return True

    def _detect_sensor_devices(self):
        """检测手机上的传感器设备路径"""
        print("\n  [传感器检测] 扫描设备...")
        self._accel_device = None
        self._step_device = None
        self._gyro_device = None

        devices, _ = self._exec("su -c 'cat /proc/bus/input/devices'", use_root=False)
        event_paths, _ = self._exec("su -c 'ls /dev/input/event*'", use_root=False)

        accel_match = None
        step_match = None
        gyro_match = None
        handlers_map = {}

        current_name = None
        for line in devices.split("\n"):
            if "Name=" in line:
                current_name = line.split('"')[1] if '"' in line else line.split("=")[1]
            if "Handlers=" in line and current_name:
                for ev in event_paths.split():
                    ev_name = ev.strip().split("/")[-1]
                    if ev_name in line:
                        handlers_map[current_name] = ev.strip()
                        break

        for name, path in handlers_map.items():
            nl = name.lower()
            if "accelerometer" in nl or "accel" in nl or "bmi160" in nl or "lsm6dsl" in nl:
                self._accel_device = path
                accel_match = name
            elif "step" in nl or "pedometer" in nl:
                self._step_device = path
                step_match = name
            elif "gyro" in nl or "rotation" in nl:
                self._gyro_device = path
                gyro_match = name

        if self._accel_device:
            print(f"    ✅ 加速度传感器: {accel_match} → {self._accel_device}")
        else:
            print(f"    ⚠️  未检测到加速度传感器（将尝试通用路径）")
            self._accel_device = "/dev/input/event4"

        if self._step_device:
            print(f"    ✅ 步数传感器: {step_match} → {self._step_device}")
        else:
            print(f"    ℹ️  未检测到独立步数传感器（将通过content provider注入）")

        if self._gyro_device:
            print(f"    ✅ 陀螺仪: {gyro_match} → {self._gyro_device}")

    def _grant_all_permissions_to_lepao(self):
        """完整授权：前后台定位 + 传感器 + 活动识别 + 开机自启"""
        if not self._LEPAO_PKG:
            return

        pkg = self._LEPAO_PKG
        print(f"\n[权限] 授权 {pkg} 所有必需权限...")

        dangerous_perms = [
            "android.permission.ACCESS_FINE_LOCATION",
            "android.permission.ACCESS_COARSE_LOCATION",
            "android.permission.ACCESS_BACKGROUND_LOCATION",
            "android.permission.ACCESS_ACTIVITY_RECOGNITION",
            "android.permission.BODY_SENSORS",
            "android.permission.VIBRATE",
            "android.permission.FOREGROUND_SERVICE",
            "android.permission.FOREGROUND_SERVICE_SPECIAL_USE",
            "android.permission.WAKE_LOCK",
            "android.permission.RECEIVE_BOOT_COMPLETED",
            "android.permission.WRITE_EXTERNAL_STORAGE",
            "android.permission.READ_EXTERNAL_STORAGE",
            "android.permission.INTERNET",
            "android.permission.ACCESS_NETWORK_STATE",
            "android.permission.ACCESS_WIFI_STATE",
            "android.permission.CHANGE_WIFI_STATE",
            "android.permission.ACCESS_CELLULAR",
            "android.permission.MODIFY_PHONE_STATE",
        ]

        auto_perms = [
            "android.permission.POST_NOTIFICATIONS",
            "android.permission.SCHEDULE_EXACT_ALARM",
            "android.permission.USE_FULL_SCREEN_INTENT",
        ]

        granted = 0
        for perm in dangerous_perms + auto_perms:
            ok, _ = self._exec(f"pm grant {pkg} {perm}", use_root=False)
            if ok:
                granted += 1

        bg_ok, _ = self._exec(
            f"appops set {pkg} ACCESS_BACKGROUND_LOCATION allow",
            use_root=False
        )
        bg_ok2, _ = self._exec(
            f"appops set {pkg} RUN_ANY_IN_BACKGROUND allow",
            use_root=False
        )
        act_ok, _ = self._exec(
            f"appops set {pkg} ACTIVITY_RECOGNITION allow",
            use_root=False
        )

        self._exec(
            f"cmd appops set {pkg} RUN_IN_BACKGROUND allow",
            use_root=True
        )
        self._exec(
            f"cmd appops set {pkg} RUN_ANY_IN_BACKGROUND allow",
            use_root=True
        )

        if self._HAS_ROOT:
            self._exec(f"su -c 'pm grant {pkg} android.permission.ACCESS_BACKGROUND_LOCATION'")
            self._exec(f"su -c 'settings put secure enabled_notification_listeners {pkg}'")
            self._exec(f"su -c 'dumpsys deviceidle disable {pkg}'")
            self._exec(f"su -c 'dumpsys deviceidle whitelist +{pkg}'")
            self._exec(f"su -c 'cmd appops set {pkg} ACCESS_BACKGROUND_LOCATION allow'")
            self._exec(f"su -c 'cmd appops set {pkg} ACTIVITY_RECOGNITION allow'")

        print(f"  ✅ 已授予 {granted}/{len(dangerous_perms + auto_perms)} 权限")
        print(f"  ✅ 后台定位: {bg_ok.strip() or 'OK'}")
        print(f"  ✅ 后台运行: {bg_ok2.strip() or 'OK'}")
        print(f"  ✅ 活动识别: {act_ok.strip() or 'OK'}")

    def _configure_location_services(self):
        """全面配置系统定位服务为高精度模式"""
        print("\n[定位服务] 配置系统定位...")

        if self._HAS_ROOT:
            self._exec("su -c 'settings put secure location_mode 3'")
            self._exec("su -c 'settings put secure location_providers_allowed gps,network'")
            self._exec("su -c 'settings put secure assisted_gps_enabled 1'")
            self._exec("su -c 'settings put secure enable_on_external 1'")
            self._exec("su -c 'settings put global location_enabled 1'")
            self._exec("su -c 'settings put global location_provider_timeout 1'")
            self._exec("su -c 'settings put secure gps_agps_enabled 1'")
            self._exec("su -c 'settings put secure location_service 1'")

            self._exec("su -c 'content insert --uri content://settings/secure --bind name:s:location_providers_allowed --bind value:s:gps,network'")
        else:
            self._exec("settings put secure location_mode 3")
            self._exec("settings put secure location_providers_allowed gps,network")

        self._exec("cmd location set-location-enabled true", use_root=True)

        providers_out, _ = self._exec("cmd location providers list", use_root=False)
        print(f"  ✅ Location providers: {providers_out.strip()[:100]}")

        enabled, _ = self._exec("cmd location is-enabled", use_root=False)
        print(f"  ✅ Location enabled: {enabled.strip()}")

    def _inject_unmarked_location_full(self, lat, lng, accuracy=4.0, altitude=50.0, bearing=0.0, speed_mps=2.0):
        """完整的无标记位置注入（多通道并行）"""
        t = int(time.time() * 1000)
        n = random.randint(4, 10)

        if self._HAS_ROOT:
            self._exec(
                f"su -c 'cmd location providers add-test-provider gps'"
            )
            self._exec(
                f"su -c 'cmd location providers set-test-provider-enabled gps true'"
            )
            self._exec(
                f"su -c 'cmd location providers set-test-provider-location gps "
                f"--location {lat:.6f},{lng:.6f} "
                f"--accuracy {accuracy:.1f} "
                f"--altitude {altitude:.1f} "
                f"--bearing {bearing:.1f} "
                f"--speed {speed_mps:.2f} "
                f"--time {t}'"
            )
            self._exec(
                f"su -c 'cmd location providers set-test-provider-status gps "
                f"--satellites {n} --status 3'"
            )

            self._exec(
                f"su -c 'cmd location inject-location --provider gps "
                f"--location {lat:.6f},{lng:.6f} "
                f"--accuracy {accuracy:.1f} --time {t}'"
            )

            self._exec(
                f"su -c 'cmd location providers add-test-provider fused'"
            )
            self._exec(
                f"su -c 'cmd location providers set-test-provider-enabled fused true'"
            )
            self._exec(
                f"su -c 'cmd location providers set-test-provider-location fused "
                f"--location {lat:.6f},{lng:.6f} "
                f"--accuracy {accuracy:.1f} --altitude {altitude:.1f} --time {t}'"
            )

            self._exec(
                f"su -c 'cmd location inject-location --provider fused "
                f"--location {lat:.6f},{lng:.6f} "
                f"--accuracy {accuracy:.1f} --time {t}'"
            )

            self._exec(
                f"su -c 'cmd location providers add-test-provider network'"
            )
            self._exec(
                f"su -c 'cmd location providers set-test-provider-enabled network true'"
            )
            self._exec(
                f"su -c 'cmd location providers set-test-provider-location network "
                f"--location {lat:.6f},{lng:.6f} "
                f"--accuracy {accuracy * 2:.1f} --altitude {altitude:.1f} --time {t}'"
            )

            gps_xml = f'<?xml version="1.0" encoding="utf-8"?><gps><provider name="gps"><location latitude="{lat}" longitude="{lng}" altitude="{altitude}" accuracy="{accuracy}" speed="{speed_mps}" bearing="{bearing}" time="{t}"/><status satellites="{n}" status="3"/></provider></gps>'
            self._exec(
                f"su -c 'mkdir -p /data/system/location && echo \\'{gps_xml}\\' > /data/system/location/gps.xml'"
            )
            self._exec(
                f"su -c 'chmod 644 /data/system/location/gps.xml && chown root.root /data/system/location/gps.xml'"
            )

            self._exec(
                f"su -c 'am broadcast -a android.location.LOCATION_CHANGED "
                f"--es latitude {lat:.6f} --es longitude {lng:.6f} "
                f"--es altitude {altitude:.1f} "
                f"--ei accuracy {int(accuracy)} --ei time {t} "
                f"--ei provider gps --ei speed {int(speed_mps * 100)} "
                f"--ei bearing {int(bearing)}'"
            )

            self._exec(
                f"su -c 'service call location 3 i32 1 s16 gps "
                f"f {lat:.6f} f {lng:.6f} f {accuracy:.1f} "
                f"f {altitude:.1f} f {bearing:.1f} f {speed_mps:.2f} i32 {t}'"
            )

            if self._LEPAO_PKG:
                lepao = self._LEPAO_PKG
                self._exec(
                    f"su -c 'am broadcast -a android.location.LOCATION_CHANGED "
                    f"--es latitude {lat:.6f} --es longitude {lng:.6f} "
                    f"--ei accuracy {int(accuracy)} --ei provider fused "
                    f"--ei time {t} --ei speed {int(speed_mps * 100)} "
                    f"--ei bearing {int(bearing)} "
                    f"-p {lepao}'"
                )
                cur_dist = int(getattr(self, "total_distance", 0))
                cur_steps = getattr(self, "_step_counter_total", 0)
                self._exec(
                    f"su -c 'am broadcast -a {lepao}.LOCATION_UPDATE "
                    f"--es latitude {lat:.6f} --es longitude {lng:.6f} "
                    f"--ei speed {int(speed_mps * 100)} "
                    f"--ei distance {cur_dist} "
                    f"--ei steps {cur_steps}'"
                )
        else:
            self._exec(f"cmd location inject-location --provider gps --location {lat:.6f},{lng:.6f} --accuracy {accuracy:.1f} --time {t}")
            if self._ANDROID_SDK >= 30:
                self._exec(f"cmd location inject-location --provider fused --location {lat:.6f},{lng:.6f} --accuracy {accuracy:.1f} --time {t}")
            self._exec(
                f"am broadcast -a android.location.LOCATION_CHANGED "
                f"--es latitude {lat:.6f} --es longitude {lng:.6f} "
                f"--ei accuracy {int(accuracy)} --ei provider gps --ei time {t}"
            )

    def _filter_anomaly_point(self, prev_lat, prev_lng, curr_lat, curr_lng, max_speed_kmh=15.0):
        """过滤异常点（瞬移/漂移）"""
        dist = haversine_distance(prev_lat, prev_lng, curr_lat, curr_lng)
        if dist < 0.1:
            return False, dist

        max_speed_mps = max_speed_kmh / 3.6
        if dist > max_speed_mps * self.gps_interval * 2:
            print(f"    [!] 过滤异常点: 距离={dist:.1f}m 超过最大速度")
            return True, dist

        lat_range = (self.start_lat - 0.02, self.start_lat + 0.02)
        lng_range = (self.start_lng - 0.02, self.start_lng + 0.02)
        if not (lat_range[0] <= curr_lat <= lat_range[1] and lng_range[0] <= curr_lng <= lng_range[1]):
            print(f"    [!] 过滤漂移点: ({curr_lat:.5f}, {curr_lng:.5f}) 超出范围")
            return True, dist

        return False, dist

    def _mock_acceleration_waveform(self):
        """模拟真实跑步的加速度波形（周期性波动 ±1.5g）"""
        if not hasattr(self, "_accel_device") or not self._accel_device:
            return

        t = time.time()
        step_freq = 3.5
        phase = (t * step_freq * 2 * math.pi) % (2 * math.pi)

        ax = round(random.gauss(0.3, 0.15), 3)
        ay = round(math.sin(phase) * 1.2 + random.gauss(0, 0.2), 3)
        az = round(math.sin(phase * 2) * 0.8 + random.gauss(9.8, 0.3), 3)

        try:
            cmds = [
                f"su -c 'sendevent {self._accel_device} 3 0 {int(ax * 1000000)}'",
                f"su -c 'sendevent {self._accel_device} 3 1 {int(ay * 1000000)}'",
                f"su -c 'sendevent {self._accel_device} 3 2 {int(az * 1000000)}'",
                f"su -c 'sendevent {self._accel_device} 0 0 0'",
            ]
            for c in cmds:
                self._exec(c, use_root=False)
        except Exception:
            pass

    def _inject_step_count(self, additional_steps):
        """同步注入步数到系统Step Counter"""
        try:
            current_total = getattr(self, "_step_counter_total", 0) + additional_steps
            self._step_counter_total = current_total

            self._exec(
                f"su -c 'content update --uri content://settings/system "
                f"--bind value:i:{int(current_total)} --where name=step_count'"
            )
            self._exec(
                f"su -c 'settings put system step_count {int(current_total)}'"
            )
        except Exception:
            pass

    def _clear_all_mock_traces(self):
        """清除所有Mock痕迹，让系统看起来干净"""
        print("\n  [痕迹清除] 清除所有Mock相关设置...")

        self._exec("su -c 'settings put secure mock_location 0'")
        self._exec("su -c 'settings put secure mock_location_app null'")
        self._exec("su -c 'settings put secure allow_mock_location 0'")
        self._exec("su -c 'settings put global mock_location 0'")
        self._exec("su -c 'settings put global mock_location_app null'")

        self._exec("su -c 'cmd location providers set-test-provider-enabled gps false'")
        self._exec("su -c 'cmd location providers remove-test-provider gps'")
        self._exec("su -c 'cmd location providers set-test-provider-enabled network false'")
        self._exec("su -c 'cmd location providers remove-test-provider network'")
        self._exec("su -c 'cmd location providers set-test-provider-enabled passive false'")
        self._exec("su -c 'cmd location providers remove-test-provider passive'")
        if self._ANDROID_SDK >= 30:
            self._exec("su -c 'cmd location providers set-test-provider-enabled fused false'")
            self._exec("su -c 'cmd location providers remove-test-provider fused'")

        self._exec("su -c 'am broadcast -a android.location.PROVIDERS_CHANGED'")
        self._exec("su -c 'am broadcast -a android.intent.action.TIME_TICK'")

    def _detect_fake_gps_apps(self):
        found = []
        for pkg, info in self.FAKE_GPS_APPS.items():
            out, _ = self._exec(f"pm list packages {pkg}", use_root=False)
            if pkg in out:
                found.append((pkg, info))
                print(f"    ✅ 已安装: {info['name']} ({pkg})")
        return found

    def setup_mock_location(self):
        self._check_environment()

        print("\n" + "=" * 55)
        print("  [GPS] 配置 Mock Location")
        print("=" * 55)

        self._USED_FAKE_GPS_PKG = None
        self._step_counter_total = 0
        self._MOCK_METHOD = "none"

        self._exec("settings put global development_settings_enabled 1")
        self._exec("settings put secure location_mode 3")
        self._exec("settings put secure mock_location 1")

        if self._HAS_ROOT:
            self._exec("su -c 'settings put secure location_mode 3'")
            self._exec("su -c 'cmd location set-location-enabled true'")
            self._MOCK_METHOD = "root_inject"
            print("  [OK] Root可用 -> 使用 cmd location inject")
        else:
            print("  [!] 无Root，尝试 Fake GPS APP...")
            found = self._detect_fake_gps_apps()
            if found:
                pkg, info = found[0]
                self._USED_FAKE_GPS_PKG = pkg
                self._MOCK_METHOD = "fake_gps_app"
                self._exec(f"settings put secure mock_location_app {pkg}")
                self._exec(info["start_intent"])
                time.sleep(1)
                print(f"  [OK] 使用 {info['name']}")
            else:
                print("\n" + "=" * 55)
                print("  [!!] 无Root也无Fake GPS APP")
                print("=" * 55)
                self._show_install_guide()
                return False

        if self._LEPAO_PKG:
            self._exec(f"pm grant {self._LEPAO_PKG} android.permission.ACCESS_FINE_LOCATION")
            self._exec(f"pm grant {self._LEPAO_PKG} android.permission.ACCESS_COARSE_LOCATION")
            self._exec(f"pm grant {self._LEPAO_PKG} android.permission.ACCESS_BACKGROUND_LOCATION")
            if self._HAS_ROOT:
                self._exec(f"su -c 'pm grant {self._LEPAO_PKG} android.permission.ACCESS_BACKGROUND_LOCATION'")

        return True

    def _show_install_guide(self):
        brand, _ = self._exec("getprop ro.product.brand", use_root=False)
        model, _ = self._exec("getprop ro.product.model", use_root=False)
        brand_low = brand.lower()
        print(f"""
  ╔══════════════════════════════════════════════════╗
  ║   需要 Root 或 Fake GPS APP（否则乐跑不认Mock！）   ║
  ╚══════════════════════════════════════════════════╝

  📱 你的手机: {brand.strip()} {model.strip()}

  ── 方案A（推荐）: Root ──
  如果你的手机已Root，脚本会自动使用无标记注入引擎
  （不需要装任何APP，直接绕过乐跑的所有Mock检测）

  ── 方案B: Fake GPS APP ──
  应用商店搜索并安装【GPS Emulator】（RosTeam）免费版""")

        if "xiaomi" in brand_low or "redmi" in brand_low:
            print("""
  小米/红米设置路径: 设置→更多设置→开发者选项→选择模拟位置信息应用
  (连点"MIUI版本"7次开启开发者选项)""")
        elif "huawei" in brand_low or "honor" in brand_low:
            print("""
  华为/荣耀设置路径: 设置→关于手机→连点"版本号"7次→开发人员选项→选择模拟位置信息应用""")
        elif "oppo" in brand_low or "realme" in brand_low:
            print("""
  OPPO/Realme设置路径: 设置→关于手机→连点"版本号"7次→其他设置→开发者选项→选择模拟位置信息应用""")
        elif "vivo" in brand_low or "iqoo" in brand_low:
            print("""
  Vivo设置路径: 设置→系统管理→关于手机→连点"软件版本号"7次→开发者选项→选择模拟位置信息应用""")
        elif "samsung" in brand_low:
            print("""
  三星设置路径: 设置→关于手机→软件信息→连点"编译编号"7次→开发者选项→选择模拟位置信息应用""")
        print("""
  ── 装完后 ──
  回到电脑，重新运行脚本！""")

    def cleanup_mock_location(self):
        if self._MOCK_METHOD == "root_inject":
            self._clear_all_mock_traces()
            print("[+] 已清除所有Mock痕迹")
        else:
            pkg = getattr(self, "_USED_FAKE_GPS_PKG", None)
            if pkg:
                info = self.FAKE_GPS_APPS.get(pkg)
                if info:
                    self._exec(info["stop_fake"])
            self._exec("settings put secure mock_location 0")
            self._exec("settings put secure mock_location_app null")

    def mock_all_providers(self, lat, lng, accuracy=5.0, bearing=0.0, speed_mps=2.0):
        t = int(time.time() * 1000)

        if self._MOCK_METHOD == "root_inject" and self._HAS_ROOT:
            self._exec(
                f"su -c 'cmd location inject-location --provider gps "
                f"--location {lat:.6f},{lng:.6f} --accuracy {accuracy:.1f} --time {t}'"
            )
            self._exec(
                f"su -c 'cmd location inject-location --provider fused "
                f"--location {lat:.6f},{lng:.6f} --accuracy {accuracy:.1f} --time {t}'"
            )
            self._exec(
                f"su -c 'am broadcast -a android.location.LOCATION_CHANGED "
                f"--es latitude {lat:.6f} --es longitude {lng:.6f} "
                f"--ei accuracy {int(accuracy)} --ei provider gps --ei time {t}'"
            )
            if self._LEPAO_PKG:
                self._exec(
                    f"su -c 'am broadcast -a android.location.LOCATION_CHANGED "
                    f"--es latitude {lat:.6f} --es longitude {lng:.6f} "
                    f"--ei accuracy {int(accuracy)} --ei provider gps "
                    f"--ei time {t} -p {self._LEPAO_PKG}'"
                )
        elif self._USED_FAKE_GPS_PKG:
            info = self.FAKE_GPS_APPS.get(self._USED_FAKE_GPS_PKG)
            if info:
                self._exec(info["set_location"].format(lat=lat, lng=lng))
                self._exec(info["start_fake"])
                if self._LEPAO_PKG:
                    self._exec(
                        f"am broadcast -a android.location.LOCATION_CHANGED "
                        f"--es latitude {lat:.6f} --es longitude {lng:.6f} "
                        f"--ei accuracy {int(accuracy)} --ei provider gps "
                        f"--ei time {t} -p {self._LEPAO_PKG}"
                    )
        else:
            self._exec(
                f"cmd location inject-location --provider gps "
                f"--location {lat:.6f},{lng:.6f} --accuracy {accuracy:.1f} --time {t}"
            )
            self._exec(
                f"am broadcast -a android.location.LOCATION_CHANGED "
                f"--es latitude {lat:.6f} --es longitude {lng:.6f} "
                f"--ei accuracy {int(accuracy)} --ei provider gps --ei time {t}"
            )

    def verify_location(self):
        out, _ = self._exec("dumpsys location", use_root=False)
        lines = []
        for line in out.split("\n"):
            low = line.lower()
            if any(k in low for k in ("last location", "mock", "test-provider",
                                       "provider", "latitude", "longitude")):
                lines.append(line.strip())
        return "\n".join(lines[:15])

    # ========== 触摸 ==========

    def touch(self, x, y):
        self._adb_raw("shell", f"input tap {x} {y}")
        time.sleep(0.4)

    # ========== 轨迹生成 ==========

    def generate_route_points(self):
        speed_mps = self.base_speed / 3.6
        kwargs = dict(
            start_lat=self.start_lat,
            start_lng=self.start_lng,
            lat_offset=self.lat_offset,
            lng_offset=self.lng_offset,
            total_distance_m=self.target_distance,
            speed_mps=speed_mps,
            interval=self.gps_interval
        )

        mode = self.track_mode
        if mode == "oval":
            points = RouteGenerator.generate_oval(**kwargs)
        elif mode == "rectangle":
            points = RouteGenerator.generate_rectangle(**kwargs)
        elif mode == "loop":
            points = RouteGenerator.generate_loop(**kwargs)
        else:
            points = RouteGenerator.generate_oval(**kwargs)

        points = RouteGenerator.apply_natural_noise(points, self.walk_amount, self.step_counter)
        return points

    # ========== 主GPS循环 ==========

    def gps_loop(self):
        print('[*] GPS loop started')
        self.gps_points = self.generate_route_points()
        print(f'[+] Generated {len(self.gps_points)} track points')

        prev_lat, prev_lng = self.start_lat, self.start_lng
        self.mock_all_providers(prev_lat, prev_lng, accuracy=3.0)
        print(f'[+] Start: ({prev_lat:.6f}, {prev_lng:.6f})')

        self.start_time = time.time()
        local_step = 0

        while self.running:
            if self.paused:
                time.sleep(0.5)
                continue

            reroute_needed = False
            for lat, lng in self.gps_points:
                if not self.running:
                    break

                while self.paused and self.running:
                    time.sleep(0.5)

                local_step += 1
                self.step_counter += 1

                dist = haversine_distance(prev_lat, prev_lng, lat, lng)
                if dist < 0.1:
                    prev_lat, prev_lng = lat, lng
                    continue

                self.mock_all_providers(lat, lng, accuracy=random.gauss(4, 2))

                self.total_distance += dist
                prev_lat, prev_lng = lat, lng

                if local_step % 20 == 0:
                    elapsed_m = (time.time() - self.start_time) / 60
                    pct = self.total_distance / self.target_distance * 100
                    print(f'  [{self.step_counter}] {self.total_distance/1000:.2f}km / {self.target_distance/1000:.1f}km ({pct:.0f}%) | ({lat:.5f},{lng:.5f}) | {elapsed_m:.1f}min')

                    if self._LEPAO_PKG:
                        st, _ = self._exec(
                            f'dumpsys activity processes | grep {self._LEPAO_PKG}',
                            use_root=False
                        )
                        if not st:
                            print('  [!] Lepao killed, restarting...')
                            self._launch_lepao()
                            self.mock_all_providers(lat, lng, accuracy=3.0)

                progress = self.total_distance / self.target_distance
                if progress >= 1.0:
                    break

                time.sleep(self.gps_interval)

            if self.total_distance < self.target_distance and self.running:
                if not reroute_needed:
                    print('[*] Route done, regenerating...')
                    self.gps_points = self.generate_route_points()
                    reroute_needed = True
                else:
                    break

        elapsed = time.time() - self.start_time if self.start_time else 0
        self._print_summary(elapsed)
        print('[*] GPS loop stopped')

    def _maybe_pause(self):
        """随机模拟短暂暂停（系鞋带、看手机等）"""
        if random.random() < self.pause_probability:
            pause_dur = random.uniform(self.min_pause, self.max_pause)
            print(f"  [*] 模拟暂停 {pause_dur:.0f}秒...")
            start = time.time()
            while time.time() - start < pause_dur and self.running:
                self.paused = True
                time.sleep(0.5)
            self.paused = False

    def _print_summary(self, elapsed):
        print("\n" + "=" * 55)
        print("  🏃 步道乐跑数据摘要")
        print("=" * 55)
        total_km = self.total_distance / 1000
        print(f"  总距离    : {total_km:.2f} km")
        print(f"  用时      : {elapsed / 60:.1f} 分钟")
        if elapsed > 0:
            avg_speed = total_km / (elapsed / 3600)
            print(f"  平均速度  : {avg_speed:.1f} km/h")
        est_steps = int(self.total_distance / self.step_length)
        print(f"  估算步数  : {est_steps} 步 (步长{self.step_length*100:.0f}cm)")
        print(f"  GPS点数   : {self.step_counter}")
        print(f"  分段数    : {len(self.segment_data)}")
        if self.segment_data:
            seg_speeds = [sum(v)/len(v) for v in self.segment_data.values()]
            print(f"  分段配速  : "
                  f"最快 {max(seg_speeds):.1f} km/h / "
                  f"最慢 {min(seg_speeds):.1f} km/h")
        print(f"  预计消耗  : {self.total_distance * 1.04:.0f} 千卡")
        print("=" * 55)

    # ========== 主入口 ==========

    def run(self, auto_touch=None):
        if auto_touch is None:
            auto_touch = CFG["touch"]["enabled"]

        if not self.device:
            if not self.connect_device():
                return

        lepao = self._find_lepao_app()
        if lepao:
            print(f"\n[*] 检测到乐跑APP: {lepao}")
            print(f"    Activity: {self._LEPAO_ACTIVITY or '(未知)'}")

            print("[*] 授权乐跑所有必需权限...")
            for perm in [
                "android.permission.ACCESS_FINE_LOCATION",
                "android.permission.ACCESS_COARSE_LOCATION",
                "android.permission.ACCESS_BACKGROUND_LOCATION",
                "android.permission.VIBRATE",
                "android.permission.FOREGROUND_SERVICE",
                "android.permission.WAKE_LOCK",
            ]:
                self._exec(f"pm grant {lepao} {perm}", use_root=False)
            print("  ✅ 权限已授予")
        else:
            print("\n[!] 没检测到乐跑APP包名")

        self._force_stop_lepao()
        print("[*] 已强制停止乐跑APP")

        print("\n[*] 启动乐跑APP（让它先注册位置监听器）...")
        self._launch_lepao()
        time.sleep(4)

        if not self.setup_mock_location():
            self._show_mock_failure_help()
            return

        print("\n" + "=" * 55)
        print("  ☀️ 步道乐跑自动化 V2.00")
        print("=" * 55)
        print(f"  目标距离    : {CFG['run']['target_km']} km")
        print(f"  速度范围    : {self.min_speed} ~ {self.max_speed} km/h")
        print(f"  基础速度    : {self.base_speed} km/h")
        print(f"  预计用时    : {CFG['run']['target_km'] / self.base_speed * 60:.0f} 分钟")
        print(f"  路线模式    : {CFG['location']['track_mode']}")
        print(f"  Mock方式    : {self._MOCK_METHOD}")
        print(f"  乐跑包名    : {lepao or '(未检测到)'}")
        print("=" * 55)

        print("\n[*] 推送 Mock 起点位置（密集推送）...")
        for i in range(5):
            self.mock_all_providers(self.start_lat, self.start_lng, accuracy=random.gauss(4, 1))
            time.sleep(0.15)

        verify, _ = self._exec(
            "dumpsys location | grep -i 'last location\\|fused' -A2",
            use_root=False
        )
        print(f"  dumpsys 验证: {verify[:250] if verify else '(无返回)'}")

        if lepao:
            self._exec(
                f"am broadcast -a android.location.LOCATION_CHANGED "
                f"--es latitude {self.start_lat} --es longitude {self.start_lng} "
                f"--ei accuracy 3 --ei provider gps --ei time {int(time.time()*1000)}",
                use_root=True
            )

        self.running = True
        self.gps_thread = threading.Thread(target=self.gps_loop, daemon=True)
        self.gps_thread.start()

        if auto_touch:
            delay = CFG["touch"]["action_delay"]
            print(f"\n[*] {delay}秒后点击开始按钮...")
            time.sleep(delay)
            tc = CFG["touch"]
            self.touch(tc["start_btn"]["x"], tc["start_btn"]["y"])
            print("[+] 已点击开始按钮")
            time.sleep(1)
            self.mock_all_providers(self.start_lat, self.start_lng, accuracy=3.0)
            print("[+] 点击开始后再次推送Mock起点")

        print("\n[*] 🏃 步道乐跑进行中...")
        print("[*] 按 Ctrl+C 可随时结束")

        try:
            while self.running and self.gps_thread.is_alive():
                self.gps_thread.join(timeout=2)
                if self.total_distance >= self.target_distance:
                    print("\n[+] 🎯 目标距离已达到！")
                    break
        except KeyboardInterrupt:
            print("\n[!] 收到中断信号，正在停止...")

        self.running = False
        if self.gps_thread:
            self.gps_thread.join(timeout=3)

        if auto_touch:
            delay = CFG["touch"]["action_delay"]
            print(f"\n[*] {delay}秒后点击结束按钮...")
            time.sleep(delay)
            tc = CFG["touch"]
            self.touch(tc["end_btn"]["x"], tc["end_btn"]["y"])
            print("[+] 已点击结束按钮")
            time.sleep(2)
            self.touch(tc["confirm_btn"]["x"], tc["confirm_btn"]["y"])
            print("[+] 已点击确认按钮")

        self.cleanup_mock_location()
        print("\n[+] ✅ 步道乐跑完成！")

    def _show_mock_failure_help(self):
        """当所有Mock方案失败时，给出清晰的手动解决步骤"""
        print("\n" + "=" * 55)
        print("  ❌ 所有Mock Location方案都失败了！")
        print("  你的手机ROM很可能阉割了原生Mock能力")
        print("=" * 55)
        print("""
  📱 请按以下步骤手动解决（任选其一）：

  ── 方案 A：手动设置Mock位置应用（最推荐）──

  ① 手机打开 → 设置 → 开发者选项
     → 找到 "选择Mock位置应用" (或"模拟位置")
     → 选择 "无" 或者 一个你装的Mock APP

  ② 如果列表是空的，需要先装一个Mock APP：
     在应用商店搜索 "Fake GPS Location Professional"
     或者 "Mock Locations (Gps)"，随便装一个

  ③ 装完后再回到开发者选项 → Mock位置应用
     → 选中那个APP

  ④ 然后重新运行本脚本！


  ── 方案 B：用Shizuku免ROOT ──

  Shizuku可以通过ADB授权，让APP获得shell权限
  安装Shizuku后，脚本可以调用更高权限的API


  ── 方案 C：ROOT后自动 ──

  如果手机已ROOT，脚本会自动：
  ① setenforce 0 关闭SELinux
  ② 用su执行所有Mock命令
  ③ 直接写 /data/system/gps.xml


  ── 你的手机信息 ──""")
        if self._MANUFACTURER:
            print(f"  品牌: {self._MANUFACTURER}")
        if self._ANDROID_SDK:
            print(f"  SDK : {self._ANDROID_SDK}")
        if self._HAS_ROOT:
            print(f"  Root: ✅ 可用（奇怪，有root却失败了...）")
        else:
            print(f"  Root: ❌ 不可用")
        if self._SELINUX_OK:
            print(f"  SELinux: 已关闭")
        else:
            print(f"  SELinux: Enforcing（拦截了Mock）")
        print("=" * 55)

    def quick_test(self):
        if not self.device:
            if not self.connect_device():
                return

        if not self.setup_mock_location():
            self._show_mock_failure_help()
            return

        print("\n" + "=" * 55)
        print("  🧪 GPS模拟诊断测试（覆盖所有Provider）")
        print("=" * 55)

        print("\n[1/5] Mock前真实位置...")
        real_pos, _ = self._exec("dumpsys location | grep -i 'last location' -A3")
        print(f"  系统当前最后位置: {real_pos[:150] if real_pos else '(无数据)'}")

        print("\n[2/5] 设置Mock位置...")
        self.mock_all_providers(self.start_lat, self.start_lng, accuracy=3.0)
        print(f"  → Mock目标: ({self.start_lat:.6f}, {self.start_lng:.6f})")
        time.sleep(2)

        print("\n[3/5] 验证Mock是否进入LocationManager...")
        verify, _ = self._exec("dumpsys location | grep -i 'last location' -A5")
        print(f"  dumpsys返回: {verify[:300] if verify else '(无返回！说明Mock未生效)'}")

        fused_check, _ = self._exec(
            "dumpsys location | grep -i 'fused' -A3"
        )
        print(f"  Fused Provider状态: {fused_check[:200] if fused_check else '(无返回)'}")

        providers, _ = self._exec("cmd location providers list")
        print(f"  当前Provider列表: {providers[:200] if providers else '(无返回)'}")

        test_providers, _ = self._exec("cmd location providers get-test-provider-enabled gps")
        print(f"  gps test-provider启用: {test_providers or '(无返回)'}")

        print("\n[4/5] 模拟3次移动...")
        for i in range(3):
            lat = self.start_lat + self.lat_offset * 0.3 * (i + 1) / 3
            lng = self.start_lng + self.lng_offset * 0.3 * (i + 1) / 3
            self.mock_all_providers(lat, lng, accuracy=random.gauss(5, 2))
            print(f"  → ({lat:.6f}, {lng:.6f})")
            time.sleep(1.5)

        print("\n[5/5] 最终验证...")
        final, _ = self._exec("dumpsys location | grep -i 'last location' -A5")
        print(f"  最终dumpsys: {final[:300] if final else '(无返回)'}")

        self.cleanup_mock_location()

        print("\n" + "=" * 55)
        print("  📋 诊断结论")
        print("=" * 55)
        print("  ✅ 如果 dumpsys 能看到你 Mock 的坐标")
        print("     → Mock成功！乐跑APP应该能收到")
        print("")
        print("  ❌ 如果 dumpsys 看不到 Mock 的坐标")
        print("     → SELinux拦截（需要root setenforce 0）")
        print("     → MIUI/ColorOS等定制ROM屏蔽了原生Mock")
        print("     → cmd location providers 命令被厂商修改")
        print("")
        print("  ⚡ 解决方案（按推荐顺序）:")
        print("  ① 设置 → 开发者选项 → Mock位置应用 → 选一个Mock APP")
        print("  ② 用 Magisk + Shizuku 来绕过SELinux")
        print("  ③ 刷root，脚本会自动 setenforce 0")
        print("=" * 55)

    def diagnostic_location(self):
        """深度诊断位置服务状态"""
        print("\n" + "=" * 55)
        print("  🔍 位置服务深度诊断")
        print("=" * 55)

        self._check_environment()

        print("\n── LocationManager详细状态 ──")
        lm, _ = self._exec("dumpsys location")
        if lm:
            for keyword in ("Last location", "Provider", "gps", "Test-provider",
                           "fused", "Mock", "enabled"):
                lines = [l for l in lm.split("\n") if keyword.lower() in l.lower()]
                for l in lines[:3]:
                    print(f"  {l.strip()[:120]}")
        else:
            print("  (无法获取dumpsys location)")

        print("\n── 强制Mock测试 ──")
        self.setup_mock_location()
        self.mock_all_providers(self.start_lat, self.start_lng)
        time.sleep(2)

        out, _ = self._exec("dumpsys location | grep -i 'last\\|current\\|mock' -A2")
        print(f"  Push后状态: {out[:300] if out else '(无返回)'}")

        self.cleanup_mock_location()
        print("\n[+] 诊断完成")

    def interactive_menu(self):
        if not self.device:
            if not self.connect_device():
                return

        while True:
            print("\n" + "=" * 55)
            print("  🏃 步道乐跑自动化 V2.0 — 交互菜单")
            print("=" * 55)
            print("  1. 🏃  开始跑步（完整自动）")
            print("  2. 🛣️  仅GPS轨迹（手动点击开始）")
            print("  3. 🧪  GPS快速测试")
            print("  4. 🔍  位置服务深度诊断")
            print("  5. 📍  手动设置GPS位置")
            print("  6. 👆  模拟屏幕点击")
            print("  7. 🛠️  执行ADB命令")
            print("  8. ⚙️   修改配置")
            print("  9. 📋  查看当前配置")
            print("  a. 📸  截屏")
            print("  b. 📄  导出手机诊断文件（关键！）")
            print("  c. 📲  安装Fake GPS APP（电脑帮你装）")
            print("  d. 🧭  Mock位置应用设置引导")
            print("  0. ❌  退出")
            print("=" * 55)

            try:
                choice = input("\n请选择 > ").strip().lower()

                if choice == "1":
                    try:
                        self.run(auto_touch=True)
                    except KeyboardInterrupt:
                        self.stop()
                elif choice == "2":
                    try:
                        self.run(auto_touch=False)
                    except KeyboardInterrupt:
                        self.stop()
                elif choice == "3":
                    self.quick_test()
                elif choice == "4":
                    self.diagnostic_location()
                elif choice == "5":
                    lat = float(input("纬度: ").strip())
                    lng = float(input("经度: ").strip())
                    if not self.device:
                        self.connect_device()
                    self.setup_mock_location()
                    self.mock_all_providers(lat, lng)
                    print(f"[+] 已设置为 ({lat}, {lng})")
                    print(f"[+] 请打开手机地图验证位置是否变化")
                elif choice == "6":
                    x = int(input("X坐标: ").strip())
                    y = int(input("Y坐标: ").strip())
                    self.touch(x, y)
                    print(f"[+] 已点击 ({x}, {y})")
                elif choice == "7":
                    while True:
                        cmd = input("ADB命令 (空返回): adb shell ").strip()
                        if not cmd:
                            break
                        print(f"$ adb shell {cmd}")
                        out, ok = self._exec(cmd)
                        print(f"  [{'OK' if ok else 'FAIL'}] {out or '(无输出)'}")
                elif choice == "8":
                    self._config_menu()
                elif choice == "9":
                    self._show_config()
                elif choice == "a":
                    self.take_screenshot()
                elif choice == "b":
                    path = input("输出文件路径 (默认 phone_diagnostic.txt): ").strip()
                    if not path:
                        path = "phone_diagnostic.txt"
                    self._check_environment()
                    self.export_diagnostic(path)
                elif choice == "c":
                    self._install_fake_gps_app()
                elif choice == "d":
                    self._show_mock_setup_guide()
                elif choice == "0":
                    print("👋 再见！")
                    break
                else:
                    print("[!] 无效选项")
            except (EOFError, KeyboardInterrupt):
                print("\n👋 再见！")
                break
            except Exception as e:
                print(f"[-] 错误: {e}")
                import traceback
                traceback.print_exc()

    def _install_fake_gps_app(self):
        """尝试通过ADB在手机上安装Fake GPS APP"""
        print("\n" + "=" * 55)
        print("  📲 自动安装 Fake GPS APP")
        print("=" * 55)

        print("""
  电脑ADB无法直接从应用商店下载APP到手机。
  需要你手动操作手机来安装：

  ── 最简单的方式（推荐）──

  ① 手机打开浏览器，访问任意搜索网站
  ② 搜索 "GPS Emulator RosTeam APK"
  ③ 下载最新的 APK 文件
  ④ 打开文件管理器安装它
     （可能需要开启"允许安装未知来源"）

  ── 或者用应用商店 ──

  ① 打开手机应用商店（应用宝/华为应用市场等）
  ② 搜索 "Fake GPS" 或 "GPS Emulator"
  ③ 随便装一个评分高的

  ── 装完后必须做 ──       

  手机 → 设置 → 开发者选项
       → 找到 "Mock位置应用" / "选择模拟位置信息应用"
       → 选中你刚装的那个APP

  完成后重新运行脚本即可！
        """)

        input("\n装好后回到这里，按回车继续...")

    def _show_mock_setup_guide(self):
        """引导用户在手机上设置Mock位置应用"""
        print("\n" + "=" * 55)
        print("  🧭 Mock位置应用设置引导")
        print("=" * 55)

        en, _ = self._exec("getenforce", use_root=False)
        sdk, _ = self._exec("getprop ro.build.version.sdk", use_root=False)
        mock_app, _ = self._exec("settings get secure mock_location_app", use_root=False)
        mock_loc, _ = self._exec("settings get secure mock_location", use_root=False)

        print(f"""
  当前状态：
    SDK: {sdk or '?'}  SELinux: {en or '?'}
    mock_location: {mock_loc or '(未设置)'}
    mock_location_app: {mock_app or '(未指定！)'}

  ── 现在请在手机上按以下步骤操作 ──

  Step 1: 打开 【设置】

  Step 2: 找到 【开发者选项】
          - 如果没有这个选项：设置 → 关于手机 → 连续点"版本号"7次

  Step 3: 在开发者选项里找：
          - "Mock位置应用"   ← MIUI/ColorOS/OneUI 叫这个
          - "选择模拟位置信息应用" ← 原生Android叫这个
          - "模拟位置"       ← 有些ROM叫这个

  Step 4: 如果列表里只有 "无"：
          → 你手机上没装 Mock GPS APP
          → 选菜单【c】安装一个Fake GPS APP
          → 然后回到这里选它

  Step 5: 选好之后，不要关闭开发者选项

  Step 6: 回到电脑，重新运行脚本！

  ── 如果找不到开发者选项 ──

  在设置顶部搜索框里搜索 "开发者" 或 "USB调试"
  一般能直接搜到入口

  ── 如果按了还是不行 ──

  选菜单【b】导出诊断文件发给我分析
        """)

        input("按回车返回菜单...")

    def _config_menu(self):
        global CFG
        while True:
            print("\n── 配置修改（步道乐跑专项）──")
            print(f"  1. 目标距离     : {CFG['run']['target_km']} km")
            print(f"  2. 基础速度     : {CFG['run']['base_speed_kmh']} km/h")
            print(f"  3. 速度上限     : {CFG['run']['max_speed_kmh']} km/h (防骑车检测)")
            print(f"  4. 速度下限     : {CFG['run']['min_speed_kmh']} km/h")
            print(f"  5. GPS起点纬度   : {CFG['location']['start_lat']}")
            print(f"  6. GPS起点经度   : {CFG['location']['start_lng']}")
            print(f"  7. 纬度偏移     : {CFG['location']['lat_offset']}")
            print(f"  8. 经度偏移     : {CFG['location']['lng_offset']}")
            print(f"  9. 路线模式     : {CFG['location']['track_mode']}")
            print(f"  10. GPS间隔     : {CFG['run']['gps_interval']}s")
            print(f"  11. 分段距离     : {CFG['run']['segment_distance_m']}m")
            print(f"  12. 模拟暂停概率 : {CFG['run']['pause_probability']}")
            print(f"  13. 人性化       : {'是' if CFG['run']['human_like'] else '否'}")
            print(f"  14. 触摸坐标     : start{CFG['touch']['start_btn']}")
            print(f"  0. 返回")

            try:
                c = input("选择要修改的项 > ").strip()
                if c == "1":
                    CFG["run"]["target_km"] = float(input("目标距离(km): ").strip())
                elif c == "2":
                    CFG["run"]["base_speed_kmh"] = float(input("基础速度(km/h): ").strip())
                elif c == "3":
                    v = float(input("速度上限(建议≤12防骑车检测): ").strip())
                    CFG["run"]["max_speed_kmh"] = v
                elif c == "4":
                    CFG["run"]["min_speed_kmh"] = float(input("速度下限(km/h): ").strip())
                elif c == "5":
                    CFG["location"]["start_lat"] = float(input("起点纬度: ").strip())
                elif c == "6":
                    CFG["location"]["start_lng"] = float(input("起点经度: ").strip())
                elif c == "7":
                    CFG["location"]["lat_offset"] = float(input("纬度偏移: ").strip())
                elif c == "8":
                    CFG["location"]["lng_offset"] = float(input("经度偏移: ").strip())
                elif c == "9":
                    m = input("路线模式(oval=椭圆操场/rectangle=矩形/loop=往返): ").strip()
                    if m in ("oval", "rectangle", "loop"):
                        CFG["location"]["track_mode"] = m
                elif c == "10":
                    CFG["run"]["gps_interval"] = float(input("GPS间隔(秒): ").strip())
                elif c == "11":
                    CFG["run"]["segment_distance_m"] = float(input("分段距离(米): ").strip())
                elif c == "12":
                    CFG["run"]["pause_probability"] = float(input("暂停概率(0-1): ").strip())
                elif c == "13":
                    CFG["run"]["human_like"] = not CFG["run"]["human_like"]
                elif c == "14":
                    for btn in ("start_btn", "end_btn", "confirm_btn"):
                        print(f"  {btn}: {CFG['touch'][btn]}")
                        x = int(input(f"  {btn} X: ").strip())
                        y = int(input(f"  {btn} Y: ").strip())
                        CFG["touch"][btn] = {"x": x, "y": y}
                elif c == "0":
                    save_config(CFG)
                    print("[+] 配置已保存")
                    break
                save_config(CFG)
            except Exception as e:
                print(f"[-] 错误: {e}")

    def _show_config(self):
        print("\n── 当前配置 ──")
        print(json.dumps(CFG, ensure_ascii=False, indent=2))

    def take_screenshot(self, save_path=None):
        if save_path is None:
            save_path = os.path.join(SCRIPT_DIR, f"shot_{int(time.time())}.png")
        try:
            cmd = [ADB_PATH, "-s", self.device.serial, "shell", "screencap", "-p"]
            p = subprocess.run(cmd, capture_output=True, timeout=15)
            with open(save_path, "wb") as f:
                f.write(p.stdout)
            print(f"[+] 截图已保存: {save_path} ({len(p.stdout)} bytes)")
            return save_path
        except Exception as e:
            print(f"[-] 截图失败: {e}")
            return None

    def export_diagnostic(self, save_path="phone_diagnostic.txt"):
        print(f"\n[*] 导出诊断信息 → {save_path}")
        if not self.device:
            self.connect_device()
        self._check_environment()

        checks = [
            ("设备型号", "getprop ro.product.model"),
            ("设备品牌", "getprop ro.product.brand"),
            ("Android版本", "getprop ro.build.version.release"),
            ("SDK版本", "getprop ro.build.version.sdk"),
            ("SELinux", "getenforce"),
            ("Mock Location", "settings get secure mock_location"),
            ("Mock App", "settings get secure mock_location_app"),
            ("Location Mode", "settings get secure location_mode"),
            ("Location Providers", "cmd location providers list"),
            ("最后GPS位置", "dumpsys location | grep -i 'last location' -A5"),
            ("Fused状态", "dumpsys location | grep -i 'fused' -A3"),
            ("是否Root", "su -c 'id'"),
            ("全部权限(安全)", "settings list secure | grep -i mock"),
            ("乐跑包列表", "pm list packages | grep -iE 'lebao|lebu|lepao|sunshine|campusrun'"),
        ]

        with open(save_path, "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write("校园跑自动化 V2.0 — 手机诊断报告\n")
            f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"设备序列号: {self.device.serial}\n")
            f.write("=" * 60 + "\n\n")

            for label, cmd in checks:
                out, ok = self._exec(cmd, use_root=False)
                f.write(f"── {label} ({cmd}) ──\n")
                f.write(f"[{ 'OK' if ok else 'FAIL' }] {out if out else '(无输出)'}\n\n")
                print(f"  ✅ {label}: {out[:80] if out else '(无输出)'}")

        print(f"\n[+] 诊断文件已生成: {save_path}")
        print(f"[+] 文件大小: {os.path.getsize(save_path)} bytes")

    def stop(self):
        self.running = False
        if self.gps_thread and self.gps_thread.is_alive():
            self.gps_thread.join(timeout=3)
        self.cleanup_mock_location()
        print("[*] 已停止")


def main():
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    print("""
    ╔═══════════════════════════════════════════╗
    ║  ☀️ 步道乐跑自动化 V2.0 — 专项优化版      ║
    ║  对抗: 分段配速检测 / 轨迹分析 / 速度异常 ║
    ╚═══════════════════════════════════════════╝
    """)

    if not ensure_adb():
        input("按回车键退出...")
        return

    runner = CampusRunV2()

    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "test":
            runner.connect_device()
            runner.quick_test()
        elif mode == "run":
            try:
                runner.run(auto_touch=True)
            except KeyboardInterrupt:
                print("\n[!] 中断")
                runner.stop()
        elif mode == "gps":
            try:
                runner.run(auto_touch=False)
            except KeyboardInterrupt:
                print("\n[!] 中断")
                runner.stop()
        elif mode == "shell":
            runner.interactive_menu()
        else:
            print("用法:")
            print("  python 校园跑自动化V2.00.py test   - 快速测试GPS")
            print("  python 校园跑自动化V2.00.py run     - 完整自动跑步")
            print("  python 校园跑自动化V2.00.py gps     - 仅GPS轨迹")
            print("  python 校园跑自动化V2.00.py shell   - 交互菜单")
    else:
        runner.interactive_menu()


if __name__ == "__main__":
    main()