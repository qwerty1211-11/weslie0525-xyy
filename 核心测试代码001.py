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


class FastGPSRunner:
    def __init__(self, root):
        self.root = root
        self.root.title("校园跑自动刷步数 Ultra Pro - 步道乐跑/闪动校园")
        self.root.geometry("820x780")
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
        self.interval = 2
        self.route_type = "circle"

        self.total_points = 0
        self.covered_points = 0
        self.start_time = None
        self.step_count = 0
        self.gps_seq = 0

        self.setup_ui()

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="🏃 校园跑自动刷步数 Ultra Pro",
                  font=("Microsoft YaHei", 15, "bold")).pack(pady=(0, 2))
        ttk.Label(main_frame, text="步道乐跑 / 闪动校园  |  极速单调用注入 + 卫星模拟 + 反检测",
                  foreground="#888", font=("Microsoft YaHei", 9)).pack(pady=(0, 10))

        # Device
        dev_frame = ttk.LabelFrame(main_frame, text="① 设备诊断", padding=8)
        dev_frame.pack(fill=tk.X, pady=3)
        r = ttk.Frame(dev_frame); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text="设备：", width=6).pack(side=tk.LEFT)
        self.device_var = tk.StringVar(value="❌ 未连接")
        ttk.Label(r, textvariable=self.device_var, foreground="#F44336").pack(side=tk.LEFT, padx=4)
        ttk.Button(r, text="🔄 扫描", command=self.scan_device).pack(side=tk.LEFT, padx=4)
        ttk.Button(r, text="🔍 完整诊断", command=self.full_diagnose).pack(side=tk.LEFT, padx=4)

        r2 = ttk.Frame(dev_frame); r2.pack(fill=tk.X, pady=2)
        ttk.Label(r2, text="ADB：", width=6).pack(side=tk.LEFT)
        self.adb_var = tk.StringVar(value="adb")
        ttk.Entry(r2, textvariable=self.adb_var, width=28).pack(side=tk.LEFT, padx=4)
        ttk.Label(r2, text="Android:").pack(side=tk.LEFT, padx=(10, 2))
        self.android_ver_var = tk.StringVar(value="-")
        ttk.Label(r2, textvariable=self.android_ver_var, foreground="#2196F3").pack(side=tk.LEFT)
        ttk.Label(r2, text=" Root:").pack(side=tk.LEFT, padx=(10, 2))
        self.root_var = tk.StringVar(value="❌")
        ttk.Label(r2, textvariable=self.root_var).pack(side=tk.LEFT)
        self.brand_var = tk.StringVar(value="")
        ttk.Label(r2, text="  设备:", foreground="#666").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Label(r2, textvariable=self.brand_var, foreground="#666").pack(side=tk.LEFT)

        # Config
        cfg = ttk.LabelFrame(main_frame, text="② 跑步参数", padding=8)
        cfg.pack(fill=tk.X, pady=3)

        g1 = ttk.Frame(cfg); g1.pack(fill=tk.X, pady=2)
        ttk.Label(g1, text="纬度：", width=6).pack(side=tk.LEFT)
        self.lat_var = tk.StringVar(value=str(self.base_lat))
        ttk.Entry(g1, textvariable=self.lat_var, width=13).pack(side=tk.LEFT, padx=2)
        ttk.Label(g1, text="经度：", width=6).pack(side=tk.LEFT, padx=(10, 0))
        self.lng_var = tk.StringVar(value=str(self.base_lng))
        ttk.Entry(g1, textvariable=self.lng_var, width=13).pack(side=tk.LEFT, padx=2)
        ttk.Button(g1, text="📍获取当前位置", command=self.get_current_location).pack(side=tk.LEFT, padx=6)

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
        self.chk_keep_screen = tk.BooleanVar(value=True)
        ttk.Checkbutton(g3, text="保持亮屏", variable=self.chk_keep_screen).pack(side=tk.LEFT, padx=10)
        self.chk_wake = tk.BooleanVar(value=True)
        ttk.Checkbutton(g3, text="定期唤醒", variable=self.chk_wake).pack(side=tk.LEFT, padx=3)
        self.chk_satellite = tk.BooleanVar(value=True)
        ttk.Checkbutton(g3, text="模拟GPS卫星", variable=self.chk_satellite).pack(side=tk.LEFT, padx=3)

        # Status
        st = ttk.LabelFrame(main_frame, text="③ 运行状态", padding=8)
        st.pack(fill=tk.X, pady=3)
        st_row = ttk.Frame(st); st_row.pack(fill=tk.X)
        for i, label in enumerate(["模拟步数", "已跑距离", "用时", "当前速度"]):
            ttk.Label(st_row, text=label, font=("Microsoft YaHei", 9)).grid(row=0, column=i, padx=18)
        self.step_lbl = ttk.Label(st_row, text="0 步", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.step_lbl.grid(row=1, column=0, padx=18)
        self.dist_lbl = ttk.Label(st_row, text="0.00 km", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.dist_lbl.grid(row=1, column=1, padx=18)
        self.time_lbl = ttk.Label(st_row, text="00:00", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.time_lbl.grid(row=1, column=2, padx=18)
        self.curr_speed_lbl = ttk.Label(st_row, text="0.0 km/h", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.curr_speed_lbl.grid(row=1, column=3, padx=18)

        self.prog = ttk.Progressbar(st, mode="determinate")
        self.prog.pack(fill=tk.X, pady=(8, 2))
        self.prog_lbl = ttk.Label(st, text="进度：0%")
        self.prog_lbl.pack(anchor=tk.W)

        btns = ttk.Frame(main_frame); btns.pack(fill=tk.X, pady=5)
        self.start_btn = ttk.Button(btns, text="▶ 开始刷步", command=self.start_run)
        self.start_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.stop_btn = ttk.Button(btns, text="■ 停止", command=self.stop_run, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.test_btn = ttk.Button(btns, text="🧪 测试GPS", command=self.test_gps)
        self.test_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        logf = ttk.LabelFrame(main_frame, text="④ 实时日志", padding=5)
        logf.pack(fill=tk.BOTH, expand=True, pady=3)
        self.log_box = scrolledtext.ScrolledText(logf, height=8, font=("Consolas", 9), state=tk.DISABLED)
        self.log_box.pack(fill=tk.BOTH, expand=True)

        tip = ttk.Label(main_frame,
                        text="⚠️ 开发者选项 → 允许USB调试 ✅  → 允许模拟位置 ✅  → 允许USB模拟定位 ✅  → 选择本程序为模拟位置应用 ⚠️",
                        foreground="#E65100", font=("Microsoft YaHei", 9), wraplength=790, justify=tk.LEFT)
        tip.pack(pady=(5, 0))

        self.scan_device()

    # ===================== Fast ADB =====================
    def adb(self, shell_cmd, timeout=12):
        """合并 adb shell 调用 - 一次执行多条"""
        adb_exe = self.adb_var.get().strip() or "adb"
        target = f"-s {self.device_id} " if self.device_id else ""
        full = f"{adb_exe} {target}shell {shell_cmd}"
        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == "nt" else None
            if startupinfo:
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=timeout, startupinfo=startupinfo)
            return r.stdout.strip(), r.stderr.strip(), r.returncode
        except subprocess.TimeoutExpired:
            return "", "TIMEOUT", -1
        except FileNotFoundError:
            return "", f"找不到adb: {adb_exe}", -1
        except Exception as e:
            return "", str(e), -1

    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, line)
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    # ===================== Scan =====================
    def scan_device(self):
        adb_exe = self.adb_var.get().strip() or "adb"
        try:
            startupinfo = subprocess.STARTUPINFO() if os.name == "nt" else None
            if startupinfo:
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            r = subprocess.run(f"{adb_exe} devices", shell=True, capture_output=True, text=True, timeout=10, startupinfo=startupinfo)
            lines = [l for l in r.stdout.strip().split("\n") if l.strip()]
            devs = [l for l in lines[1:] if "\tdevice" in l and "unauthorized" not in l]
            if devs:
                self.device_id = devs[0].split("\t")[0]
                self.device_var.set(f"✅ {self.device_id}")
                self.android_version = self._get("getprop ro.build.version.release")
                self.android_ver_var.set(f"{self.android_version}")
                self.brand = self._get("getprop ro.product.manufacturer")
                self.model = self._get("getprop ro.product.model")
                self.brand_var.set(f"{self.brand} {self.model}")
                self.has_root = self._check_root()
                self.root_var.set("✅" if self.has_root else "❌")
                self.log(f"设备连接: {self.device_id}, Android {self.android_version}, {self.brand} {self.model}, Root={self.has_root}")
                self._prepare_device()
            else:
                self.device_id = None
                self.device_var.set("❌ 未检测到设备")
        except Exception as e:
            self.device_id = None
            self.device_var.set("❌ ADB错误")
            self.log(f"ADB扫描失败: {e}")

    def _get(self, prop):
        out, _, _ = self.adb(prop)
        return out if out else "未知"

    def _check_root(self):
        out, _, code = self.adb("su -c 'id'")
        return code == 0 and "uid=0" in out

    # ===================== Prepare =====================
    def _prepare_device(self):
        """一次性 shell 调用完成所有准备"""
        self.log("🔧 准备设备环境 (单次调用)...")

        # ===== 合并成一条命令 =====
        script = " && ".join([
            # Mock location 核心开关
            "settings put global adb_enabled 1",
            "settings put global enable_mock_location 1",
            "settings put secure enable_mock_location 1",
            "settings put secure location_mode 3",
            "settings put secure location_providers_allowed gps,network",
            # appops
            "appops set 20010 MOCK_LOCATION allow",
            "appops set 10630 MOCK_LOCATION allow",
            # Location 强制启用
            "cmd location set-location-enabled true gps",
            "cmd location set-location-enabled true network",
            # 先清理旧的 test provider
            "cmd location remove-test-provider gps 2>/dev/null",
            "cmd location remove-test-provider network 2>/dev/null",
            # 创建新的 test provider
            "cmd location add-test-provider gps enabled true has-monitors true",
            "cmd location add-test-provider network enabled true has-monitors true",
            # 亮屏
            "svc power stayon true",
        ])

        # 厂商特化
        brand_lower = self.brand.lower()
        if any(x in brand_lower for x in ["xiaomi", "mi"]):
            script += " && " + " && ".join([
                "settings put system enable_mock_location 1",
                "settings put global miui_opt_switch 1",
            ])
        if any(x in brand_lower for x in ["huawei", "honor"]):
            script += " && " + " && ".join([
                "settings put secure enable_hw_location_simulate 1",
                "settings put global enable_hw_location_simulate 1",
            ])
        if any(x in brand_lower for x in ["oppo", "realme", "oneplus"]):
            script += " && settings put oppo_enable_virtual_location 1"
        if any(x in brand_lower for x in ["vivo", "iqoo"]):
            script += " && " + " && ".join([
                "settings put secure enable_virtual_location 1",
                "settings put global enable_virtual_location 1",
            ])

        # Root 强化
        if self.has_root:
            script += " && su -c '" + " && ".join([
                "settings put secure enable_mock_location 1",
                "settings put global enable_mock_location 1",
                "cmd location set-location-enabled true gps",
            ]) + "'"

        out, err, code = self.adb(script)

        # 验证 mock location 是否生效
        verify_script = " && ".join([
            "settings get secure enable_mock_location",
            "settings get global enable_mock_location",
            "cmd location is-provider-enabled gps",
        ])
        vout, _, _ = self.adb(verify_script)
        lines = vout.split("\n")
        mock_sec = lines[0] if len(lines) > 0 else "?"
        mock_glb = lines[1] if len(lines) > 1 else "?"
        gps_ok = lines[2] if len(lines) > 2 else "?"
        self.log(f"  Mock(secure)={mock_sec}  Mock(global)={mock_glb}  GPS={gps_ok}")
        self.log("🔧 准备完成\n")

    # ===================== Inject - CORE =====================
    def inject_once(self, lat, lng, alt=50.0, speed_kmh=5.0, bearing=0.0):
        """
        极速单次注入 - 所有通道合并成一条 shell 命令
        原来 20+ 次 adb → 现在 1 次
        """
        self.gps_seq += 1
        acc = random.uniform(3.0, 10.0)
        alt_j = alt + random.uniform(-3.0, 3.0)
        lat_r = round(lat, 8)
        lng_r = round(lng, 8)
        speed_ms = speed_kmh / 3.6  # km/h → m/s

        # ===== 一次性 shell 脚本 =====
        # 核心原理: inject-location 在多数 Android 版本上不会给 Location 打 mock 标记
        script_parts = []

        # 1. inject-location (最强, 不打mock标记, Android 12+ 推荐)
        script_parts.append(
            f"cmd location inject-location gps {lat_r} {lng_r} {alt_j:.1f} {acc:.1f} {speed_ms:.3f} {bearing:.1f}"
        )
        script_parts.append(
            f"cmd location inject-location network {lat_r} {lng_r} {alt_j:.1f} {acc:.1f} {speed_ms:.3f} {bearing:.1f}"
        )

        # 2. set-test-provider-location (test provider 方式)
        script_parts.append(
            f"cmd location set-test-provider-location gps {lat_r} {lng_r} {alt_j:.1f} {acc:.1f} {speed_ms:.3f} {bearing:.1f}"
        )
        script_parts.append(
            f"cmd location set-test-provider-location network {lat_r} {lng_r} {alt_j:.1f} {acc:.1f} {speed_ms:.3f} {bearing:.1f}"
        )

        # 3. 基础 set-location
        script_parts.append(f"cmd location set-location gps {lat_r} {lng_r} {acc:.1f}")
        script_parts.append(f"cmd location set-location network {lat_r} {lng_r} {acc:.1f}")

        # 4. settings (兼容旧版)
        script_parts.append(f"settings put secure last_location {lat_r},{lng_r}")
        script_parts.append(f"settings put global last_location {lat_r},{lng_r}")

        # 5. GPS 卫星模拟 (关键! 没有卫星数据 APP 判定无效)
        if self.chk_satellite.get():
            num_sats = random.randint(8, 14)
            # 模拟真实 GPS 卫星: PRN编号 1-32 (GPS), 编号120+ (北斗), 编号200+ (GLONASS)
            sat_data_parts = []
            for _ in range(num_sats):
                prn = random.choice([
                    random.randint(1, 32),       # GPS
                    random.randint(120, 137),    # 北斗
                    random.randint(200, 220),    # GLONASS
                ])
                snr = random.uniform(20.0, 45.0)   # 信噪比 dB-Hz
                elev = random.uniform(15.0, 85.0)   # 仰角
                azim = random.uniform(0.0, 360.0)   # 方位角
                sat_data_parts.append(f"{prn},{snr:.1f},{elev:.1f},{azim:.1f}")
            sat_arg = "|".join(sat_data_parts)
            script_parts.append(
                f"am broadcast -a android.location.GPS_SATELLITE_INFO --es satellites '{sat_arg}'"
            )

        # 6. GPS Fix 变化广播
        script_parts.append(
            f"am broadcast -a android.location.GPS_FIX_CHANGED "
            f"--es latitude {lat_r} --es longitude {lng_r} --ef accuracy {acc:.1f}"
        )

        # 7. Root 强化
        if self.has_root:
            script_parts.append(
                f"su -c 'cmd location inject-location gps {lat_r} {lng_r} {alt_j:.1f} {acc:.1f} {speed_ms:.3f} {bearing:.1f}'"
            )

        # 合并执行 - 仅 1 次 adb shell 调用
        script = " && ".join(script_parts)
        self.adb(script)

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
    def calc_bearing(lat1, lng1, lat2, lng2):
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlng = math.radians(lng2 - lng1)
        y = math.sin(dlng) * math.cos(lat2_r)
        x = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlng)
        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360

    def generate_route(self, lat, lng, distance_km, route_type):
        points = []
        total_m = distance_km * 1000

        if route_type == "circle":
            r_m = total_m / (2 * math.pi)
            r_deg = r_m / 111000.0
            seg_deg = 8.0 / 111000.0
            n = max(40, int(2 * math.pi * r_deg / seg_deg))
            for i in range(n + 1):
                a = (i / n) * 2 * math.pi
                pl = lat + r_deg * math.cos(a)
                pn = lng + r_deg * math.sin(a) / math.cos(math.radians(lat))
                points.append((pl, pn))

        elif route_type == "figure8":
            r_m = total_m / (4 * math.pi)
            r_deg = r_m / 111000.0
            seg_deg = 8.0 / 111000.0
            full_deg = 8 * math.pi * r_deg
            n = max(50, int(full_deg / seg_deg))
            for i in range(n + 1):
                t = (i / n) * 2 * math.pi
                pl = lat + r_deg * math.sin(t) * 0.5
                pn = lng + r_deg * math.sin(2 * t) / math.cos(math.radians(lat))
                points.append((pl, pn))

        elif route_type == "zigzag":
            side_m = total_m / 2
            side_deg = side_m / 111000.0
            seg_deg = 8.0 / 111000.0
            n = max(40, int(side_deg * 4 / seg_deg))
            for i in range(n + 1):
                t = i / n
                if t < 0.25:
                    pl = lat
                    pn = lng + side_deg * (t / 0.25) / math.cos(math.radians(lat))
                elif t < 0.5:
                    pl = lat + side_deg * ((t - 0.25) / 0.25)
                    pn = lng + side_deg / math.cos(math.radians(lat))
                elif t < 0.75:
                    pl = lat + side_deg
                    pn = lng + side_deg * (1 - (t - 0.5) / 0.25) / math.cos(math.radians(lat))
                else:
                    pl = lat + side_deg * (1 - (t - 0.75) / 0.25)
                    pn = lng
                points.append((pl, pn))

        elif route_type == "outbound":
            half_deg = (total_m / 2) / 111000.0
            seg_deg = 8.0 / 111000.0
            n = max(30, int(half_deg * 2 / seg_deg))
            for i in range(n + 1):
                t = i / n
                if t <= 0.5:
                    pl = lat + half_deg * (t / 0.5)
                    pn = lng
                else:
                    pl = lat + half_deg * (1 - (t - 0.5) / 0.5)
                    pn = lng
                points.append((pl, pn))

        return points

    # ===================== Test =====================
    def test_gps(self):
        if not self.device_id:
            messagebox.showwarning("提示", "请先扫描连接设备！")
            return
        try:
            lat = float(self.lat_var.get())
            lng = float(self.lng_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效经纬度！")
            return

        self.log(f"🧪 === GPS注入测试 ({lat}, {lng}) ===")
        self._prepare_device()

        # 先注入一个点
        self.inject_once(lat, lng, alt=50.0, speed_kmh=0.0, bearing=0.0)
        time.sleep(0.5)

        # 注入第二个点 (模拟移动了100米)
        test_lat = lat + 0.0009  # ~100m
        test_lng = lng
        brg = self.calc_bearing(lat, lng, test_lat, test_lng)
        self.inject_once(test_lat, test_lng, alt=50.0, speed_kmh=5.0, bearing=brg)
        self.log(f"  第二点: ({test_lat}, {test_lng}), bearing={brg:.0f}°")

        time.sleep(2.0)

        # 回读
        self.log("🔍 回读验证...")
        checks = [
            ("cmd gps", "cmd location get-location gps"),
            ("cmd net", "cmd location get-location network"),
            ("secure", "settings get secure last_location"),
            ("global", "settings get global last_location"),
        ]
        for name, cmd in checks:
            out, _, _ = self.adb(cmd)
            self.log(f"  {name}: {out}")

        out_d, _, _ = self.adb("dumpsys location | head -50")
        lat_found = re.findall(r'-?\d{2,3}\.\d{4,}', out_d)
        if lat_found:
            self.log(f"  dumpsys 中发现坐标: {lat_found[:5]}")
        else:
            self.log("  dumpsys location 未解析到有效坐标")

        self.log("🧪 === 测试完成 ===\n")

    # ===================== Run / Stop =====================
    def start_run(self):
        if not self.device_id:
            messagebox.showwarning("提示", "请先扫描连接设备！")
            return
        try:
            lat = float(self.lat_var.get())
            lng = float(self.lng_var.get())
            dist = float(self.dist_var.get())
            spd = float(self.speed_var.get())
            interval = float(self.interval_var.get())
        except ValueError:
            messagebox.showerror("错误", "参数格式有误！")
            return
        if dist <= 0 or spd <= 0 or interval <= 0:
            messagebox.showerror("错误", "距离/速度/间隔必须 > 0")
            return

        self.base_lat, self.base_lng = lat, lng
        self.target_distance, self.speed, self.interval = dist, spd, interval
        self.route_type = self.route_var.get()

        self.log(f"=== 开始刷步: {dist}km @ {spd}km/h, 轨迹={self.route_type} ===")
        self._prepare_device()

        self.total_points = 0
        self.covered_points = 0
        self.step_count = 0
        self.start_time = time.time()
        self.running = True

        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)

        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        route = self.generate_route(self.base_lat, self.base_lng, self.target_distance, self.route_type)
        self.total_points = len(route)
        self.root.after(0, lambda: self.prog.configure(value=0))

        cum_dist = 0.0
        prev_lat, prev_lng = self.base_lat, self.base_lng
        gps_count = 0

        # 起点
        self.inject_once(self.base_lat, self.base_lng, alt=50.0, speed_kmh=0.0, bearing=0.0)
        time.sleep(1.0)

        # 预热第一点
        if len(route) > 0:
            p1_lat, p1_lng = route[0]
            seg_d = self.haversine(prev_lat, prev_lng, p1_lat, p1_lng)
            brg = self.calc_bearing(prev_lat, prev_lng, p1_lat, p1_lng)
            cur_spd = (seg_d / max(self.interval, 0.1)) * 3.6
            cur_spd = cur_spd * random.uniform(0.90, 1.10)
            cur_spd = max(2.0, min(12.0, cur_spd))
            brg = (brg + random.uniform(-3, 3) + 360) % 360

            self.inject_once(p1_lat, p1_lng, alt=random.uniform(45, 55), speed_kmh=cur_spd, bearing=brg)
            gps_count += 1
            prev_lat, prev_lng = p1_lat, p1_lng
            cum_dist += seg_d
            self.covered_points = 1
            time.sleep(self.interval)

        # 主循环
        for i in range(1, len(route)):
            if not self.running:
                break

            plat, plng = route[i]
            seg_d = self.haversine(prev_lat, prev_lng, plat, plng)
            brg = self.calc_bearing(prev_lat, prev_lng, plat, plng)
            cur_spd = (seg_d / max(self.interval, 0.1)) * 3.6

            if random.random() < 0.2:
                cur_spd *= random.uniform(0.70, 1.30)
            else:
                cur_spd *= random.uniform(0.90, 1.10)
            cur_spd = max(2.0, min(12.0, cur_spd))
            brg = (brg + random.uniform(-5, 5) + 360) % 360

            self.inject_once(plat, plng, alt=random.uniform(45, 55), speed_kmh=cur_spd, bearing=brg)
            gps_count += 1

            # 定期保持亮屏和唤醒 (每 ~10 次)
            if self.chk_keep_screen.get() and gps_count % 10 == 0:
                self.adb("svc power stayon true && input keyevent 82")

            cum_dist += seg_d
            prev_lat, prev_lng = plat, plng
            self.covered_points = i + 1
            self.step_count = int(cum_dist / 0.7)

            elapsed = time.time() - self.start_time
            avg_speed = (cum_dist / elapsed) * 3.6 if elapsed > 0 else 0

            self.root.after(0, lambda d=cum_dist/1000, s=self.step_count, t=elapsed,
                                   cs=cur_spd, as_=avg_speed, g=gps_count:
                            self._update_ui(d, s, t, cs, as_, g))

            time.sleep(self.interval)

        if self.running:
            self.running = False
            final_d = cum_dist / 1000
            self.root.after(0, lambda: self._finish(final_d))

    def _update_ui(self, dist, steps, elapsed, cur_speed, avg_speed, gps_count):
        self.dist_lbl.configure(text=f"{dist:.2f} km")
        self.step_lbl.configure(text=f"{steps} 步")
        m = int(elapsed) // 60
        s = int(elapsed) % 60
        self.time_lbl.configure(text=f"{m:02d}:{s:02d}")
        self.curr_speed_lbl.configure(text=f"{avg_speed:.1f} km/h")
        pct = (self.covered_points / self.total_points * 100) if self.total_points > 0 else 0
        self.prog.configure(value=pct)
        self.prog_lbl.configure(text=f"进度：{pct:.1f}%  |  GPS注入 {gps_count} 次  |  均速 {avg_speed:.1f} km/h")

    def _finish(self, final_dist):
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.prog.configure(value=100)
        self.prog_lbl.configure(text=f"✅ 完成！总距离 {final_dist:.2f} km")
        self.log(f"=== 完成: {final_dist:.2f}km, ~{self.step_count}步 ===")
        messagebox.showinfo("完成", f"🎉 刷步完成！\n\n总距离：{final_dist:.2f} km\n模拟步数：~{self.step_count} 步")

    def stop_run(self):
        self.running = False
        self.adb("svc power stayon false && settings put secure enable_mock_location 0 && settings put global enable_mock_location 0")
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.prog_lbl.configure(text="已停止")
        self.log("=== 手动停止 ===")

    def full_diagnose(self):
        self.log("=== 完整诊断 ===")
        self.scan_device()
        if not self.device_id:
            return
        checks = [
            ("Android版本", "getprop ro.build.version.release"),
            ("手机品牌", "getprop ro.product.manufacturer"),
            ("手机型号", "getprop ro.product.model"),
            ("Location模式", "settings get secure location_mode"),
            ("Mock(global)", "settings get global enable_mock_location"),
            ("Mock(secure)", "settings get secure enable_mock_location"),
            ("GPS启用", "cmd location is-provider-enabled gps"),
            ("Network启用", "cmd location is-provider-enabled network"),
            ("Location开关", "cmd location is-location-enabled"),
            ("Screen状态", "dumpsys power | grep 'Display Power' | head -1"),
            ("Test Provider", "cmd location list-test-providers"),
        ]
        for name, cmd in checks:
            out, err, _ = self.adb(cmd)
            self.log(f"  {name}: {out or err[:60]}")
        self.log("=== 诊断完成 ===\n")

    def get_current_location(self):
        if not self.device_id:
            messagebox.showwarning("提示", "请先扫描连接设备！")
            return
        self.log("尝试获取当前位置...")
        # 尝试多个来源
        for cmd in ["cmd location get-location gps", "cmd location get-location network"]:
            out, _, _ = self.adb(cmd)
            if out:
                nums = re.findall(r'-?\d+\.\d+', out)
                if len(nums) >= 2:
                    self.lat_var.set(nums[0])
                    self.lng_var.set(nums[1])
                    self.log(f"✅ 获取成功: {nums[0]}, {nums[1]} (from {cmd})")
                    return
        # dumpsys fallback
        out, _, _ = self.adb("dumpsys location")
        for line in out.split("\n"):
            l = line.lower()
            if "latitude" in l or "last location" in l:
                nums = re.findall(r'-?\d+\.\d+', line)
                if len(nums) >= 2:
                    self.lat_var.set(nums[0])
                    self.lng_var.set(nums[1])
                    self.log(f"✅ dumpsys获取成功: {nums[0]}, {nums[1]}")
                    return
        self.log("❌ 自动获取失败，请手动输入经纬度")


def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    FastGPSRunner(root)
    root.mainloop()


if __name__ == "__main__":
    main()