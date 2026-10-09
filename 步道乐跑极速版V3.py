#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步道乐跑 · 极速刷步数 V3.1 (修复版)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
修复点:
  1. 自动诊断 Mock 是否真的进了系统 LocationManager
  2. 自动点击乐跑【开始/结束/确认】按钮
  3. 多通道密集推送 (gps + fused + network + xml + broadcast)
  4. 乐跑被杀自动拉起 + 重推起点
  5. 屏幕坐标自动获取 (获取分辨率，按钮坐标按比例算)
  6. 跑完自动点结束 + 确认
"""

import math
import random
import subprocess
import sys
import os
import time
import json

try:
    from ppadb.client import Client as AdbClient
except ImportError:
    print("[!] 正在安装 pure-python-adb ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pure-python-adb"])
    from ppadb.client import Client as AdbClient

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADB_PATH = os.path.join(SCRIPT_DIR, "platform-tools", "adb.exe")
CFG_PATH = os.path.join(SCRIPT_DIR, "lepao_v3_cfg.json")

DEFAULT_START_LAT = 41.6872
DEFAULT_START_LNG = 123.6306
DEFAULT_SPEED_KMS = 0.003    # 真实跑步约 10 km/h = 0.0028 km/s
DEFAULT_STEP_LEN_M = 0.70
DEFAULT_INTERVAL = 0.5
DEFAULT_RUNTIME_SEC = 600    # 默认 10 分钟
DEFAULT_TRACK_RADIUS_M = 500

DEFAULT_CFG = {
    "lat": DEFAULT_START_LAT,
    "lng": DEFAULT_START_LNG,
    "speed_kms": DEFAULT_SPEED_KMS,
    "runtime_sec": DEFAULT_RUNTIME_SEC,
    "interval": DEFAULT_INTERVAL,
    "track_radius": DEFAULT_TRACK_RADIUS_M,
    "step_len": DEFAULT_STEP_LEN_M,
    "start_btn_ratio": (0.5, 0.90),   # 屏幕比例 x%, y%  (乐跑"开始"按钮)
    "end_btn_ratio":   (0.5, 0.90),   # 乐跑"结束"按钮
    "confirm_btn_ratio": (0.5, 0.70), # 结束后的"确认"弹窗
    "auto_start": True,
    "auto_stop": True,
}


def load_cfg():
    if os.path.exists(CFG_PATH):
        try:
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            cfg = DEFAULT_CFG.copy()
            cfg.update(saved)
            return cfg
        except Exception:
            pass
    return DEFAULT_CFG.copy()


def save_cfg(cfg):
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def haversine(lat1, lng1, lat2, lng2):
    R = 6371000
    p1 = math.radians(lat1); p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1); dl = math.radians(lng2 - lng1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def move_forward(lat, lng, distance_m, bearing_deg):
    R = 6371000
    br = math.radians(bearing_deg)
    p1 = math.radians(lat); l1 = math.radians(lng)
    p2 = math.asin(math.sin(p1)*math.cos(distance_m/R) +
                   math.cos(p1)*math.sin(distance_m/R)*math.cos(br))
    l2 = l1 + math.atan2(math.sin(br)*math.sin(distance_m/R)*math.cos(p1),
                         math.cos(distance_m/R)-math.sin(p1)*math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


# ─────────────────────────────────────────────────────────
class LepaoSpeedRun:
    def __init__(self, cfg):
        self.cfg = cfg
        self.speed_kms = float(cfg["speed_kms"])
        self.speed_mps = self.speed_kms * 1000.0
        self.runtime_sec = float(cfg["runtime_sec"])
        self.start_lat = float(cfg["lat"])
        self.start_lng = float(cfg["lng"])
        self.interval = float(cfg["interval"])
        self.step_len = float(cfg["step_len"])
        self.track_radius = float(cfg["track_radius"])

        self.device = None
        self._root = False
        self._mock_method = "none"
        self._lepao_pkg = None
        self._lepao_activity = None
        self._screen_w = 1080
        self._screen_h = 2400

        self.total_dist_m = 0.0
        self.total_steps = 0
        self.start_ts = None
        self.running = False

    # ─────────────── ADB 底层 ───────────────
    @staticmethod
    def ensure_adb():
        if not os.path.exists(ADB_PATH):
            print("[*] 首次运行，下载 ADB tools ...")
            import urllib.request, zipfile
            url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
            zip_path = os.path.join(SCRIPT_DIR, "platform-tools.zip")
            urllib.request.urlretrieve(url, zip_path)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(SCRIPT_DIR)
            os.remove(zip_path)
            print("[+] ADB 已就绪")
        subprocess.run([ADB_PATH, "start-server"], capture_output=True, timeout=10)

    def _raw(self, *args, timeout=15):
        cmd = [ADB_PATH, "-s", self.device.serial] + list(args)
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               encoding="utf-8", errors="replace")
            return p.stdout.strip(), p.stderr.strip(), p.returncode
        except subprocess.TimeoutExpired:
            return "", "TIMEOUT", -1

    def _sh(self, cmd, timeout=10, use_root=True):
        out, err, rc = self._raw("shell", cmd, timeout=timeout)
        if rc == 0:
            return out, True
        if use_root and self._root:
            out2, _, rc2 = self._raw("shell", f"su -c '{cmd}'", timeout=timeout)
            if rc2 == 0:
                return out2, True
        return (out or err), False

    # ─────────────── 连接 & 信息 ───────────────
    def connect(self):
        self.ensure_adb()
        print("\n" + "═" * 60)
        print("  【第 1 步】连接手机")
        print("═" * 60)

        client = AdbClient(host="127.0.0.1", port=5037)
        try:
            devs = [d for d in client.devices() if d.serial != "host"]
        except Exception:
            subprocess.run([ADB_PATH, "kill-server"], capture_output=True)
            subprocess.run([ADB_PATH, "start-server"], capture_output=True)
            time.sleep(2)
            devs = [d for d in AdbClient().devices() if d.serial != "host"]

        if not devs:
            print("[-] 没检测到手机")
            print("    数据线连接 + 开 USB 调试 + 手机弹窗点允许")
            return False

        if len(devs) > 1:
            for i, d in enumerate(devs):
                try:
                    m = d.shell("getprop ro.product.model").strip()
                except Exception:
                    m = "?"
                print(f"  [{i}] {m} ({d.serial})")
            sel = input("选择 [0]: ").strip()
            try:
                self.device = devs[int(sel)]
            except Exception:
                self.device = devs[0]
        else:
            self.device = devs[0]

        model, _ = self._sh("getprop ro.product.model", use_root=False)
        brand, _ = self._sh("getprop ro.product.brand", use_root=False)
        ver, _ = self._sh("getprop ro.build.version.release", use_root=False)
        sdk, _ = self._sh("getprop ro.build.version.sdk", use_root=False)

        # 获取分辨率
        size_out, _ = self._sh("wm size", use_root=False)
        if "Physical size:" in size_out:
            sz = size_out.split("Physical size:")[-1].strip()
            if "x" in sz:
                self._screen_w, self._screen_h = [int(x) for x in sz.split("x")]

        # Root 检测
        su_out, su_ok = self._sh("su -c 'id'", use_root=False)
        self._root = su_ok and "uid=0" in su_out

        print(f"\n  ✅ {brand} {model}")
        print(f"     Android {ver} (SDK {sdk})")
        print(f"     分辨率 {self._screen_w}×{self._screen_h}")
        print(f"     Root   : {'是 ✅' if self._root else '否 ⚠️  (部分Mock方式不可用)'}")
        return True

    # ─────────────── 乐跑 ───────────────
    def find_lepao(self):
        print("\n  [*] 扫描乐跑 APP ...")
        guesses = ["com.lebao.lepaozu", "com.lebu.lepaozu",
                   "com.sunshine.campusrun", "com.lebao.run", "com.lebu.run",
                   "com.lebao.campusrun"]
        all_pkgs, _ = self._sh("pm list packages", use_root=False)
        found = None
        for g in guesses:
            if g in all_pkgs:
                found = g; break
        if not found:
            for line in all_pkgs.split("\n"):
                if "package:" in line:
                    p = line.split(":")[1].strip()
                    low = p.lower()
                    if any(k in low for k in ("lebao","lebu","lepao","sunshine","campusrun")):
                        found = p; break

        self._lepao_pkg = found
        if found:
            resolve, _ = self._sh(
                f"cmd package resolve-activity --brief -a android.intent.action.MAIN "
                f"-c android.intent.category.LAUNCHER {found}", use_root=False)
            for line in resolve.split("\n"):
                if "/" in line and found in line:
                    self._lepao_activity = line.strip(); break
            if not self._lepao_activity:
                self._lepao_activity = f"{found}/.MainActivity"
            print(f"  📦 乐跑: {found}")
            self._grant_lepao_perms()
        else:
            print("  ⚠️  没找到乐跑（建议安装后重连，纯Mock也能用）")
        return found

    def _grant_lepao_perms(self):
        if not self._lepao_pkg: return
        perms = [
            "android.permission.ACCESS_FINE_LOCATION",
            "android.permission.ACCESS_COARSE_LOCATION",
            "android.permission.ACCESS_BACKGROUND_LOCATION",
            "android.permission.VIBRATE",
            "android.permission.FOREGROUND_SERVICE",
            "android.permission.WAKE_LOCK",
            "android.permission.ACTIVITY_RECOGNITION",
            "android.permission.BODY_SENSORS",
            "android.permission.POST_NOTIFICATIONS",
        ]
        for p in perms:
            self._sh(f"pm grant {self._lepao_pkg} {p}", use_root=False)
        self._sh(f"appops set {self._lepao_pkg} ACCESS_BACKGROUND_LOCATION allow", use_root=False)
        self._sh(f"appops set {self._lepao_pkg} ACTIVITY_RECOGNITION allow", use_root=False)

    def launch_lepao(self):
        if not self._lepao_pkg: return
        self._sh(f"am force-stop {self._lepao_pkg}", use_root=False)
        time.sleep(0.5)
        if self._lepao_activity:
            self._sh(f"am start -n {self._lepao_activity}", use_root=False)
        else:
            self._sh(f"monkey -p {self._lepao_pkg} -c android.intent.category.LAUNCHER 1", use_root=False)
        time.sleep(3)

    # ─────────────── 点击 ───────────────
    def _ratio_to_px(self, ratio):
        rx, ry = ratio
        return int(self._screen_w * rx), int(self._screen_h * ry)

    def tap(self, x, y):
        self._raw("shell", f"input tap {x} {y}")
        time.sleep(0.5)

    def tap_start_btn(self):
        x, y = self._ratio_to_px(self.cfg["start_btn_ratio"])
        print(f"  👆 点击【开始】 ({x},{y})")
        self.tap(x, y)

    def tap_end_btn(self):
        x, y = self._ratio_to_px(self.cfg["end_btn_ratio"])
        print(f"  👆 点击【结束】 ({x},{y})")
        self.tap(x, y)

    def tap_confirm_btn(self):
        x, y = self._ratio_to_px(self.cfg["confirm_btn_ratio"])
        print(f"  👆 点击【确认】 ({x},{y})")
        self.tap(x, y)

    # ─────────────── Mock 配置 ───────────────
    def setup_mock(self):
        print("\n" + "═" * 60)
        print("  【第 2 步】配置 Mock GPS")
        print("═" * 60)

        self._sh("settings put global development_settings_enabled 1", use_root=False)
        self._sh("settings put secure location_mode 3", use_root=False)
        self._sh("settings put secure location_providers_allowed gps,network", use_root=False)
        self._sh("settings put secure mock_location 1", use_root=False)

        if self._root:
            print("  [Root] 尝试无标记注入 ...")
            self._sh("su -c 'setenforce 0'")
            ok_gps = self._sh("su -c 'cmd location providers add-test-provider gps'")[1]
            self._sh("su -c 'cmd location providers set-test-provider-enabled gps true'")
            self._sh("su -c 'cmd location providers add-test-provider fused'")
            self._sh("su -c 'cmd location providers set-test-provider-enabled fused true'")
            self._sh("su -c 'cmd location providers add-test-provider network'")
            self._sh("su -c 'cmd location providers set-test-provider-enabled network true'")
            self._sh("su -c 'cmd location providers add-test-provider passive'")
            self._sh("su -c 'cmd location providers set-test-provider-enabled passive true'")
            if ok_gps:
                self._mock_method = "root_inject"
                print("  ✅ Root 无标记注入 (最强模式)")
            else:
                self._mock_method = "cmd_inject"
                print("  ✅ cmd location inject")
        else:
            ok = self._sh(
                "cmd location inject-location --provider gps "
                f"--location {self.start_lat},{self.start_lng} "
                f"--accuracy 3 --time {int(time.time()*1000)}",
                use_root=False)[1]
            if ok:
                self._mock_method = "cmd_inject"
                print("  ✅ cmd location inject (无Root)")
            else:
                self._mock_method = "broadcast"
                print("  ⚠️  仅 broadcast 方式 (可能部分APP收不到)")

        # 自检 - 看 dumpsys 能不能看到我们的 Mock
        return self._verify_mock()

    def _verify_mock(self):
        print("\n  [验证] 推送 Mock 起点 + 检查系统是否接收 ...")
        self.push_location(self.start_lat, self.start_lng,
                           bearing_deg=0.0, speed_mps=2.0)
        time.sleep(1.5)

        out, _ = self._sh(
            "dumpsys location | grep -i 'last location\\|last fused\\|mock\\|provider' -A2",
            use_root=False
        )
        ok = False
        if out:
            low = out.lower()
            if "last location" in low or "last fused" in low:
                if f"{self.start_lat:.4f}" in out or f"{self.start_lng:.4f}" in out:
                    ok = True

        if ok:
            print("  ✅ 系统 LocationManager 已接收 Mock")
            print(f"  {out[:200]}")
        else:
            print("  ❌ Mock 没进系统！乐跑肯定也收不到！")
            print(f"  dumpsys 片段: {out[:300] if out else '(空)'}")
            print("\n  ── 解决方案 ──")
            print("  ① 手机 → 设置 → 开发者选项 → 开【USB调试（安全设置）】")
            print("  ② 开发者选项 → 找到【Mock位置应用】→ 选一个 Fake GPS APP")
            print("  ③ 如果是小米/OPPO/Vivo，关闭【MIUI优化/ColorOS保护】")
            print("  ④ 有 Root 的话脚本会自动用更强方式")
            print("  ⑤ 实在不行 → 用 GPS Emulator (RosTeam) APP 手动推")
        return ok

    # ─────────────── 核心: 多通道密集推送 ───────────────
    def push_location(self, lat, lng, accuracy=4.0, bearing_deg=0.0, speed_mps=2.0):
        t = int(time.time() * 1000)
        la = f"{lat:.7f}"
        ln = f"{lng:.7f}"

        if self._mock_method == "root_inject":
            self._sh(f"su -c 'cmd location inject-location --provider gps "
                     f"--location {la},{ln} --accuracy {accuracy:.1f} --time {t}'")
            self._sh(f"su -c 'cmd location inject-location --provider fused "
                     f"--location {la},{ln} --accuracy {accuracy:.1f} --time {t}'")
            self._sh(f"su -c 'cmd location providers set-test-provider-location gps "
                     f"--location {la},{ln} --accuracy {accuracy:.1f} "
                     f"--altitude 50 --bearing {bearing_deg:.1f} "
                     f"--speed {speed_mps:.2f} --time {t}'")
            self._sh(f"su -c 'cmd location providers set-test-provider-location fused "
                     f"--location {la},{ln} --accuracy {accuracy:.1f} "
                     f"--altitude 50 --time {t}'")
            self._sh(f"su -c 'cmd location providers set-test-provider-location network "
                     f"--location {la},{ln} --accuracy {accuracy*2:.1f} "
                     f"--altitude 50 --time {t}'")
            self._sh(f"su -c 'am broadcast -a android.location.LOCATION_CHANGED "
                     f"--es latitude {la} --es longitude {ln} "
                     f"--es altitude 50 --ei accuracy {int(accuracy)} "
                     f"--ei provider gps --ei time {t} "
                     f"--ei speed {int(speed_mps*100)} --ei bearing {int(bearing_deg)}'")
            self._sh(f"su -c 'am broadcast -a android.location.LOCATION_CHANGED "
                     f"--es latitude {la} --es longitude {ln} "
                     f"--ei accuracy {int(accuracy)} --ei provider fused "
                     f"--ei time {t} --ei speed {int(speed_mps*100)} "
                     f"--ei bearing {int(bearing_deg)}'")
            if self._lepao_pkg:
                self._sh(f"su -c 'am broadcast -a android.location.LOCATION_CHANGED "
                         f"--es latitude {la} --es longitude {ln} "
                         f"--ei accuracy {int(accuracy)} --ei provider gps "
                         f"--ei time {t} -p {self._lepao_pkg}'")
                self._sh(f"su -c 'am broadcast -a android.location.LOCATION_CHANGED "
                         f"--es latitude {la} --es longitude {ln} "
                         f"--ei accuracy {int(accuracy)} --ei provider fused "
                         f"--ei time {t} -p {self._lepao_pkg}'")
            self._write_gps_xml(lat, lng, accuracy, bearing_deg, speed_mps, t)

        elif self._mock_method == "cmd_inject":
            self._sh(f"cmd location inject-location --provider gps "
                     f"--location {la},{ln} --accuracy {accuracy:.1f} --time {t}",
                     use_root=False)
            self._sh(f"cmd location inject-location --provider fused "
                     f"--location {la},{ln} --accuracy {accuracy:.1f} --time {t}",
                     use_root=False)
            self._sh(f"am broadcast -a android.location.LOCATION_CHANGED "
                     f"--es latitude {la} --es longitude {ln} "
                     f"--ei accuracy {int(accuracy)} --ei provider gps --ei time {t}",
                     use_root=False)
            if self._lepao_pkg:
                self._sh(f"am broadcast -a android.location.LOCATION_CHANGED "
                         f"--es latitude {la} --es longitude {ln} "
                         f"--ei accuracy {int(accuracy)} --ei provider fused "
                         f"--ei time {t} -p {self._lepao_pkg}", use_root=False)

        else:
            self._sh(f"am broadcast -a android.location.LOCATION_CHANGED "
                     f"--es latitude {la} --es longitude {ln} "
                     f"--ei accuracy {int(accuracy)} --ei provider gps --ei time {t}",
                     use_root=False)

    def _write_gps_xml(self, lat, lng, accuracy, bearing, speed, t):
        if not self._root: return
        n = random.randint(4, 10)
        xml = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<gps>'
            '<provider name="gps">'
            f'<location latitude="{lat}" longitude="{lng}" altitude="50" '
            f'accuracy="{accuracy}" speed="{speed}" bearing="{bearing}" time="{t}"/>'
            f'<status satellites="{n}" status="3"/>'
            '</provider>'
            '</gps>'
        )
        try:
            self._sh(f"su -c 'mkdir -p /data/system/location'")
            self._sh(f"su -c 'echo \\'{xml}\\' > /data/system/location/gps.xml'")
            self._sh(f"su -c 'chmod 644 /data/system/location/gps.xml'")
            self._sh(f"su -c 'chown root.root /data/system/location/gps.xml'")
        except Exception:
            pass

    # ─────────────── 清理 ───────────────
    def cleanup(self):
        print("\n  [*] 清理 Mock ...")
        if self._root:
            for cmd in [
                "su -c 'cmd location providers set-test-provider-enabled gps false'",
                "su -c 'cmd location providers remove-test-provider gps'",
                "su -c 'cmd location providers set-test-provider-enabled fused false'",
                "su -c 'cmd location providers remove-test-provider fused'",
                "su -c 'cmd location providers set-test-provider-enabled network false'",
                "su -c 'cmd location providers remove-test-provider network'",
                "su -c 'settings put secure mock_location 0'",
                "su -c 'settings put secure mock_location_app null'",
                "su -c 'am broadcast -a android.location.PROVIDERS_CHANGED'",
            ]:
                self._sh(cmd)
        else:
            self._sh("settings put secure mock_location 0", use_root=False)
            self._sh("settings put secure mock_location_app null", use_root=False)

    # ─────────────── 主循环 ───────────────
    def run(self):
        print("\n" + "═" * 60)
        print("  🏃 步道乐跑 · 极速刷步数 V3.1")
        print("═" * 60)
        spd_kmh = self.speed_kms * 3600
        print(f"  速度        : {self.speed_kms:.6f} km/s  ({spd_kmh:.1f} km/h)")
        print(f"  GPS推送间隔 : {self.interval} 秒")
        print(f"  总时长      : {self.runtime_sec} 秒")
        total_km_theory = self.speed_kms * self.runtime_sec
        print(f"  预计公里数  : {total_km_theory:.2f} km")
        print(f"  预计步数    : {int(total_km_theory*1000 / self.step_len):,} 步")
        print(f"  轨迹半径    : {self.track_radius} 米")
        print("═" * 60)

        # 起跑前密集推送起点
        print("\n[*] 密集推送起点 (20次) ...")
        for _ in range(20):
            self.push_location(self.start_lat, self.start_lng,
                               accuracy=random.gauss(4, 1))
            time.sleep(0.08)

        # 自动点击开始
        if self.cfg["auto_start"] and self._lepao_pkg:
            print("\n[*] 3 秒后自动点击乐跑【开始】按钮 ...")
            for i in [3, 2, 1]:
                print(f"     {i}..."); time.sleep(1)
            self.tap_start_btn()
            time.sleep(1.5)
            # 点完再推一次
            for _ in range(5):
                self.push_location(self.start_lat, self.start_lng, accuracy=3.0)
                time.sleep(0.1)

        lat, lng = self.start_lat, self.start_lng
        self.start_ts = time.time()
        self.running = True

        accumulated_angle = 0.0
        last_check = 0

        try:
            while self.running:
                elapsed = time.time() - self.start_ts
                if elapsed >= self.runtime_sec:
                    print(f"\n[*] 时长到了 ({elapsed:.1f}s)")
                    break

                # 前进距离
                dist_step = self.speed_mps * self.interval
                self.total_dist_m += dist_step

                # 圆周运动
                angle_delta = dist_step / max(self.track_radius, 10)
                accumulated_angle += angle_delta
                cur_bearing = (math.degrees(accumulated_angle) + 90) % 360

                lat, lng = move_forward(lat, lng, dist_step, cur_bearing)
                lat += random.gauss(0, 0.00003)
                lng += random.gauss(0, 0.00003)

                self.total_steps += int(dist_step / self.step_len)

                self.push_location(
                    lat, lng,
                    accuracy=random.gauss(4, 1.5),
                    bearing_deg=cur_bearing,
                    speed_mps=self.speed_mps
                )

                # 状态栏
                km = self.total_dist_m / 1000
                eta = self.runtime_sec - elapsed
                spd_disp = self.speed_kms
                if spd_disp >= 1:
                    spd_str = f"{spd_disp:,.1f} km/s"
                elif spd_disp >= 0.001:
                    spd_str = f"{spd_disp*1000:.3f} m/s"
                else:
                    spd_str = f"{spd_disp*3600:.2f} km/h"
                print(f"\r  🏃 {km:,.2f}km | {self.total_steps:,}步 | "
                      f"速度 {spd_str} | 剩 {eta:.0f}s   ", end="", flush=True)

                # 乐跑存活性检查
                if self._lepao_pkg and elapsed - last_check > 20:
                    last_check = elapsed
                    st, _ = self._sh(
                        f"dumpsys activity processes | grep {self._lepao_pkg}",
                        use_root=False
                    )
                    if not st:
                        print("\n  [!] 乐跑被杀，重新拉起 + 推起点 ...")
                        self.launch_lepao()
                        for _ in range(10):
                            self.push_location(lat, lng, accuracy=3.0)
                            time.sleep(0.1)
                        if self.cfg["auto_start"]:
                            self.tap_start_btn()
                            time.sleep(1)

                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n\n[!] 手动中断")

        self.running = False
        print()

        # 自动结束
        if self.cfg["auto_stop"] and self._lepao_pkg:
            print("\n[*] 2 秒后自动点击【结束】...")
            time.sleep(2)
            self.tap_end_btn()
            time.sleep(2)
            self.tap_confirm_btn()
            time.sleep(1)

        self._print_summary(time.time() - (self.start_ts or time.time()))

    def _print_summary(self, elapsed):
        print("\n" + "═" * 60)
        print("  📊 跑步数据")
        print("═" * 60)
        km = self.total_dist_m / 1000
        print(f"  实际总距离  : {km:.4f} km")
        print(f"  实际总步数  : {self.total_steps:,} 步")
        print(f"  实际用时    : {elapsed:.2f} 秒")
        if elapsed > 0:
            avg_kmh = km / (elapsed / 3600)
            print(f"  平均速度    : {avg_kmh:.2f} km/h")
        print(f"  轨迹半径    : {self.track_radius} m")
        print(f"  Mock方式    : {self._mock_method}")
        print("═" * 60)


# ─────────────────────────────────────────────────────────
def set_default_btns(runner):
    w = runner._screen_w
    h = runner._screen_h
    # 尝试几个常见乐跑版本的按钮坐标（按屏幕比例）
    print(f"\n  屏幕 {w}×{h}，尝试自动定位按钮 ...")
    print("  如果坐标不对，在菜单 8 里手动调整比例")
    return


# ─────────────────────────────────────────────────────────
def interactive():
    cfg = load_cfg()
    print("\n" + "═" * 60)
    print("  🏃 步道乐跑 · 极速刷步数 V3.1 (修复版)")
    print("═" * 60)

    runner = LepaoSpeedRun(cfg)
    if not runner.connect():
        return

    runner.find_lepao()
    runner.launch_lepao()
    ok = runner.setup_mock()

    if not ok:
        print("\n" + "─" * 60)
        print("  ⚠️  Mock 没通过验证，先别跑！")
        print("  请修复好 Mock 后再继续，否则乐跑不会变！")
        print("─" * 60)
        fix = input("  修复好了吗？ (y=继续 / n=退出): ").strip().lower()
        if fix != "y":
            runner.cleanup()
            return
        runner.launch_lepao()
        runner.setup_mock()

    # 存默认按钮
    set_default_btns(runner)

    while True:
        print("\n" + "─" * 60)
        kmh = runner.cfg["speed_kms"] * 3600
        print(f"  当前: 速度 {runner.cfg['speed_kms']:.6f} km/s ({kmh:.1f} km/h) | "
              f"{runner.cfg['runtime_sec']:.0f}s | "
              f"半径 {runner.cfg['track_radius']}m")
        print("─" * 60)
        print("  1. 🏃 开始跑（当前参数）")
        print("  2. 🚀 极速三档  100,000 km/s")
        print("  3. 🛸 极速二档   10,000 km/s")
        print("  4. ⚡ 极速一档    1,000 km/s")
        print("  5. 🏃 真实跑步    10 km/h (0.0028 km/s)")
        print("  6. 🧪 仅推起点坐标")
        print("  7. 📸 截屏看看屏幕上有啥")
        print("  8. ⚙️  修改参数/按钮坐标")
        print("  0. ❌ 退出")
        print("─" * 60)

        choice = input("选择 > ").strip()

        if choice == "0":
            runner.cleanup()
            print("👋 再见"); break

        elif choice in ("2","3","4","5"):
            if choice == "2": runner.cfg["speed_kms"] = 100000.0
            elif choice == "3": runner.cfg["speed_kms"] = 10000.0
            elif choice == "4": runner.cfg["speed_kms"] = 1000.0
            elif choice == "5": runner.cfg["speed_kms"] = 10.0/3600  # 10 km/h
            runner.speed_kms = runner.cfg["speed_kms"]
            runner.speed_mps = runner.speed_kms * 1000.0
            save_cfg(runner.cfg)
            runner.run()
            runner.launch_lepao()
            runner.setup_mock()

        elif choice == "1":
            runner.run()
            runner.launch_lepao()
            runner.setup_mock()

        elif choice == "6":
            print(f"  推送 20 次起点 ({runner.start_lat}, {runner.start_lng}) ...")
            for _ in range(20):
                runner.push_location(runner.start_lat, runner.start_lng,
                                     accuracy=random.gauss(4, 1))
                time.sleep(0.08)
            print("  ✅ 推送完成，手机地图应该能看到位置移动")

        elif choice == "7":
            path = os.path.join(SCRIPT_DIR, "lepao_screen.png")
            runner._raw("shell", "screencap -p /sdcard/lepao_screen.png")
            runner._raw("pull", "/sdcard/lepao_screen.png", path)
            print(f"  ✅ 截屏已保存: {path}")
            os.startfile(path)

        elif choice == "8":
            cfg_m = runner.cfg.copy()
            print("\n  ── 修改参数 ──")
            for key, (prompt, typ) in [
                ("lat",   ("起点纬度 [{}]: ", float)),
                ("lng",   ("起点经度 [{}]: ", float)),
                ("speed_kms", ("速度 km/s [{}]: ", float)),
                ("runtime_sec", ("总时长 秒 [{}]: ", float)),
                ("track_radius", ("绕圈半径 米 [{}]: ", float)),
                ("interval", ("GPS推送间隔 秒 [{}]: ", float)),
                ("start_btn_ratio", ("开始按钮坐标 比例 (x,y) [{}]: ", str)),
                ("end_btn_ratio", ("结束按钮坐标 比例 (x,y) [{}]: ", str)),
                ("confirm_btn_ratio", ("确认按钮坐标 比例 (x,y) [{}]: ", str)),
                ("auto_start", ("自动点开始 (y/n) [{}]: ", str)),
                ("auto_stop",  ("自动点结束 (y/n) [{}]: ", str)),
            ]:
                cur = cfg_m[key]
                inp = input(f"    {prompt.format(cur)} ").strip()
                if not inp: continue
                try:
                    if key in ("start_btn_ratio","end_btn_ratio","confirm_btn_ratio"):
                        parts = inp.replace("(","").replace(")","").split(",")
                        cfg_m[key] = (float(parts[0]), float(parts[1]))
                    elif key in ("auto_start","auto_stop"):
                        cfg_m[key] = inp.lower() in ("y","1","true")
                    else:
                        cfg_m[key] = typ(inp)
                except Exception as e:
                    print(f"    输入错误: {e}")
            runner.cfg = cfg_m
            runner.speed_kms = float(cfg_m["speed_kms"])
            runner.speed_mps = runner.speed_kms * 1000.0
            runner.start_lat = float(cfg_m["lat"])
            runner.start_lng = float(cfg_m["lng"])
            save_cfg(cfg_m)
            print("  ✅ 已保存")


# ─────────────────────────────────────────────────────────
def main():
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print("""
  步道乐跑 V3.1  使用说明
  ─────────────────────
  交互菜单:
    python 步道乐跑极速版V3.py

  命令行:
    python 步道乐跑极速版V3.py --speed 0.003 --time 600 --lat 41.68 --lng 123.63
    python 步道乐跑极速版V3.py --speed 100000 --time 60
        """)
        return

    args = {}
    i = 1
    while i < len(sys.argv):
        k = sys.argv[i].lstrip("-")
        if i + 1 < len(sys.argv):
            args[k] = sys.argv[i+1]; i += 2
        else:
            args[k] = True; i += 1

    if args:
        cfg = load_cfg()
        if "speed" in args: cfg["speed_kms"] = float(args["speed"])
        if "time" in args: cfg["runtime_sec"] = float(args["time"])
        if "lat" in args: cfg["lat"] = float(args["lat"])
        if "lng" in args: cfg["lng"] = float(args["lng"])
        runner = LepaoSpeedRun(cfg)
        try:
            if runner.connect():
                runner.find_lepao()
                runner.launch_lepao()
                runner.setup_mock()
                runner.run()
        finally:
            runner.cleanup()
    else:
        try:
            interactive()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 退出")


if __name__ == "__main__":
    main()