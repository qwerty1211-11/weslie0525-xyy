import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import time
import math
import random
import re
import os
import sys


class UltraGPSRunner:
    def __init__(self, root):
        self.root = root
        self.root.title("校园跑刷步 Ultra Pro v3 - 步道乐跑/闪动校园")
        self.root.geometry("830x800")
        self.root.resizable(False, False)

        self.running = False
        self.thread = None
        self.device_id = None
        self.android_version = None
        self.has_root = False
        self.brand = ""
        self.model = ""

        self.base_lat = 39.9042
        self.base_lng = 116.4074
        self.target_distance = 2.0
        self.speed = 5.0
        self.interval = 1
        self.route_type = "circle"

        self.total_points = 0
        self.covered_points = 0
        self.start_time = None
        self.step_count = 0

        self.setup_ui()

    def setup_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main, text="🏃 校园跑刷步 Ultra Pro v3",
                  font=("Microsoft YaHei", 15, "bold")).pack(pady=(0, 2))
        ttk.Label(main, text="Mock Location + Test Provider + 多通道注入",
                  foreground="#888", font=("Microsoft YaHei", 9)).pack(pady=(0, 10))

        dev = ttk.LabelFrame(main, text="① 设备", padding=8)
        dev.pack(fill=tk.X, pady=3)
        r = ttk.Frame(dev); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text="设备：", width=6).pack(side=tk.LEFT)
        self.device_var = tk.StringVar(value="❌ 未连接")
        ttk.Label(r, textvariable=self.device_var, foreground="#F44336").pack(side=tk.LEFT, padx=4)
        ttk.Button(r, text="🔄 扫描", command=self.scan).pack(side=tk.LEFT, padx=4)
        ttk.Button(r, text="🔍 深度诊断", command=self.deep_diagnose).pack(side=tk.LEFT, padx=4)
        ttk.Button(r, text="🧪 注入测试", command=self.test_single_inject).pack(side=tk.LEFT, padx=4)

        r2 = ttk.Frame(dev); r2.pack(fill=tk.X, pady=2)
        ttk.Label(r2, text="ADB：", width=6).pack(side=tk.LEFT)
        self.adb_var = tk.StringVar(value="adb")
        ttk.Entry(r2, textvariable=self.adb_var, width=28).pack(side=tk.LEFT, padx=4)
        self.aver = tk.StringVar(value="-")
        self.brd = tk.StringVar(value="")
        self.rt = tk.StringVar(value="❌")
        ttk.Label(r2, text="Android:", foreground="#666").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Label(r2, textvariable=self.aver, foreground="#2196F3").pack(side=tk.LEFT)
        ttk.Label(r2, text="设备:", foreground="#666").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Label(r2, textvariable=self.brd, foreground="#666").pack(side=tk.LEFT)
        ttk.Label(r2, text="Root:", foreground="#666").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Label(r2, textvariable=self.rt).pack(side=tk.LEFT)

        cfg = ttk.LabelFrame(main, text="② 参数", padding=8)
        cfg.pack(fill=tk.X, pady=3)
        g1 = ttk.Frame(cfg); g1.pack(fill=tk.X, pady=2)
        ttk.Label(g1, text="纬度：", width=6).pack(side=tk.LEFT)
        self.lat_var = tk.StringVar(value=str(self.base_lat))
        ttk.Entry(g1, textvariable=self.lat_var, width=13).pack(side=tk.LEFT, padx=2)
        ttk.Label(g1, text="经度：", width=6).pack(side=tk.LEFT, padx=(8, 0))
        self.lng_var = tk.StringVar(value=str(self.base_lng))
        ttk.Entry(g1, textvariable=self.lng_var, width=13).pack(side=tk.LEFT, padx=2)
        ttk.Button(g1, text="📍获取定位", command=self.get_loc).pack(side=tk.LEFT, padx=6)

        g2 = ttk.Frame(cfg); g2.pack(fill=tk.X, pady=2)
        ttk.Label(g2, text="距离(km)：", width=10).pack(side=tk.LEFT)
        self.dist_var = tk.StringVar(value=str(self.target_distance))
        ttk.Entry(g2, textvariable=self.dist_var, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Label(g2, text="  速度(km/h)：", width=12).pack(side=tk.LEFT)
        self.speed_var = tk.StringVar(value=str(self.speed))
        ttk.Entry(g2, textvariable=self.speed_var, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Label(g2, text="  间隔(秒)：", width=10).pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value=str(self.interval))
        ttk.Entry(g2, textvariable=self.interval_var, width=6).pack(side=tk.LEFT, padx=2)

        g3 = ttk.Frame(cfg); g3.pack(fill=tk.X, pady=2)
        ttk.Label(g3, text="轨迹：", width=6).pack(side=tk.LEFT)
        self.route_var = tk.StringVar(value="circle")
        ttk.Combobox(g3, textvariable=self.route_var, width=10, state="readonly",
                     values=["circle", "figure8", "zigzag", "outbound"]).pack(side=tk.LEFT, padx=2)
        self.chk_sat = tk.BooleanVar(value=True)
        ttk.Checkbutton(g3, text="模拟卫星", variable=self.chk_sat).pack(side=tk.LEFT, padx=10)
        self.chk_wake = tk.BooleanVar(value=True)
        ttk.Checkbutton(g3, text="保持亮屏", variable=self.chk_wake).pack(side=tk.LEFT, padx=3)

        st = ttk.LabelFrame(main, text="③ 状态", padding=8)
        st.pack(fill=tk.X, pady=3)
        sr = ttk.Frame(st); sr.pack(fill=tk.X)
        for i, label in enumerate(["步数", "距离", "用时", "速度"]):
            ttk.Label(sr, text=label, font=("Microsoft YaHei", 9)).grid(row=0, column=i, padx=20)
        self.sl = ttk.Label(sr, text="0", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.sl.grid(row=1, column=0, padx=20)
        self.dl = ttk.Label(sr, text="0.00 km", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.dl.grid(row=1, column=1, padx=20)
        self.tl = ttk.Label(sr, text="00:00", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.tl.grid(row=1, column=2, padx=20)
        self.cl = ttk.Label(sr, text="0.0 km/h", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.cl.grid(row=1, column=3, padx=20)

        self.prog = ttk.Progressbar(st, mode="determinate")
        self.prog.pack(fill=tk.X, pady=(8, 2))
        self.pl = ttk.Label(st, text="进度：0%")
        self.pl.pack(anchor=tk.W)

        btns = ttk.Frame(main); btns.pack(fill=tk.X, pady=5)
        self.start_btn = ttk.Button(btns, text="▶ 开始刷步", command=self.start_run)
        self.start_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.stop_btn = ttk.Button(btns, text="■ 停止", command=self.stop_run, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        logf = ttk.LabelFrame(main, text="④ 日志", padding=5)
        logf.pack(fill=tk.BOTH, expand=True, pady=3)
        self.log_box = scrolledtext.ScrolledText(logf, height=8, font=("Consolas", 9), state=tk.DISABLED)
        self.log_box.pack(fill=tk.BOTH, expand=True)

        tip = ttk.Label(main, text="⚠️ 开始前先开步道乐跑/闪动校园 App 并点开始跑步！⚠️",
                        foreground="#E65100", font=("Microsoft YaHei", 10, "bold"))
        tip.pack(pady=(5, 0))

        threading.Thread(target=self.scan, daemon=True).start()

    # ===================== ADB =====================
    def adb(self, shell_cmd, timeout=5):
        adb_exe = self.adb_var.get().strip() or "adb"
        target = f"-s {self.device_id} " if self.device_id else ""
        full = f"{adb_exe} {target}shell {shell_cmd}"
        try:
            si = subprocess.STARTUPINFO() if os.name == "nt" else None
            if si:
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=timeout, startupinfo=si)
            return r.stdout.strip(), r.stderr.strip(), r.returncode
        except subprocess.TimeoutExpired:
            return "", "TIMEOUT", -1
        except FileNotFoundError:
            return "", f"找不到adb: {adb_exe}", -1
        except Exception as e:
            return "", str(e), -1

    def log(self, msg):
        def _l():
            ts = time.strftime("%H:%M:%S")
            self.log_box.configure(state=tk.NORMAL)
            self.log_box.insert(tk.END, f"[{ts}] {msg}\n")
            self.log_box.see(tk.END)
            self.log_box.configure(state=tk.DISABLED)
        self.root.after(0, _l)

    # ===================== Scan =====================
    def scan(self):
        adb_exe = self.adb_var.get().strip() or "adb"
        try:
            si = subprocess.STARTUPINFO() if os.name == "nt" else None
            if si:
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            r = subprocess.run(f"{adb_exe} devices", shell=True, capture_output=True, text=True, timeout=8, startupinfo=si)
            devs = [l for l in r.stdout.strip().split("\n") if "\tdevice" in l and "unauthorized" not in l]
            if devs:
                did = devs[0].split("\t")[0]
                self.device_id = did
                self.root.after(0, lambda: self.device_var.set(f"✅ {did}"))

                av = self.adb("getprop ro.build.version.release")[0] or "未知"
                br = self.adb("getprop ro.product.manufacturer")[0] or ""
                md = self.adb("getprop ro.product.model")[0] or ""
                self.android_version = av
                self.brand = br
                self.model = md

                ro, _, rc = self.adb("su -c 'id'", timeout=3)
                self.has_root = (rc == 0 and "uid=0" in ro)

                self.root.after(0, lambda: self.aver.set(av))
                self.root.after(0, lambda: self.brd.set(f"{br} {md}"))
                self.root.after(0, lambda: self.rt.set("✅" if self.has_root else "❌"))
                self.log(f"设备: {did}, Android {av}, {br} {md}, root={'是' if self.has_root else '否'}")

                self.prepare()
            else:
                self.device_id = None
                self.root.after(0, lambda: self.device_var.set("❌ 未检测到设备"))
                self.log("未检测到设备")
        except Exception as e:
            self.device_id = None
            self.root.after(0, lambda: self.device_var.set(f"❌ ADB错误"))
            self.log(f"扫描失败: {e}")

    # ===================== Prepare =====================
    def prepare(self):
        self.log("🔧 正在准备 (Mock Location + Test Provider)...")

        s1 = " && ".join([
            "settings put global adb_enabled 1",
            "settings put global enable_mock_location 1",
            "settings put secure enable_mock_location 1",
            "settings put secure location_mode 3",
            "settings put secure location_providers_allowed gps,network",
            "appops set 20010 MOCK_LOCATION allow",
            "appops set 10630 MOCK_LOCATION allow",
            "appops set 0 MOCK_LOCATION allow",
        ])
        _, _, c = self.adb(s1)
        self.log(f"  Mock开关: code={c}")

        s2 = " && ".join([
            "cmd location set-location-enabled true gps",
            "cmd location set-location-enabled true network",
            "cmd location remove-test-provider gps 2>/dev/null",
            "cmd location remove-test-provider network 2>/dev/null",
            "cmd location add-test-provider gps enabled true has-monitors true has-altitude true has-speed true has-bearing true",
            "cmd location add-test-provider network enabled true has-monitors true",
            "cmd location set-test-provider-enabled gps true",
            "cmd location set-test-provider-enabled network true",
        ])
        _, err, c = self.adb(s2)
        self.log(f"  Provider: code={c}  err={err[:80]}")

        bl = self.brand.lower()
        extras = []
        if any(x in bl for x in ["xiaomi", "mi"]):
            extras += ["settings put system enable_mock_location 1", "settings put global miui_opt_switch 1"]
        if any(x in bl for x in ["huawei", "honor"]):
            extras += ["settings put secure enable_hw_location_simulate 1", "settings put global enable_hw_location_simulate 1"]
        if any(x in bl for x in ["oppo", "realme", "oneplus"]):
            extras += ["settings put oppo_enable_virtual_location 1"]
        if any(x in bl for x in ["vivo", "iqoo"]):
            extras += ["settings put secure enable_virtual_location 1", "settings put global enable_virtual_location 1"]
        if extras:
            self.adb(" && ".join(extras))
            self.log(f"  厂商特化完成")

        if self.has_root:
            rs = "su -c '" + " && ".join([
                "settings put secure enable_mock_location 1",
                "settings put global enable_mock_location 1",
                "cmd location add-test-provider gps enabled true has-monitors true",
                "cmd location set-test-provider-enabled gps true",
            ]) + "'"
            self.adb(rs)
            self.log(f"  Root强化完成")

        v1 = self.adb("settings get secure enable_mock_location")[0]
        v2 = self.adb("settings get global enable_mock_location")[0]
        v3 = self.adb("cmd location is-location-enabled")[0]
        v4 = self.adb("cmd location is-provider-enabled gps")[0]
        v5 = self.adb("cmd location list-test-providers")[0]
        self.log(f"  验证: mock_sec={v1} mock_glb={v2} loc={v3} gps_prov={v4}")
        self.log(f"  Test Providers: {v5[:80]}")
        self.log("🔧 准备完成\n")

    # ===================== Inject =====================
    def inject_fast(self, lat, lng, alt=50.0, speed_kmh=5.0, bearing=0.0):
        lat_r = round(lat, 8)
        lng_r = round(lng, 8)
        speed_ms = speed_kmh / 3.6
        acc = random.uniform(4.0, 8.0)
        alt_j = alt + random.uniform(-2, 2)

        script_parts = [
            f"cmd location set-test-provider-location gps {lat_r} {lng_r} {alt_j:.1f} {acc:.1f} {speed_ms:.3f} {bearing:.1f}",
            f"cmd location set-test-provider-location network {lat_r} {lng_r} {alt_j:.1f} {acc:.1f} {speed_ms:.3f} {bearing:.1f}",
            f"cmd location inject-location gps {lat_r} {lng_r} {alt_j:.1f} {acc:.1f} {speed_ms:.3f} {bearing:.1f}",
            f"cmd location inject-location network {lat_r} {lng_r} {alt_j:.1f} {acc:.1f} {speed_ms:.3f} {bearing:.1f}",
            f"cmd location set-location gps {lat_r} {lng_r} {acc:.1f}",
            f"cmd location set-location network {lat_r} {lng_r} {acc:.1f}",
            f"am broadcast -a android.location.GPS_FIX_CHANGED --es latitude {lat_r} --es longitude {lng_r} --ef accuracy {acc:.1f}",
            f"am broadcast -a android.location.PROVIDERS_CHANGED --ez extras true",
        ]

        if self.chk_sat.get():
            sats = []
            for _ in range(random.randint(9, 14)):
                prn = random.choice([random.randint(1, 32), random.randint(120, 137), random.randint(200, 220)])
                sats.append(f"{prn},{random.uniform(22, 42):.1f},{random.uniform(20, 80):.1f},{random.uniform(0, 360):.1f}")
            script_parts.append(f"am broadcast -a android.location.GPS_SATELLITE_INFO --es satellites '|'.join(sats)")

        if self.has_root:
            script_parts.append(f"su -c 'cmd location set-test-provider-location gps {lat_r} {lng_r} {alt_j:.1f} {acc:.1f} {speed_ms:.3f} {bearing:.1f}'")

        script = " && ".join(script_parts)

        for _ in range(3):
            self.adb(script)
            time.sleep(0.05)

        return True

    # ===================== Route =====================
    @staticmethod
    def haversine(lat1, lng1, lat2, lng2):
        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def bearing(lat1, lng1, lat2, lng2):
        r1, r2 = math.radians(lat1), math.radians(lat2)
        dl = math.radians(lng2 - lng1)
        y = math.sin(dl) * math.cos(r2)
        x = math.cos(r1) * math.sin(r2) - math.sin(r1) * math.cos(r2) * math.cos(dl)
        return (math.degrees(math.atan2(y, x)) + 360) % 360

    def make_route(self, lat, lng, dist_km, route_type):
        pts = []
        total_m = dist_km * 1000
        seg_deg = 5.5 / 111000.0

        if route_type == "circle":
            r_deg = (total_m / (2 * math.pi)) / 111000.0
            n = max(60, int(2 * math.pi * r_deg / seg_deg))
            for i in range(n + 1):
                a = (i / n) * 2 * math.pi
                pts.append((lat + r_deg * math.cos(a), lng + r_deg * math.sin(a) / math.cos(math.radians(lat))))
        elif route_type == "figure8":
            r_deg = (total_m / (4 * math.pi)) / 111000.0
            n = max(80, int(8 * math.pi * r_deg / seg_deg))
            for i in range(n + 1):
                t = (i / n) * 2 * math.pi
                pts.append((lat + r_deg * math.sin(t) * 0.5, lng + r_deg * math.sin(2 * t) / math.cos(math.radians(lat))))
        elif route_type == "zigzag":
            side_d = (total_m / 2) / 111000.0
            n = max(60, int(side_d * 4 / seg_deg))
            for i in range(n + 1):
                t = i / n
                if t < 0.25: pl, pn = lat, lng + side_d * (t / 0.25) / math.cos(math.radians(lat))
                elif t < 0.5: pl, pn = lat + side_d * ((t - 0.25) / 0.25), lng + side_d / math.cos(math.radians(lat))
                elif t < 0.75: pl, pn = lat + side_d, lng + side_d * (1 - (t - 0.5) / 0.25) / math.cos(math.radians(lat))
                else: pl, pn = lat + side_d * (1 - (t - 0.75) / 0.25), lng
                pts.append((pl, pn))
        elif route_type == "outbound":
            half = (total_m / 2) / 111000.0
            n = max(50, int(half * 2 / seg_deg))
            for i in range(n + 1):
                t = i / n
                pts.append((lat + half * (t / 0.5 if t <= 0.5 else (1 - (t - 0.5) / 0.5)), lng))
        return pts

    # ===================== Test =====================
    def test_single_inject(self):
        if not self.device_id:
            messagebox.showwarning("提示", "请先扫描！"); return
        try:
            lat = float(self.lat_var.get())
            lng = float(self.lng_var.get())
        except:
            messagebox.showerror("错误", "经纬度有误"); return

        self.log(f"\n🧪 === 注入测试 ===")
        self.prepare()

        self.inject_fast(lat, lng, speed_kmh=0.0, bearing=0.0)
        self.log(f"  注入起点: ({lat}, {lng})")
        time.sleep(1.0)

        lat2 = lat + 0.00045
        lng2 = lng
        brg = self.bearing(lat, lng, lat2, lng2)
        self.inject_fast(lat2, lng2, speed_kmh=5.0, bearing=brg)
        self.log(f"  注入第二点: ({lat2}, {lng2}) bearing={brg:.0f}°")
        time.sleep(1.5)

        self.log("🔍 回读:")
        for name, cmd in [
            ("test-gps", "cmd location get-test-provider-location gps"),
            ("cmd-gps", "cmd location get-location gps"),
            ("cmd-net", "cmd location get-location network"),
            ("setting", "settings get secure last_location"),
            ("provider", "cmd location list-test-providers"),
        ]:
            out, err, c = self.adb(cmd)
            self.log(f"  {name}: {out or err[:60]}")

        out, _, _ = self.adb("dumpsys location")
        interesting = [l for l in out.split("\n") if any(k in l.lower() for k in ["location", "gps", "last", "mock", "client"])]
        if interesting:
            self.log(f"  dumpsys关键行:")
            for line in interesting[:10]:
                self.log(f"    > {line.strip()[:120]}")

        self.log("🧪 === 测试结束 ===\n")

    def deep_diagnose(self):
        if not self.device_id:
            self.scan(); return
        self.log("\n🔍 === 深度诊断 ===")
        cmds = [
            ("Android", "getprop ro.build.version.release"),
            ("Brand", "getprop ro.product.manufacturer"),
            ("Model", "getprop ro.product.model"),
            ("Root", "su -c 'id'"),
            ("Location Mode", "settings get secure location_mode"),
            ("Mock Secure", "settings get secure enable_mock_location"),
            ("Mock Global", "settings get global enable_mock_location"),
            ("Location Enabled", "cmd location is-location-enabled"),
            ("GPS Provider", "cmd location is-provider-enabled gps"),
            ("Net Provider", "cmd location is-provider-enabled network"),
            ("Test Providers", "cmd location list-test-providers"),
            ("Test Provider GPS", "cmd location get-test-provider-location gps"),
            ("Test Provider Net", "cmd location get-test-provider-location network"),
            ("Active Providers", "cmd location get-active-providers"),
            ("GPS Last", "cmd location get-location gps"),
            ("Net Last", "cmd location get-location network"),
            ("Screen", "dumpsys power | grep 'Display Power' | head -1"),
        ]
        for name, cmd in cmds:
            out, err, code = self.adb(cmd, timeout=8)
            val = out if out else (err[:80] if err else "(empty)")
            self.log(f"  {name}: {val}")
        self.log("🔍 === 诊断结束 ===\n")

    # ===================== Get Loc =====================
    def get_loc(self):
        if not self.device_id:
            messagebox.showwarning("提示", "请先连接！"); return
        self.log("尝试获取当前位置...")
        for cmd in ["cmd location get-location gps", "cmd location get-location network",
                     "cmd location get-test-provider-location gps"]:
            out, _, _ = self.adb(cmd)
            nums = re.findall(r'-?\d+\.\d+', out)
            if len(nums) >= 2:
                self.lat_var.set(nums[0]); self.lng_var.set(nums[1])
                self.log(f"✅ 成功: {nums[0]}, {nums[1]}")
                return
        out, _, _ = self.adb("dumpsys location")
        for line in out.split("\n"):
            nums = re.findall(r'-?\d+\.\d+', line)
            if len(nums) >= 2 and -90 <= float(nums[0]) <= 90 and -180 <= float(nums[1]) <= 180:
                self.lat_var.set(nums[0]); self.lng_var.set(nums[1])
                self.log(f"✅ dumpsys成功: {nums[0]}, {nums[1]}"); return
        self.log("❌ 自动获取失败")

    # ===================== Run =====================
    def start_run(self):
        if not self.device_id:
            messagebox.showwarning("提示", "请先扫描！"); return
        try:
            lat = float(self.lat_var.get())
            lng = float(self.lng_var.get())
            dist = float(self.dist_var.get())
            spd = float(self.speed_var.get())
            interval = float(self.interval_var.get())
        except ValueError:
            messagebox.showerror("错误", "参数有误！"); return
        if dist <= 0 or spd <= 0 or interval <= 0:
            messagebox.showerror("错误", "参数必须 > 0"); return

        self.base_lat, self.base_lng = lat, lng
        self.target_distance, self.speed, self.interval = dist, spd, interval
        self.route_type = self.route_var.get()

        self.log(f"=== 开始刷步: {dist}km @ {spd}km/h, 间隔{interval}s ===")
        self.prepare()

        self.total_points = 0
        self.covered_points = 0
        self.step_count = 0
        self.start_time = time.time()
        self.running = True

        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)

        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        route = self.make_route(self.base_lat, self.base_lng, self.target_distance, self.route_type)
        self.total_points = len(route)
        self.root.after(0, lambda: self.prog.configure(value=0))

        cum = 0.0
        pl, pn = self.base_lat, self.base_lng
        cnt = 0

        self.inject_fast(self.base_lat, self.base_lng, speed_kmh=0.0, bearing=0.0)
        time.sleep(1.0)

        if len(route) > 0:
            l1, n1 = route[0]
            d = self.haversine(pl, pn, l1, n1)
            b = self.bearing(pl, pn, l1, n1)
            sp = max(2.0, min(12.0, (d / max(self.interval, 0.1)) * 3.6 * random.uniform(0.9, 1.1)))
            self.inject_fast(l1, n1, speed_kmh=sp, bearing=b)
            cnt += 1; pl, pn = l1, n1; cum += d; self.covered_points = 1
            time.sleep(self.interval)

        for i in range(1, len(route)):
            if not self.running: break
            lat, lng = route[i]
            d = self.haversine(pl, pn, lat, lng)
            b = self.bearing(pl, pn, lat, lng)
            sp = (d / max(self.interval, 0.1)) * 3.6
            if random.random() < 0.2: sp *= random.uniform(0.7, 1.3)
            else: sp *= random.uniform(0.9, 1.1)
            sp = max(2.0, min(12.0, sp))
            b = (b + random.uniform(-5, 5) + 360) % 360

            self.inject_fast(lat, lng, speed_kmh=sp, bearing=b)
            cnt += 1

            if self.chk_wake.get() and cnt % 15 == 0:
                self.adb("svc power stayon true && input keyevent 82")

            cum += d; pl, pn = lat, lng
            self.covered_points = i + 1
            self.step_count = int(cum / 0.7)

            el = time.time() - self.start_time
            avg = (cum / el) * 3.6 if el > 0 else 0

            self.root.after(0, lambda dd=cum/1000, ss=self.step_count, tt=el, av=avg, cc=cnt:
                           self._ui(dd, ss, tt, av, cc))

            time.sleep(self.interval)

        if self.running:
            self.running = False
            fd = cum / 1000
            self.root.after(0, lambda: self._done(fd))

    def _ui(self, d, s, t, avg, c):
        self.dl.configure(text=f"{d:.2f} km")
        self.sl.configure(text=f"{s}")
        m = int(t) // 60; s2 = int(t) % 60
        self.tl.configure(text=f"{m:02d}:{s2:02d}")
        self.cl.configure(text=f"{avg:.1f} km/h")
        pct = (self.covered_points / self.total_points * 100) if self.total_points > 0 else 0
        self.prog.configure(value=pct)
        self.pl.configure(text=f"进度：{pct:.1f}%  |  注入 {c} 次")

    def _done(self, fd):
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.prog.configure(value=100)
        self.pl.configure(text=f"✅ 完成！总距离 {fd:.2f} km")
        self.log(f"=== 完成: {fd:.2f}km ~{self.step_count}步 ===")
        messagebox.showinfo("完成", f"刷步完成！\n\n总距离：{fd:.2f} km\n步数：~{self.step_count}")

    def stop_run(self):
        self.running = False
        self.adb("svc power stayon false && settings put secure enable_mock_location 0 && settings put global enable_mock_location 0")
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.pl.configure(text="已停止")
        self.log("=== 停止 ===")


def main():
    import traceback
    try:
        root = tk.Tk()
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
        UltraGPSRunner(root)
        root.mainloop()
    except Exception as e:
        err = traceback.format_exc()
        try:
            import tkinter.messagebox as mb
            mb.showerror("启动失败", f"{e}\n\n{err}")
        except:
            print(err)
        input("按回车退出...")

if __name__ == "__main__":
    main()