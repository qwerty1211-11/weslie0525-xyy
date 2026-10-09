#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步道乐跑自动刷 V6 🛡️防检测版 (GPS直接注入, 连续轨迹)
  - cmd location providers set-test-provider-location 高频注入
  - 每秒 10 次注入 (gps + network + fused = 30次/s)
  - 每次注入后重新 enable provider (对抗乐跑反检测循环)
  - 人类跑步速度曲线 + GPS噪声
  - 反模拟器 / 反Root
  - 自动杀掉 Ninja Fake GPS / 影梭 等冲突应用
  
前提:
  1. 手机已装步道乐跑
  2. USB 调试已开启
  3. 首次运行会给 shell 授予 MOCK_LOCATION 权限 (一次性)
  4. 点开始后在手机上点乐跑「开始跑步」
"""

import subprocess, sys, time, math, os, re, random, threading
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEVICE = "10AD3P0298003QF"
LEPAO_PKG = "com.lptiyu.tanke"
SHELL_UID = "2000"

LAT = 41.6872
LNG = 123.6306
STEP_LEN = 0.70
INJECT_PER_SEC = 10  # 每秒注入次数 (对抗乐跑反检测, 高频竞态)

class ADC:
    SPEED_FLUCTUATION = 0.22
    GPS_JITTER_M = 5.0
    PAUSE_CHANCE = 0.025
    PAUSE_MIN_SEC = 2
    PAUSE_MAX_SEC = 10
    PAUSE_LONG_CHANCE = 0.005
    PAUSE_LONG_MIN = 20
    PAUSE_LONG_MAX = 60
    HUMAN_RUN_FREQ = 3.5
    REAL_RUN_HOURS = list(range(17, 23)) + list(range(6, 9))

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

def cmd_loc(*args, timeout=5):
    """直接调用 cmd location providers (不经过 sh -c, 否则会报 'No service specified')"""
    full = ["shell", "cmd", "location", "providers"] + list(args)
    return adb(*full, timeout=timeout)

def pkg_exists(pkg):
    out, _, _ = adb("shell", "pm", "list", "packages", pkg)
    return pkg in out

def kill_conflict_apps(log=None):
    log = log or print
    log("\n🛡️ [冲突清理] 杀掉 Ninja Fake GPS / 影梭 等...")
    conflicts = [
        "com.ninja.toolkit.pulse.fake.gps.pro",
        "com.vphone.launcher",
        "com.nick.apps.locationspoofer",
        "com.kuxun.fakegps",
        "com.lerist.fakelocation",
        "com.pocketpcs.moklocation",
    ]
    for pkg in conflicts:
        out, _, _ = adb("shell", "am", "force-stop", pkg)
    adb("shell", "settings", "delete", "secure", "mock_location_app")
    log("  ✅ 冲突应用已清理")

def launch(pkg, activity=None):
    adb("shell", "am", "force-stop", pkg)
    time.sleep(0.3)
    if activity:
        adb("shell", "am", "start", "-n", f"{pkg}/{activity}")
    else:
        adb("shell", "monkey", "-p", pkg,
            "-c", "android.intent.category.LAUNCHER", "1")

# ============================================================
#  🌟 核心: GPS 直接注入
# ============================================================
R_EARTH = 6371000.0

def _offset(lat, lng, dy_m, dx_m):
    dlat = dy_m / R_EARTH * 180.0 / math.pi
    dlng = dx_m / (R_EARTH * math.cos(math.radians(lat))) * 180.0 / math.pi
    return lat + dlat, lng + dlng

def _noise(lat, lng):
    r = random.gauss(0, ADC.GPS_JITTER_M / 3)
    if random.random() < 0.05:
        r *= 3.5
    ang = random.uniform(0, 2 * math.pi)
    return _offset(lat, lng, r * math.sin(ang), r * math.cos(ang))

def inject_gps(lat, lng, accuracy=5.0, log=None):
    lat_f = f"{lat:.7f}"
    lng_f = f"{lng:.7f}"
    now_ms = str(int(time.time() * 1000))
    
    for prov in ["gps", "network", "fused"]:
        cmd_loc("set-test-provider-location", prov,
                "--location", f"{lat_f},{lng_f}",
                "--accuracy", f"{accuracy + (3 if prov == 'network' else 0):.1f}",
                "--time", now_ms, timeout=3)
        cmd_loc("set-test-provider-enabled", prov, "true", timeout=3)

def remove_all_test_providers(log=None):
    for prov in ["gps", "network", "fused"]:
        cmd_loc("set-test-provider-enabled", prov, "false", timeout=3)
        cmd_loc("remove-test-provider", prov, timeout=3)
    if log:
        log("  ✅ test provider 已清理")

def setup_gps_injection(log=None):
    log = log or print
    log("\n🛡️ [GPS注入] 授予 shell MOCK_LOCATION...")
    adb("shell", "appops", "set", SHELL_UID, "MOCK_LOCATION", "allow")
    adb("shell", "appops", "set", "shell", "MOCK_LOCATION", "allow")
    
    log("\n🛡️ [GPS注入] 清理旧 test provider...")
    remove_all_test_providers(log)
    
    log("\n🛡️ [GPS注入] 添加 test provider (gps + network + fused)...")
    all_ok = True
    for name, flags in [
        ("gps", ["--supportsAltitude", "--supportsSpeed", "--supportsBearing", "--requiresSatellite"]),
        ("network", ["--requiresNetwork"]),
        ("fused", ["--supportsAltitude", "--supportsSpeed", "--supportsBearing"]),
    ]:
        out, _, rc = cmd_loc("add-test-provider", name, *flags, timeout=5)
        if rc != 0:
            log(f"  ⚠ add {name}: {out[:80]}")
            all_ok = False
        else:
            log(f"  ✅ add-test-provider {name}")
        
        out2, _, rc2 = cmd_loc("set-test-provider-enabled", name, "true", timeout=5)
        if rc2 != 0:
            log(f"  ⚠ enable {name}: {out2[:80]}")
            all_ok = False
        else:
            log(f"  ✅ {name} enabled")
    
    log("\n🛡️ [GPS注入] 初始注入验证...")
    inject_gps(LAT, LNG, accuracy=4.0, log=log)
    time.sleep(0.8)
    out, _, _ = adb("shell", "dumpsys", "location", timeout=8)
    mock_lines = [l for l in out.splitlines() if "mock" in l.lower() or "M:" in l]
    if mock_lines:
        log("  ✅ 验证成功: 系统读到 mock location")
        for l in mock_lines[:4]:
            if "M:" in l and "Location[" in l:
                m = re.search(r'M:(-?\d+),(-?\d+)', l)
                if m:
                    log(f"  📍 ({int(m.group(1))/1e7:.5f}, {int(m.group(2))/1e7:.5f})")
    else:
        log(f"  ⚠ 未检测到 mock (可能首次有延迟), 继续运行...")
    return all_ok


# ============================================================
#  反检测
# ============================================================
def anti_emulator(log=print):
    log("\n🛡️ [反模拟器] 检查...")
    props = {"ro.product.model": "V2230A", "ro.product.brand": "vivo",
             "ro.product.device": "pd2230a", "ro.hardware": "mt6891"}
    out, _, _ = adb("shell", "getprop", "ro.hardware")
    bad = ["goldfish", "qemu", "ranchu", "sdk", "emulator", "bluestacks", "nox", "mumu"]
    if any(k in out.lower() for k in bad):
        for k, v in props.items():
            adb("shell", "setprop", k, v)
        log(f"  ✅ 已伪装 vivo V2230A (原: {out.strip()})")
    else:
        log(f"  ✅ 硬件正常: {out.strip()}")

def anti_root(log=print):
    log("\n🛡️ [反Root] 检查...")
    paths = ["/system/bin/su", "/system/xbin/su", "/sbin/su",
             "/data/adb/magisk", "/system/bin/.magisk"]
    found = []
    for p in paths:
        o, _, _ = adb("shell", "ls", p)
        if o and "No such file" not in o and "cannot access" not in o:
            found.append(p)
    if found:
        log(f"  ⚠ Root痕迹: {len(found)}处")
    else:
        log("  ✅ Root干净")

def full_antidetect(log=print):
    log("=" * 60)
    log("  🛡️ 防检测 + GPS直接注入 V6")
    log(f"  📡 注入频率 {INJECT_PER_SEC}次/s x 3prov = {INJECT_PER_SEC*30}次/s | 3.5Hz人类频率")
    log("=" * 60)
    kill_conflict_apps(log)
    anti_emulator(log)
    anti_root(log)


# ============================================================
#  速度曲线
# ============================================================
def human_speed(base, elapsed, total):
    w = total * 0.1
    f = total * 0.8
    if elapsed < w:
        p = elapsed / w
        phase = base * (0.4 + 0.6 * p)
    elif elapsed < f:
        phase = base
    else:
        fatigue = (elapsed - f) / (total - f)
        phase = base * (1 - 0.15 * fatigue)
    breath = math.sin(2 * math.pi * 0.15 * elapsed) * ADC.SPEED_FLUCTUATION * 0.5
    noise = (random.random() - 0.5) * ADC.SPEED_FLUCTUATION
    final = phase * (1 + breath + noise)
    return max(phase * 0.6, final)


def check_lptiyu_running():
    """检查乐跑是否在跑步中 (只看当前活跃的 location request, 排除历史记录)"""
    out, _, _ = adb("shell", "dumpsys", "location", timeout=6)
    for l in out.splitlines():
        s = l.strip()
        if "lptiyu" not in s.lower() or "ProviderRequest[" not in s or "@+" not in s:
            continue
        if re.match(r'^\d{2}-\d{2} ', s):
            continue
        if "PASSIVE" in s or "OFF" in s:
            continue
        m = re.search(r'@\+([\dms]+)', s)
        if not m:
            continue
        interval_str = m.group(1)
        total_ms = 0
        if 'ms' in interval_str:
            mm = re.search(r'(\d+)ms', interval_str)
            if mm:
                total_ms += int(mm.group(1))
        else:
            if 'h' in interval_str:
                h = re.search(r'(\d+)h', interval_str)
                if h:
                    total_ms += int(h.group(1)) * 3600000
            mmin = re.search(r'(\d+)m(?!s)', interval_str)
            if mmin:
                total_ms += int(mmin.group(1)) * 60000
            ss = re.search(r'(\d+)s', interval_str)
            if ss:
                total_ms += int(ss.group(1)) * 1000
        if 0 < total_ms < 30000:
            return True
    return False

def get_lptiyu_counter():
    """读取乐跑收到的 location 总数"""
    out, _, _ = adb("shell", "dumpsys", "location", timeout=6)
    max_cnt = 0
    for l in out.splitlines():
        if "lptiyu" in l.lower() and "locations = " in l:
            m = re.search(r'locations = (\d+)', l)
            if m:
                max_cnt = max(max_cnt, int(m.group(1)))
    return max_cnt


# ============================================================
#  RunEngine - 高频 GPS 注入 + 乐跑状态监控
# ============================================================
class RunEngine:
    def __init__(self, log_cb=None, stop_event=None):
        self.log = log_cb or print
        self.stop_event = stop_event or threading.Event()
    
    def _wait_for_lptiyu_run(self):
        """等待用户在手机上点『开始跑步』"""
        self.log("\n" + "=" * 50)
        self.log("📱 请在手机上打开乐跑 → 点『开始跑步』")
        self.log("   检测到乐跑请求高频定位后自动开始注入...")
        self.log("=" * 50)
        
        waited = 0
        while not self.stop_event.is_set():
            out, _, _ = adb("shell", "dumpsys", "location", timeout=6)
            found_interval = None
            for l in out.splitlines():
                s = l.strip()
                if "lptiyu" not in s.lower() or "ProviderRequest[" not in s or "@+" not in s:
                    continue
                if re.match(r'^\d{2}-\d{2} ', s):
                    continue
                if "PASSIVE" in s or "OFF" in s:
                    continue
                m = re.search(r'@\+([\dms]+)', s)
                if not m:
                    continue
                s2 = m.group(1)
                total_ms = 0
                if 'ms' in s2:
                    mm = re.search(r'(\d+)ms', s2)
                    if mm:
                        total_ms += int(mm.group(1))
                else:
                    ss = re.search(r'(\d+)s', s2)
                    if ss:
                        total_ms += int(ss.group(1)) * 1000
                    mm = re.search(r'(\d+)m(?!s)', s2)
                    if mm:
                        total_ms += int(mm.group(1)) * 60000
                if 0 < total_ms < 30000:
                    found_interval = total_ms
                    break
            
            if found_interval:
                self.log(f"  ✅ 乐跑已开始跑步! (interval={found_interval}ms, 等待 {waited}s)")
                return True
            
            time.sleep(2)
            waited += 2
            if waited % 10 == 0:
                self.log(f"  ⏳ 等待乐跑点开始跑步... ({waited}s)")
        return False
    
    def _counter_monitor(self, prev_cnt, label=""):
        """监控乐跑 counter 是否在增长"""
        cnt = get_lptiyu_counter()
        delta = cnt - prev_cnt
        if delta > 0:
            self.log(f"  📊 乐跑已收到 {delta} 个新位置! (累计 {cnt}) {label}")
            return cnt, True
        return cnt, False
    
    def run_circle(self, speed_kmh=10, radius_m=300, duration_sec=600):
        self.log("")
        self.log(f"🏃 圆周刷跑 | {speed_kmh} km/h | r={radius_m}m | {duration_sec}s")
        
        setup_gps_injection(log=self.log)
        time.sleep(0.5)
        
        if not self._wait_for_lptiyu_run():
            self.log("⏹ 已取消")
            return
        
        lat, lng = LAT, LNG
        start_time = time.time()
        pause_log = []
        prev_counter = get_lptiyu_counter()
        self.log(f"  📍 乐跑起始 location count = {prev_counter}")
        self.log(f"  注入频率 {INJECT_PER_SEC}次/s x 3prov = {INJECT_PER_SEC*3}次/s")
        
        monitor_interval = 3
        last_monitor = 0
        
        while not self.stop_event.is_set():
            elapsed = time.time() - start_time
            if elapsed >= duration_sec:
                break
            
            cur_speed = human_speed(speed_kmh, elapsed, duration_sec)
            
            for _ in range(INJECT_PER_SEC):
                if self.stop_event.is_set():
                    break
                if time.time() - start_time >= duration_sec:
                    break
                
                lat_speed_ms = cur_speed * 1000 / 3600
                angular = lat_speed_ms / radius_m
                angle = angular * elapsed + math.radians(90)
                dx_m = math.cos(angle) * lat_speed_ms / INJECT_PER_SEC
                dy_m = math.sin(angle) * lat_speed_ms / INJECT_PER_SEC
                
                lat, lng = _offset(lat, lng, dy_m, dx_m)
                lat, lng = _noise(lat, lng)
                if random.random() < 0.03:
                    lat, lng = _noise(lat, lng)
                
                inject_gps(lat, lng, accuracy=random.uniform(3.5, 8.0))
                time.sleep(1.0 / INJECT_PER_SEC)
            
            elapsed_int = int(time.time() - start_time)
            
            if elapsed_int - last_monitor >= monitor_interval:
                cnt = get_lptiyu_counter()
                delta = cnt - prev_counter
                prev_counter = cnt
                if delta > 0:
                    self.log(f"  ✅ 乐跑+{delta} locs | 累计 {cnt} | 📍({lat:.5f},{lng:.5f}) | ⏱{elapsed_int}s")
                else:
                    self.log(f"  ⚠ 乐跑未接收 location | counter={cnt} | 检查手机是否在跑步界面")
                last_monitor = elapsed_int
            
            if elapsed_int > 20 and random.random() < ADC.PAUSE_CHANCE:
                if random.random() < ADC.PAUSE_LONG_CHANCE:
                    pd = random.randint(ADC.PAUSE_LONG_MIN, ADC.PAUSE_LONG_MAX)
                    self.log(f"  🛑 长暂停 {pd}s")
                else:
                    pd = random.randint(ADC.PAUSE_MIN_SEC, ADC.PAUSE_MAX_SEC)
                    self.log(f"  🛑 暂停 {pd}s")
                pause_log.append(pd)
                for _ in range(pd):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)
                inject_gps(lat, lng, accuracy=4.0)
            
            # 状态
            if elapsed % 15 == 0 and elapsed > 0:
                dist = (speed_kmh * 1000 / 3600) * elapsed
                steps = int(dist / STEP_LEN)
                self.log(f"  ⏱ {elapsed}s | 步数≈{steps} | {dist:.0f}m | {cur_speed:.1f}km/h | 📍({lat:.5f},{lng:.5f})")
        
        elapsed = int(time.time() - start_time)
        dist_total = speed_kmh * elapsed / 3600
        steps = int(dist_total * 1000 / STEP_LEN)
        self.log(f"\n  🏁 完成! {elapsed}s | 步数≈{steps} | 距离≈{dist_total:.2f}km")
        if pause_log:
            self.log(f"  ℹ 暂停 {len(pause_log)}次 累计{sum(pause_log)}s")
    
    def run_straight(self, speed_kmh=10, direction="forward", duration_sec=600):
        self.log("")
        self.log(f"🏃 直线刷跑 | {speed_kmh} km/h | {duration_sec}s | 方向:{direction}")
        
        setup_gps_injection(log=self.log)
        time.sleep(0.5)
        
        if not self._wait_for_lptiyu_run():
            self.log("⏹ 已取消")
            return
        
        lat, lng = LAT, LNG
        start_time = time.time()
        pause_log = []
        prev_counter = get_lptiyu_counter()
        self.log(f"  📍 乐跑起始 location count = {prev_counter}")
        self.log(f"  注入频率 {INJECT_PER_SEC}次/s x 3prov = {INJECT_PER_SEC*3}次/s")
        
        signs = {"forward": (1, 0), "back": (-1, 0), "right": (0, 1), "left": (0, -1)}
        ds, ls = signs.get(direction, (1, 0))
        last_monitor = 0
        
        while not self.stop_event.is_set():
            elapsed = time.time() - start_time
            if elapsed >= duration_sec:
                break
            
            cur_speed = human_speed(speed_kmh, elapsed, duration_sec)
            lat_speed_ms = cur_speed * 1000 / 3600
            
            for _ in range(INJECT_PER_SEC):
                if self.stop_event.is_set():
                    break
                if time.time() - start_time >= duration_sec:
                    break
                
                dx_m = ls * lat_speed_ms / INJECT_PER_SEC + random.uniform(-0.3, 0.3)
                dy_m = ds * lat_speed_ms / INJECT_PER_SEC + random.uniform(-0.3, 0.3)
                
                lat, lng = _offset(lat, lng, dy_m, dx_m)
                lat, lng = _noise(lat, lng)
                
                inject_gps(lat, lng, accuracy=random.uniform(3.5, 8.0))
                time.sleep(1.0 / INJECT_PER_SEC)
            
            elapsed_int = int(time.time() - start_time)
            
            if elapsed_int - last_monitor >= 3:
                cnt = get_lptiyu_counter()
                delta = cnt - prev_counter
                prev_counter = cnt
                if delta > 0:
                    self.log(f"  ✅ 乐跑+{delta} locs | 累计 {cnt} | 📍({lat:.5f},{lng:.5f}) | ⏱{elapsed_int}s")
                else:
                    self.log(f"  ⚠ 乐跑未接收 location | counter={cnt} | 检查手机是否在跑步界面")
                last_monitor = elapsed_int
            
            if elapsed_int > 20 and random.random() < ADC.PAUSE_CHANCE:
                pd = random.randint(ADC.PAUSE_MIN_SEC, ADC.PAUSE_MAX_SEC)
                self.log(f"  🛑 暂停 {pd}s")
                pause_log.append(pd)
                for _ in range(pd):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)
                inject_gps(lat, lng, accuracy=4.0)
            
            if elapsed % 15 == 0 and elapsed > 0:
                dist = (speed_kmh * 1000 / 3600) * elapsed
                steps = int(dist / STEP_LEN)
                self.log(f"  ⏱ {elapsed}s | 步数≈{steps} | {dist:.0f}m | {cur_speed:.1f}km/h")
        
        elapsed = int(time.time() - start_time)
        dist_total = speed_kmh * elapsed / 3600
        steps = int(dist_total * 1000 / STEP_LEN)
        self.log(f"\n  🏁 完成! {elapsed}s | 步数≈{steps} | 距离≈{dist_total:.2f}km")


# ============================================================
#  🖥️ GUI
# ============================================================
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("步道乐跑自动刷 V6 🛡️GPS注入版")
        self.root.geometry("780x620")
        self.root.configure(bg="#1a1a2e")
        self.stop_event = threading.Event()
        self.engine = RunEngine(log_cb=self.log, stop_event=self.stop_event)
        self._ui()
    
    def _ui(self):
        tk.Label(self.root, text="🏃 步道乐跑自动刷 V6", bg="#1a1a2e", fg="#00d4ff",
                 font=("Microsoft YaHei UI", 14, "bold")).pack(anchor="w", padx=15, pady=(12, 2))
        
        info = tk.Frame(self.root, bg="#16213e", highlightbackground="#0f3460", highlightthickness=1)
        info.pack(fill="x", padx=15, pady=4)
        tk.Label(info,
                 text=f"🛡️ 直接GPS注入 | {INJECT_PER_SEC*3}次/s | 3.5Hz | ±{int(ADC.SPEED_FLUCTUATION*100)}% | 随机暂停",
                 bg="#16213e", fg="#a0a0c0", font=("Microsoft YaHei UI", 9)).pack(pady=6)
        
        p = tk.Frame(self.root, bg="#1a1a2e")
        p.pack(fill="x", padx=15)
        
        r1 = tk.Frame(p, bg="#1a1a2e"); r1.pack(fill="x", pady=2)
        tk.Label(r1, text="🏃 速度:", bg="#1a1a2e", fg="#e0e0e0", width=7, anchor="w").pack(side="left")
        self.speed_var = tk.DoubleVar(value=10.0)
        self.speed_lbl = tk.Label(r1, text="10.0 km/h", bg="#1a1a2e", fg="#00ff88",
                                   font=("Microsoft YaHei UI", 10, "bold"))
        tk.Scale(r1, from_=4, to=10000, resolution=0.5, orient="horizontal",
                 variable=self.speed_var, bg="#1a1a2e", fg="#00d4ff",
                 troughcolor="#16213e", highlightthickness=0, length=350, showvalue=0,
                 command=lambda v: self.speed_lbl.configure(text=f"{float(v):.1f} km/h")).pack(side="left", padx=8)
        self.speed_lbl.pack(side="left")
        
        r2 = tk.Frame(p, bg="#1a1a2e"); r2.pack(fill="x", pady=2)
        tk.Label(r2, text="⏱ 时长:", bg="#1a1a2e", fg="#e0e0e0", width=7, anchor="w").pack(side="left")
        self.dur = tk.IntVar(value=600)
        ttk.Combobox(r2, textvariable=self.dur, width=12, state="readonly",
                     values=[300, 420, 600, 900, 1200, 1800]).pack(side="left", padx=8)
        tk.Label(r2, text="秒  (10min≈1.67km)", bg="#1a1a2e", fg="#808080",
                 font=("Microsoft YaHei UI", 9)).pack(side="left", padx=8)
        
        r3 = tk.Frame(p, bg="#1a1a2e"); r3.pack(fill="x", pady=2)
        tk.Label(r3, text="📍 轨迹:", bg="#1a1a2e", fg="#e0e0e0", width=7, anchor="w").pack(side="left")
        self.mode = tk.StringVar(value="circle")
        tk.Radiobutton(r3, text="圆周", variable=self.mode, value="circle",
                       bg="#1a1a2e", fg="#e0e0e0", selectcolor="#16213e").pack(side="left", padx=8)
        tk.Radiobutton(r3, text="直线", variable=self.mode, value="straight",
                       bg="#1a1a2e", fg="#e0e0e0", selectcolor="#16213e").pack(side="left")
        
        btns = tk.Frame(self.root, bg="#1a1a2e"); btns.pack(fill="x", padx=15, pady=8)
        self.start_btn = tk.Button(btns, text="▶ 开始刷跑", command=self.on_start,
                                   bg="#00b894", fg="#fff", font=("Microsoft YaHei UI", 11, "bold"),
                                   relief="flat", padx=20, pady=10)
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = tk.Button(btns, text="⏹ 停止", command=self.on_stop,
                                  bg="#d63031", fg="#fff", font=("Microsoft YaHei UI", 11, "bold"),
                                  relief="flat", padx=20, pady=10, state="disabled")
        self.stop_btn.pack(side="left", padx=4)
        tk.Button(btns, text="🧹 清理", command=lambda: (remove_all_test_providers(self.log), self.log("✅ 已清理")),
                  bg="#636e72", fg="#fff", font=("Microsoft YaHei UI", 10),
                  relief="flat", padx=10, pady=10).pack(side="right")
        
        tk.Label(self.root, text="📋 日志:", bg="#1a1a2e", fg="#e0e0e0").pack(anchor="w", padx=15)
        self.log_text = scrolledtext.ScrolledText(self.root, bg="#0d1b2a", fg="#b0e0e6",
                                                  font=("Consolas", 9), height=16, relief="flat")
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(2, 12))
    
    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n")
        self.log_text.see("end")
        self.root.update_idletasks()
    
    def on_start(self):
        self.stop_event.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        
        full_antidetect(self.log)
        
        def run():
            try:
                adb("shell", "am", "force-stop", LEPAO_PKG)
                time.sleep(0.5)
                setup_gps_injection(log=self.log)
                self.log("\n启动乐跑...")
                adb("shell", "am", "start", "-n", "com.lptiyu.tanke/.activities.splash.SplashActivity")
                time.sleep(4)
                pid_out, _, _ = adb("shell", "pidof", LEPAO_PKG)
                self.log(f"  ✅ 乐跑已启动 PID={pid_out}")
                self.log("  📱 请在手机上点『开始跑步』")
                
                if self.mode.get() == "circle":
                    self.engine.run_circle(speed_kmh=self.speed_var.get(), duration_sec=self.dur.get())
                else:
                    self.engine.run_straight(speed_kmh=self.speed_var.get(), duration_sec=self.dur.get())
            except Exception as e:
                import traceback
                self.log(f"❌ 异常: {e}")
                self.log(traceback.format_exc())
            finally:
                self.start_btn.configure(state="normal")
                self.stop_btn.configure(state="disabled")
        
        threading.Thread(target=run, daemon=True).start()
    
    def on_stop(self):
        self.stop_event.set()
        self.log("\n⏹ 停止中...")

def main():
    if HAS_GUI:
        root = tk.Tk(); App(root); root.mainloop()
    else:
        full_antidetect()
        adb("shell", "am", "force-stop", LEPAO_PKG); time.sleep(0.5)
        setup_gps_injection()
        print("\n启动乐跑...")
        adb("shell", "am", "start", "-n", "com.lptiyu.tanke/.activities.splash.SplashActivity")
        time.sleep(4)
        pid_out, _, _ = adb("shell", "pidof", LEPAO_PKG)
        print(f"  PID={pid_out}")
        print("请在手机上点开始跑步, 然后回车..."); input()
        
        try:
            s = float(input("速度km/h [10]: ").strip() or "10")
            d = int(input("时长秒 [600]: ").strip() or "600")
            m = input("模式 [1=圆周 2=直线]: ").strip() or "1"
        except:
            s, d, m = 10, 600, "1"
        
        e = RunEngine()
        (e.run_straight if m == "2" else e.run_circle)(speed_kmh=s, duration_sec=d)

if __name__ == "__main__":
    main()