#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
步道乐跑 V3.0 - 纯原生零手机软件版
  手机端: 零安装 (不需要影梭/Frida/任何第三方App)
  PC端:   Python + adb shell cmd location providers 直接注入
  防检测: 高频注入(10次/s x 3prov) + 3s keepalive 对抗乐跑反检测

架构:
  PC Python ──adb──▶ cmd location providers {add|enable|set-location}
                       (安卓系统原生API, shell权限, 乐跑踢不掉)
"""

import subprocess, sys, time, math, re, random, threading, os

try:
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox
    HAS_GUI = True
except ImportError:
    HAS_GUI = False

ADB = r"C:\Users\lenovo\PycharmProjects\PythonProject\platform-tools\adb.exe"
DEVICE = ""
LEPAO_PKG = "com.lptiyu.tanke"
STEP_LEN = 0.70
LAT = 41.6872
LNG = 123.6306
PROVIDERS = ["gps", "network", "fused"]

scan_lock = threading.Lock()

def scan_device():
    global DEVICE
    with scan_lock:
        try:
            r = subprocess.run([ADB, "devices"], capture_output=True, text=True, timeout=5,
                               encoding="utf-8", errors="replace")
            for line in r.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("List"):
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    DEVICE = parts[0]
                    return DEVICE
        except Exception:
            pass
        DEVICE = ""
        return ""

def adb_raw(*args, timeout=10):
    cmd = [ADB] + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except Exception as e:
        return "", str(e), -1

def adb_shell(*cmds, timeout=10):
    if not DEVICE:
        scan_device()
    shell_cmd = " ; ".join(cmds)
    return adb_raw("-s", DEVICE, "shell", shell_cmd, timeout=timeout)

def adb_nosel(*args, timeout=10):
    return adb_raw(*args, timeout=timeout)

def is_device_online():
    return bool(scan_device())

def providers_init(log=None):
    log = log or print
    out, _, rc = adb_shell(
        "cmd location providers add-test-provider gps --supportsAltitude --supportsSpeed --supportsBearing --requiresSatellite",
        "cmd location providers add-test-provider network --requiresNetwork",
        "cmd location providers add-test-provider fused --supportsAltitude --supportsSpeed --supportsBearing",
        "cmd location providers set-test-provider-enabled gps true",
        "cmd location providers set-test-provider-enabled network true",
        "cmd location providers set-test-provider-enabled fused true",
    )
    log(f"  ✅ 3个 test providers 已就绪 (gps/network/fused)")
    return True

def providers_keepalive():
    adb_shell(
        "cmd location providers set-test-provider-enabled gps true",
        "cmd location providers set-test-provider-enabled network true",
        "cmd location providers set-test-provider-enabled fused true",
        timeout=3,
    )

def providers_remove_all():
    adb_shell(
        "cmd location providers set-test-provider-enabled gps false",
        "cmd location providers set-test-provider-enabled network false",
        "cmd location providers set-test-provider-enabled fused false",
        "cmd location providers remove-test-provider gps",
        "cmd location providers remove-test-provider network",
        "cmd location providers remove-test-provider fused",
        timeout=4,
    )

def inject_gps(lat, lng, acc=4.0):
    lat_s = f"{lat:.7f}"
    lng_s = f"{lng:.7f}"
    ts = str(int(time.time() * 1000))
    cmds = []
    for p in PROVIDERS:
        cmds.append(f"cmd location providers set-test-provider-enabled {p} true")
        cmds.append(f"cmd location providers set-test-provider-location {p} --location {lat_s},{lng_s} --accuracy {acc} --time {ts}")
    adb_shell(*cmds, timeout=5)

def launch(pkg, activity=None):
    adb_shell(f"am force-stop {pkg}")
    time.sleep(0.3)
    if activity:
        adb_shell(f"am start -n {activity}")
    else:
        adb_raw("-s", DEVICE, "shell", "monkey", "-p", pkg,
                "-c", "android.intent.category.LAUNCHER", "1")

def kill_conflict_apps(log=None):
    log = log or print
    conflicts = [
        "com.ninja.toolkit.pulse.fake.gps.pro",
        "com.zcshou.gogogo",
        "com.vphone.launcher",
        "com.nick.apps.locationspoofer",
        "com.kuxun.fakegps",
        "com.lerist.fakelocation",
        "com.fake.gps",
        "com.mock.location",
    ]
    for pkg in conflicts:
        adb_shell(f"am force-stop {pkg}")
    adb_shell("settings delete secure mock_location_app")
    log(f"  ✅ 冲突假定位App已清理 (连影梭都不需要!)")

R_EARTH = 6371000.0

def _offset(lat, lng, dy_m, dx_m):
    dlat = dy_m / R_EARTH * 180.0 / math.pi
    dlng = dx_m / (R_EARTH * math.cos(math.radians(lat))) * 180.0 / math.pi
    return lat + dlat, lng + dlng

def _noise(lat, lng):
    r = random.gauss(0, 3.0)
    if random.random() < 0.05:
        r *= 3.0
    ang = random.uniform(0, 2 * math.pi)
    return _offset(lat, lng, r * math.sin(ang), r * math.cos(ang))

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
    breath = math.sin(2 * math.pi * 0.15 * elapsed) * 0.22 * 0.5
    noise = (random.random() - 0.5) * 0.22
    final = phase * (1 + breath + noise)
    return max(phase * 0.6, final)

def get_lptiyu_counter():
    out, _, _ = adb_raw("-s", DEVICE, "shell", "dumpsys location", timeout=6)
    max_cnt = 0
    for l in out.splitlines():
        if "lptiyu" in l.lower() and "locations = " in l:
            m = re.search(r'locations = (\d+)', l)
            if m:
                max_cnt = max(max_cnt, int(m.group(1)))
    return max_cnt

def check_lptiyu_running():
    out, _, _ = adb_raw("-s", DEVICE, "shell", "dumpsys location", timeout=6)
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
            if mm: total_ms += int(mm.group(1))
        else:
            ss = re.search(r'(\d+)s', interval_str)
            if ss: total_ms += int(ss.group(1)) * 1000
            mm = re.search(r'(\d+)m(?!s)', interval_str)
            if mm: total_ms += int(mm.group(1)) * 60000
        if 0 < total_ms < 30000:
            return True
    return False

def full_antidetect(log=print):
    log("=" * 60)
    log("  🛡️ V3.0 纯原生零手机软件版")
    log("  📱 手机上什么都不用装! 纯 adb shell cmd location")
    log("  🔁 高频注入 + 3s keepalive 对抗乐跑反检测")
    log("=" * 60)
    kill_conflict_apps(log)
    log("")
    log("🛡️ [反模拟器]")
    out, _, _ = adb_raw("-s", DEVICE, "shell", "getprop ro.hardware")
    bad = ["goldfish", "qemu", "ranchu", "sdk", "emulator"]
    if any(k in out.lower() for k in bad):
        adb_shell("setprop ro.product.model V2230A",
                  "setprop ro.product.brand vivo",
                  "setprop ro.product.device pd2230a",
                  "setprop ro.hardware mt6891")
        log(f"  ✅ 已伪装 vivo V2230A")
    else:
        log(f"  ✅ 硬件正常: {out.strip()}")
    log("")
    log("🛡️ [权限]")
    adb_shell("appops set 2000 MOCK_LOCATION allow",
              "appops set shell MOCK_LOCATION allow",
              "settings delete secure mock_location_app")
    log(f"  ✅ shell MOCK_LOCATION 已授权")

class Runner:
    def __init__(self, log_cb=None, stop_event=None, track_cb=None):
        self.log = log_cb or print
        self.stop_event = stop_event or threading.Event()
        self.track_cb = track_cb
        self.stats = {"steps": 0, "distance": 0, "gps_count": 0, "duration": 0}
        self.inject_count = 0

    def _wait_for_lptiyu_run(self):
        self.log("\n" + "=" * 50)
        self.log("📱 请在手机上打开乐跑 → 点『开始跑步』")
        self.log("=" * 50)
        waited = 0
        while not self.stop_event.is_set():
            if check_lptiyu_running():
                self.log(f"  ✅ 乐跑已开始跑步! (等待 {waited}s)")
                return True
            time.sleep(2)
            waited += 2
            if waited % 10 == 0:
                self.log(f"  ⏳ 等待乐跑点开始跑步... ({waited}s)")
        return False

    def run_circle(self, speed_kmh=10, radius_m=300, duration_sec=600, lat=LAT, lng=LNG, inject_per_sec=10):
        self.log(f"\n🏃 圆周刷跑 | {speed_kmh} km/h | r={radius_m}m | {duration_sec}s | {inject_per_sec}次/s")
        full_antidetect(log=self.log)
        providers_init(log=self.log)
        time.sleep(0.5)

        if not self._wait_for_lptiyu_run():
            self.log("⏹ 已取消")
            return

        start_time = time.time()
        prev_counter = get_lptiyu_counter()
        self.log(f"  📍 乐跑起始 location count = {prev_counter}")
        self.stats["gps_count"] = prev_counter

        last_monitor = 0
        last_keepalive = 0
        no_gps_count = 0
        cur_lat, cur_lng = lat, lng
        INJ_DELAY = 1.0 / inject_per_sec

        try:
            while not self.stop_event.is_set():
                elapsed = time.time() - start_time
                if elapsed >= duration_sec:
                    break

                cur_speed = human_speed(speed_kmh, elapsed, duration_sec)
                lat_speed_ms = cur_speed * 1000 / 3600

                for _ in range(inject_per_sec):
                    if self.stop_event.is_set() or (time.time() - start_time) >= duration_sec:
                        break
                    angular = lat_speed_ms / radius_m
                    angle = angular * elapsed + math.radians(90)
                    dx_m = math.cos(angle) * lat_speed_ms / inject_per_sec
                    dy_m = math.sin(angle) * lat_speed_ms / inject_per_sec
                    cur_lat, cur_lng = _offset(cur_lat, cur_lng, dy_m, dx_m)
                    cur_lat, cur_lng = _noise(cur_lat, cur_lng)
                    inject_gps(cur_lat, cur_lng, acc=random.uniform(3.5, 8.0))
                    self.inject_count += 1
                    time.sleep(INJ_DELAY)

                elapsed_int = int(elapsed)

                if elapsed_int - last_keepalive >= 3:
                    providers_keepalive()
                    inject_gps(cur_lat, cur_lng, acc=4.0)
                    self.inject_count += 1
                    last_keepalive = elapsed_int

                if elapsed_int - last_monitor >= 3:
                    cnt = get_lptiyu_counter()
                    delta = cnt - prev_counter
                    prev_counter = cnt
                    self.stats["gps_count"] = cnt
                    self.stats["duration"] = elapsed_int
                    dist = (speed_kmh * 1000 / 3600) * elapsed
                    self.stats["distance"] = dist
                    self.stats["steps"] = int(dist / STEP_LEN)
                    if delta > 0:
                        no_gps_count = 0
                        self.log(f"  ✅ 乐跑+{delta} locs | 累计 {cnt} | 步数≈{self.stats['steps']} | 📍({cur_lat:.5f},{cur_lng:.5f}) | ⏱{elapsed_int}s | 💉{self.inject_count}")
                    else:
                        no_gps_count += 1
                        self.log(f"  ⚠ 乐跑未接收 location ({no_gps_count}/5)")
                        if no_gps_count >= 5:
                            self.log(f"  🔧 重建 providers + 重注入...")
                            providers_remove_all()
                            providers_init(log=self.log)
                            inject_gps(cur_lat, cur_lng, acc=4.0)
                            no_gps_count = 0
                            time.sleep(1)
                    if self.track_cb:
                        self.track_cb(cur_lat, cur_lng)
                    last_monitor = elapsed_int

                if elapsed_int > 20 and random.random() < 0.025:
                    pd = random.randint(2, 10) if random.random() > 0.005 else random.randint(20, 60)
                    self.log(f"  🛑 模拟暂停 {pd}s")
                    for _ in range(pd):
                        if self.stop_event.is_set():
                            break
                        time.sleep(1)

                time.sleep(0.02)

        finally:
            elapsed = int(time.time() - start_time)
            dist_total = speed_kmh * elapsed / 3600
            steps = int(dist_total * 1000 / STEP_LEN)
            self.stats["steps"] = steps
            self.stats["distance"] = dist_total * 1000
            self.stats["duration"] = elapsed
            self.log(f"\n  🏁 完成! {elapsed}s | 步数≈{steps} | 距离≈{dist_total:.2f}km | 💉共注入{self.inject_count}次")

    def run_straight(self, speed_kmh=10, direction="forward", duration_sec=600, lat=LAT, lng=LNG, inject_per_sec=10):
        self.log(f"\n🏃 直线刷跑 | {speed_kmh} km/h | {duration_sec}s | {inject_per_sec}次/s")
        full_antidetect(log=self.log)
        providers_init(log=self.log)
        time.sleep(0.5)

        if not self._wait_for_lptiyu_run():
            self.log("⏹ 已取消")
            return

        start_time = time.time()
        prev_counter = get_lptiyu_counter()
        self.log(f"  📍 乐跑起始 location count = {prev_counter}")
        self.stats["gps_count"] = prev_counter

        last_monitor = 0
        last_keepalive = 0
        no_gps_count = 0
        cur_lat, cur_lng = lat, lng
        signs = {"forward": (1, 0), "back": (-1, 0), "right": (0, 1), "left": (0, -1)}
        ds, ls = signs.get(direction, (1, 0))
        INJ_DELAY = 1.0 / inject_per_sec

        try:
            while not self.stop_event.is_set():
                elapsed = time.time() - start_time
                if elapsed >= duration_sec:
                    break

                cur_speed = human_speed(speed_kmh, elapsed, duration_sec)
                lat_speed_ms = cur_speed * 1000 / 3600

                for _ in range(inject_per_sec):
                    if self.stop_event.is_set() or (time.time() - start_time) >= duration_sec:
                        break
                    cur_lat = cur_lat + ds * (lat_speed_ms / inject_per_sec) / 111000.0
                    cur_lng = cur_lng + ls * (lat_speed_ms / inject_per_sec) / (111000.0 * math.cos(math.radians(cur_lat)))
                    cur_lat, cur_lng = _noise(cur_lat, cur_lng)
                    inject_gps(cur_lat, cur_lng, acc=random.uniform(3.5, 8.0))
                    self.inject_count += 1
                    time.sleep(INJ_DELAY)

                elapsed_int = int(elapsed)

                if elapsed_int - last_keepalive >= 3:
                    providers_keepalive()
                    inject_gps(cur_lat, cur_lng, acc=4.0)
                    self.inject_count += 1
                    last_keepalive = elapsed_int

                if elapsed_int - last_monitor >= 3:
                    cnt = get_lptiyu_counter()
                    delta = cnt - prev_counter
                    prev_counter = cnt
                    self.stats["gps_count"] = cnt
                    self.stats["duration"] = elapsed_int
                    dist = (speed_kmh * 1000 / 3600) * elapsed
                    self.stats["distance"] = dist
                    self.stats["steps"] = int(dist / STEP_LEN)
                    if delta > 0:
                        no_gps_count = 0
                        self.log(f"  ✅ 乐跑+{delta} locs | 累计 {cnt} | 步数≈{self.stats['steps']} | 📍({cur_lat:.5f},{cur_lng:.5f}) | ⏱{elapsed_int}s | 💉{self.inject_count}")
                    else:
                        no_gps_count += 1
                        self.log(f"  ⚠ 乐跑未接收 location ({no_gps_count}/5)")
                        if no_gps_count >= 5:
                            self.log(f"  🔧 重建 providers + 重注入...")
                            providers_remove_all()
                            providers_init(log=self.log)
                            inject_gps(cur_lat, cur_lng, acc=4.0)
                            no_gps_count = 0
                            time.sleep(1)
                    if self.track_cb:
                        self.track_cb(cur_lat, cur_lng)
                    last_monitor = elapsed_int

                if elapsed_int > 20 and random.random() < 0.025:
                    pd = random.randint(2, 10) if random.random() > 0.005 else random.randint(20, 60)
                    self.log(f"  🛑 模拟暂停 {pd}s")
                    for _ in range(pd):
                        if self.stop_event.is_set():
                            break
                        time.sleep(1)

                time.sleep(0.02)

        finally:
            elapsed = int(time.time() - start_time)
            dist_total = speed_kmh * elapsed / 3600
            steps = int(dist_total * 1000 / STEP_LEN)
            self.stats["steps"] = steps
            self.stats["distance"] = dist_total * 1000
            self.stats["duration"] = elapsed
            self.log(f"\n  🏁 完成! {elapsed}s | 步数≈{steps} | 距离≈{dist_total:.2f}km | 💉共注入{self.inject_count}次")

    def stop(self):
        self.stop_event.set()

if HAS_GUI:
    class App:
        def __init__(self, root):
            self.root = root
            self.root.title("步道乐跑 V3.0 - 纯原生零手机软件版 🛡️终极防检测")
            self.root.geometry("1020x780")
            self.root.configure(bg="#1a1a2e")
            self.run_stop = threading.Event()
            self._daemon_stop = threading.Event()
            self._daemon_running = False
            self._build_ui()
            self._device_check()
            self._start_daemon()

        def _start_daemon(self):
            def run():
                self._daemon_running = True
                first_log = True
                providers_inited = False
                angle = 0
                radius_lat = 30.0 / 111000.0
                radius_lng = 30.0 / (111000.0 * math.cos(math.radians(LAT)))
                last_keepalive = 0
                last_device_check = 0
                while not self._daemon_stop.is_set():
                    now = int(time.time())
                    if now - last_device_check >= 10:
                        if not is_device_online():
                            time.sleep(3)
                            continue
                        last_device_check = now
                    try:
                        if not providers_inited:
                            providers_init(log=print)
                            providers_inited = True
                        if first_log:
                            self._thread_log("🛡️ 自动守护线程已启动 → 圆周运动 GPS 注入 (r=30m)")
                            first_log = False
                        angle += 0.012
                        cur_lat = LAT + radius_lat * math.cos(angle) + random.uniform(-0.000005, 0.000005)
                        cur_lng = LNG + radius_lng * math.sin(angle) + random.uniform(-0.000005, 0.000005)
                        ts = str(int(time.time() * 1000))
                        ls, ns = f"{cur_lat:.7f}", f"{cur_lng:.7f}"
                        cmds = []
                        for p in PROVIDERS:
                            cmds.append(f"cmd location providers set-test-provider-enabled {p} true")
                            cmds.append(f"cmd location providers set-test-provider-location {p} --location {ls},{ns} --accuracy 4.5 --time {ts}")
                        adb_shell(*cmds, timeout=4)
                        time.sleep(0.4)
                    except Exception as e:
                        time.sleep(1)
                self._daemon_running = False
            threading.Thread(target=run, daemon=True).start()

        def _build_ui(self):
            style = ttk.Style()
            style.theme_use("clam")
            style.configure("TNotebook", background="#1a1a2e", borderwidth=0)
            style.configure("TNotebook.Tab", background="#16213e", foreground="#e0e0e0",
                            padding=[14, 7], font=("微软雅黑", 9, "bold"))
            style.map("TNotebook.Tab", background=[("selected", "#0f3460")])
            style.configure("TFrame", background="#1a1a2e")

            nb = ttk.Notebook(self.root)
            nb.pack(fill="both", expand=True, padx=6, pady=6)
            self._build_control_tab(nb)
            self._build_map_tab(nb)
            self._build_help_tab(nb)

        def _build_control_tab(self, nb):
            tab = ttk.Frame(nb)
            nb.add(tab, text="🎮 控制")

            panel = tk.Frame(tab, bg="#16213e", highlightthickness=1, highlightbackground="#0f3460")
            panel.pack(fill="x", padx=10, pady=6)
            tk.Label(panel, text="🛡️ V3.0 纯原生零手机软件版 🛡️", bg="#16213e", fg="#00d4ff",
                     font=("微软雅黑", 13, "bold")).pack(pady=(8, 2))
            tk.Label(panel, text="手机上什么都不用装! 纯 adb shell cmd location providers 高频注入 + 3s keepalive",
                     bg="#16213e", fg="#aaa", font=("微软雅黑", 8)).pack(pady=(0, 8))

            row1 = tk.Frame(tab, bg="#1a1a2e")
            row1.pack(fill="x", padx=10, pady=4)
            for text, cb, color in [
                ("🔄 重连ADB", self.on_reconnect, "#16a085"),
                ("🛡️ 一键防检测", self.on_antidetect, "#27ae60"),
                ("📡 初始化GPS注入", self.on_init_providers, "#2980b9"),
                ("🏃 启动乐跑", self.on_launch_lptiyu, "#e55039"),
                ("📡 清理冲突", self.on_kill_conflict, "#8e44ad"),
                ("📡 清理GPS注入", self.on_remove_providers, "#c0392b"),
            ]:
                tk.Button(row1, text=text, command=cb, bg=color, fg="white",
                          font=("微软雅黑", 9, "bold"), relief="flat", padx=8, pady=5,
                          cursor="hand2").pack(side="left", padx=4)

            panel2 = tk.Frame(tab, bg="#16213e", highlightthickness=1, highlightbackground="#0f3460")
            panel2.pack(fill="x", padx=10, pady=6)
            tk.Label(panel2, text="🏃 刷跑参数", bg="#16213e", fg="#00d4ff",
                     font=("微软雅黑", 11, "bold")).pack(anchor="w", padx=10, pady=(8, 4))
            grid = tk.Frame(panel2, bg="#16213e")
            grid.pack(padx=10, pady=8)
            items = [
                ("速度(km/h):", "var_speed", "10"),
                ("时长(秒):", "var_duration", "600"),
                ("半径(m):", "var_radius", "300"),
                ("注入频率/s:", "var_rate", "10"),
                ("起点纬度:", "var_lat", str(LAT)),
                ("起点经度:", "var_lng", str(LNG)),
            ]
            for i, (label, attr, default) in enumerate(items):
                tk.Label(grid, text=label, bg="#16213e", fg="#e0e0e0").grid(row=i//2, column=(i%2)*2, sticky="e", padx=4, pady=4)
                var = tk.StringVar(value=default)
                setattr(self, attr, var)
                tk.Entry(grid, textvariable=var, width=10).grid(row=i//2, column=(i%2)*2+1, sticky="w", padx=4, pady=4)
            tk.Label(grid, text="轨迹:", bg="#16213e", fg="#e0e0e0").grid(row=3, column=0, sticky="e", padx=4, pady=4)
            self.var_track = tk.StringVar(value="圆周")
            ttk.Combobox(grid, textvariable=self.var_track, values=["圆周", "直线"], width=8, state="readonly").grid(row=3, column=1, sticky="w", padx=4, pady=4)

            start_row = tk.Frame(tab, bg="#1a1a2e")
            start_row.pack(fill="x", padx=10, pady=6)
            self.btn_start = tk.Button(start_row, text="▶ 开始刷跑", command=self.on_start,
                                       bg="#e74c3c", fg="white", font=("微软雅黑", 14, "bold"),
                                       relief="flat", padx=30, pady=8, cursor="hand2", width=14)
            self.btn_start.pack(side="left", padx=6)
            self.btn_stop = tk.Button(start_row, text="⏹ 停止", command=self.on_stop,
                                      bg="#7f8c8d", fg="white", font=("微软雅黑", 14, "bold"),
                                      relief="flat", padx=30, pady=8, cursor="hand2", width=14, state="disabled")
            self.btn_stop.pack(side="left", padx=6)

            log_panel = tk.Frame(tab, bg="#16213e", highlightthickness=1, highlightbackground="#0f3460")
            log_panel.pack(fill="both", expand=True, padx=10, pady=6)
            tk.Label(log_panel, text="📋 运行日志", bg="#16213e", fg="#00d4ff",
                     font=("微软雅黑", 9, "bold")).pack(anchor="w", padx=10, pady=(6, 2))
            self.log_text = scrolledtext.ScrolledText(log_panel, height=10, bg="#0d1117", fg="#c9d1d9",
                                                      font=("Consolas", 9), insertbackground="#58a6ff")
            self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        def _build_map_tab(self, nb):
            tab = ttk.Frame(nb)
            nb.add(tab, text="🗺️ 轨迹+状态")

            stat_bar = tk.Frame(tab, bg="#16213e")
            stat_bar.pack(fill="x", padx=10, pady=6)

            self.stat_labels = {}
            cards = [("🚶 步数", "steps", "#e74c3c"), ("📏 距离", "distance", "#3498db"),
                     ("📡 GPS", "gps_count", "#27ae60"), ("⏱ 时长", "duration", "#f39c12"),
                     ("💉 注入", "inject", "#9b59b6"), ("📍 设备", "device", "#1abc9c"),
                     ("🎯 乐跑", "lptiyu", "#16a085")]
            for i, (title, key, color) in enumerate(cards):
                card = tk.Frame(stat_bar, bg="#16213e", highlightthickness=2, highlightbackground=color)
                card.grid(row=0, column=i, padx=4, pady=4, sticky="nsew")
                tk.Label(card, text=title, bg="#16213e", fg=color, font=("微软雅黑", 9, "bold")).pack(pady=(6, 1))
                lbl = tk.Label(card, text="--", bg="#16213e", fg="#ffffff", font=("微软雅黑", 14, "bold"))
                lbl.pack(pady=(0, 6))
                self.stat_labels[key] = lbl
            for i in range(7):
                stat_bar.columnconfigure(i, weight=1)

            map_frame = tk.Frame(tab, bg="#0d1117", highlightthickness=2, highlightbackground="#0f3460")
            map_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
            self.map_canvas = tk.Canvas(map_frame, bg="#0d1117", highlightthickness=0, cursor="crosshair")
            self.map_canvas.pack(fill="both", expand=True)
            self.map_track = []
            self.map_start = None
            self.map_canvas.bind("<Configure>", lambda e: self._redraw_map())

        def _build_help_tab(self, nb):
            tab = ttk.Frame(nb)
            nb.add(tab, text="📖 说明")
            help_text = """
【V3.0 纯原生零手机软件版】 ✅ 终极版

  V1 的问题: 依赖影梭/Frida/第三方假定位App → 易被乐跑踢掉
  V2 的问题: 依赖手机端 gps_daemon.sh 脚本
  V3.0 的解法: 手机上什么都不用装! 纯 adb shell cmd location providers

  原理:
    adb shell cmd location providers add-test-provider gps/network/fused
    adb shell cmd location providers set-test-provider-enabled true
    adb shell cmd location providers set-test-provider-location ...

  这三条是安卓系统原生 shell 命令, 属于系统级 mock provider, 乐跑根本踢不掉!

  防检测机制:
    1. 高频注入 (默认 10次/s × 3prov = 30次GPS/s)
    2. 3秒一次 keepalive (set-test-provider-enabled true 对抗乐跑 remove)
    3. 连续 5 次乐跑 counter 没增长 → 完全重建 providers + 重注入
    4. 速度曲线 + GPS噪声 + 随机暂停 → 模拟真实人类跑步

  使用流程:
    1. 插USB → 开USB调试 → 点"🔄 重连ADB"
    2. 点"🛡️ 一键防检测" (自动杀假定位App + 伪装硬件)
    3. 点"📡 初始化GPS注入" (或直接点"▶ 开始刷跑")
    4. 点"🏃 启动乐跑" → 手机乐跑点"开始跑步"
    5. 点"▶ 开始刷跑" → 自动圆周/直线轨迹

  已清理的冲突App (自动杀): 影梭/FakeGPS/Ninja/LocationSpoofer 等
  乐跑 counter 被压到根本踢不动 mock provider!
"""
            tk.Label(tab, text=help_text, bg="#1a1a2e", fg="#e0e0e0",
                     font=("微软雅黑", 9), justify="left", wraplength=920).pack(anchor="w", padx=20, pady=15)

        def _thread_log(self, msg):
            def do():
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
            self.root.after(0, do)

        def _device_check(self):
            def check():
                if is_device_online():
                    self.stat_labels["device"].config(text=f"✅ {DEVICE[:12]}", fg="#2ecc71")
                else:
                    self.stat_labels["device"].config(text="❌ 未连接", fg="#e74c3c")
                self.root.after(3000, check)
            check()

        def _stats_timer(self):
            def update():
                if hasattr(self, 'engine') and self.engine and not self.engine.stop_event.is_set():
                    s = self.engine.stats
                    self.stat_labels["steps"].config(text=str(s.get("steps", 0)))
                    self.stat_labels["distance"].config(text=f"{s.get('distance',0)/1000:.2f}km")
                    self.stat_labels["gps_count"].config(text=str(s.get("gps_count", 0)))
                    self.stat_labels["duration"].config(text=f"{s.get('duration', 0)}s")
                    self.stat_labels["inject"].config(text=str(self.engine.inject_count))
                try:
                    running = check_lptiyu_running()
                    self.stat_labels["lptiyu"].config(
                        text="🏃 跑步中" if running else "⏸ 等待",
                        fg="#2ecc71" if running else "#f39c12")
                except Exception:
                    pass
                self.root.after(2000, update)
            update()

        def _on_track_point(self, lat, lng):
            def do():
                if not self.map_track:
                    self.map_start = (lat, lng)
                self.map_track.append((lat, lng))
                self._redraw_map()
            self.root.after(0, do)

        def _gps_to_canvas(self, lat, lng):
            if not self.map_track:
                return None, None
            w = self.map_canvas.winfo_width()
            h = self.map_canvas.winfo_height()
            if w < 10 or h < 10:
                return None, None
            all_pts = self.map_track + ([self.map_start] if self.map_start else [])
            lats = [p[0] for p in all_pts]
            lngs = [p[1] for p in all_pts]
            lat_min, lat_max = min(lats), max(lats)
            lng_min, lng_max = min(lngs), max(lngs)
            lat_range = max(lat_max - lat_min, 0.0001)
            lng_range = max(lng_max - lng_min, 0.0001)
            margin = 40
            scale = min((w - margin*2) / lng_range, (h - margin*2) / lat_range, 200000)
            cx = margin + (lng - lng_min) * scale
            cy = margin + (lat_max - lat) * scale
            return int(cx), int(cy)

        def _redraw_map(self):
            self.map_canvas.delete("all")
            w = self.map_canvas.winfo_width()
            h = self.map_canvas.winfo_height()
            if w < 10 or h < 10:
                return
            for i in range(0, w, 50):
                self.map_canvas.create_line(i, 0, i, h, fill="#1a2634", width=1)
            for i in range(0, h, 50):
                self.map_canvas.create_line(0, i, w, i, fill="#1a2634", width=1)
            if len(self.map_track) >= 2:
                pts = []
                for lat, lng in self.map_track:
                    cx, cy = self._gps_to_canvas(lat, lng)
                    if cx is not None:
                        pts.extend([cx, cy])
                if len(pts) >= 4:
                    self.map_canvas.create_line(pts, fill="#2ecc71", width=3, smooth=True, arrow="last", arrowshape=(10,12,4))
            if self.map_start:
                sx, sy = self._gps_to_canvas(self.map_start[0], self.map_start[1])
                if sx is not None:
                    self.map_canvas.create_oval(sx-8, sy-8, sx+8, sy+8, fill="#e74c3c", outline="#fff", width=2)
                    self.map_canvas.create_text(sx, sy-14, text="起点", fill="#e74c3c", font=("微软雅黑", 9, "bold"))
            if self.map_track:
                last = self.map_track[-1]
                ex, ey = self._gps_to_canvas(last[0], last[1])
                if ex is not None:
                    self.map_canvas.create_oval(ex-7, ey-7, ex+7, ey+7, fill="#f1c40f", outline="#fff", width=2)
                    self.map_canvas.create_text(ex, ey-12, text="当前", fill="#f1c40f", font=("微软雅黑", 9, "bold"))

        def _run_thread(self, target, *args):
            threading.Thread(target=target, args=args, daemon=True).start()

        def on_reconnect(self):
            def run():
                self._thread_log("\n🔄 ADB 重连中...")
                adb_nosel("kill-server")
                time.sleep(0.5)
                adb_nosel("start-server")
                time.sleep(1.5)
                if scan_device():
                    self._thread_log(f"  ✅ 已连接设备: {DEVICE}")
                else:
                    self._thread_log("  ❌ 未检测到设备, 检查 USB/调试授权")
            self._run_thread(run)

        def on_antidetect(self):
            def run():
                if not is_device_online():
                    self._thread_log("❌ 设备未连接!")
                    return
                full_antidetect(log=self._thread_log)
            self._run_thread(run)

        def on_init_providers(self):
            def run():
                if not is_device_online():
                    self._thread_log("❌ 设备未连接!")
                    return
                self._thread_log("\n📡 初始化 GPS test providers...")
                providers_init(log=self._thread_log)
                inject_gps(float(self.var_lat.get()), float(self.var_lng.get()), acc=4.0)
                self._thread_log("  ✅ GPS 注入已就绪!")
            self._run_thread(run)

        def on_remove_providers(self):
            def run():
                self._thread_log("\n📡 清理所有 test providers...")
                providers_remove_all()
                self._thread_log("  ✅ 已清理")
            self._run_thread(run)

        def on_launch_lptiyu(self):
            def run():
                if not is_device_online():
                    self._thread_log("❌ 设备未连接!")
                    return
                self._thread_log("\n🏃 启动乐跑...")
                launch(LEPAO_PKG)
                self._thread_log("  ✅ 乐跑已启动 → 点『开始跑步』")
            self._run_thread(run)

        def on_kill_conflict(self):
            def run():
                kill_conflict_apps(log=self._thread_log)
            self._run_thread(run)

        def on_start(self):
            if not is_device_online():
                messagebox.showerror("错误", "设备未连接!")
                return
            if hasattr(self, 'engine') and self.engine and not self.engine.stop_event.is_set():
                messagebox.showwarning("警告", "已有刷跑在进行中")
                return
            try:
                speed = float(self.var_speed.get())
                duration = int(self.var_duration.get())
                lat = float(self.var_lat.get())
                lng = float(self.var_lng.get())
                radius = float(self.var_radius.get())
                rate = int(self.var_rate.get())
                track = self.var_track.get()
            except ValueError:
                messagebox.showerror("错误", "参数格式错误")
                return

            self.run_stop = threading.Event()
            self.engine = Runner(log_cb=self._thread_log, stop_event=self.run_stop, track_cb=self._on_track_point)
            self.btn_start.config(state="disabled", bg="#7f8c8d")
            self.btn_stop.config(state="normal", bg="#e74c3c")

            if track == "圆周":
                target = self.engine.run_circle
                kwargs = {"speed_kmh": speed, "radius_m": radius, "duration_sec": duration,
                          "lat": lat, "lng": lng, "inject_per_sec": rate}
            else:
                target = self.engine.run_straight
                kwargs = {"speed_kmh": speed, "duration_sec": duration,
                          "lat": lat, "lng": lng, "inject_per_sec": rate}

            def run_target():
                try:
                    target(**kwargs)
                except Exception as e:
                    self._thread_log(f"  ❌ 异常: {e}")
                finally:
                    self.root.after(0, self._run_done)

            threading.Thread(target=run_target, daemon=True).start()

        def on_stop(self):
            if hasattr(self, 'engine') and self.engine:
                self.engine.stop()
                self.run_stop.set()
                self._thread_log("\n⏹ 停止中...")

        def _run_done(self):
            self.btn_start.config(state="normal", bg="#e74c3c")
            self.btn_stop.config(state="disabled", bg="#7f8c8d")

    def main():
        root = tk.Tk()
        app = App(root)
        app._stats_timer()
        root.mainloop()
else:
    def main():
        print("需要 tkinter")
        sys.exit(1)

if __name__ == "__main__":
    main()