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
import struct
import queue


class AdbConnection:
    """常驻 adb shell 通道（端到端实时性的关键）。

    旧实现每发一条指令都 subprocess 启动一次 adb 进程，一个轨迹点约15条指令，
    累计延迟常达数秒，手机端收点间隔被拉长 -> APP按真实时间判定速度异常 -> 丢点。
    这里保持一个常驻 shell：
      - 所有命令写入同一条管道，无进程反复启动开销；
      - 每条脚本末尾追加 echo 标记，阻塞读到标记才算“手机已执行完”，形成 ACK；
      - 超时自动杀掉重连，防止管道失步后所有点静默失败。
    """

    def __init__(self, adb_exe, device_id, log_fn=None):
        self.adb_exe = adb_exe
        self.device_id = device_id
        self.log_fn = log_fn
        self.proc = None
        self.q = None
        self.reader = None
        self.lock = threading.Lock()
        self.seq = 0
        self.alive = False
        self._start_locked()

    def _spawn(self):
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.proc = subprocess.Popen(
            [self.adb_exe, "-s", self.device_id, "shell"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            startupinfo=startupinfo,
        )
        self.q = queue.Queue()
        self.reader = threading.Thread(target=self._reader_loop, daemon=True)
        self.reader.start()

    def _reader_loop(self):
        try:
            for line in self.proc.stdout:
                self.q.put(line)
        except (ValueError, OSError):
            pass
        finally:
            self.q.put(None)

    def _collect_locked(self, script, marker, timeout):
        """写入脚本并读取到 marker 行。返回 (marker之前的输出, marker行或None)。"""
        try:
            self.proc.stdin.write(script + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError):
            return "", None
        lines = []
        end = time.time() + timeout
        while True:
            remain = end - time.time()
            if remain <= 0:
                return "\n".join(lines), None
            try:
                line = self.q.get(timeout=remain)
            except queue.Empty:
                return "\n".join(lines), None
            if line is None:
                return "\n".join(lines), None
            s = line.strip()
            if s == marker or s.startswith(marker + ":"):
                return "\n".join(lines), s
            lines.append(s)

    def _start_locked(self):
        try:
            self._spawn()
        except Exception as e:
            self.alive = False
            if self.log_fn:
                self.log_fn(f"持久ADB shell启动失败: {e}")
            return False
        _, hit = self._collect_locked("echo __ADB_PING__", "__ADB_PING__", 8)
        self.alive = hit is not None
        if not self.alive and self.log_fn:
            self.log_fn("⚠️ 持久ADB shell握手失败，将退回兼容模式（实时性较差）")
        return self.alive

    def _restart_locked(self):
        try:
            self.proc.kill()
            self.proc.wait(timeout=2)
        except Exception:
            pass
        self._start_locked()

    def execute(self, script, timeout=10):
        """执行一段 shell 脚本（可含 ; 串联多条命令），阻塞到手机执行完。

        返回 (输出文本, returncode)；rc=-2 表示超时/断连（已尝试重连）。
        """
        with self.lock:
            if not self.alive:
                self._restart_locked()
            if not self.alive:
                return "", -1
            self.seq += 1
            marker = f"__ADB_ACK_{self.seq}__"
            out, hit = self._collect_locked(script + f"; echo {marker}:$?", marker, timeout)
            if hit is None:
                self._restart_locked()
                return out, -2
            try:
                rc = int(hit.split(":")[-1])
            except ValueError:
                rc = -1
            return out, rc

    def close(self):
        with self.lock:
            self.alive = False
            try:
                if self.proc:
                    self.proc.kill()
            except Exception:
                pass


class EnhancedGPSRunner:
    def __init__(self, root):
        self.root = root
        self.root.title("校园跑自动刷步数 Pro - 步道乐跑/闪动校园")
        self.root.geometry("860x1000")
        self.root.minsize(820, 780)
        self.root.resizable(True, True)

        self.running = False
        self.thread = None
        self.device_id = None
        self.android_version = None
        self.has_root = False
        self.use_sensor_sim = True
        self.use_accel_sim = True
        # 常驻ADB通道：所有实时注入走它，避免逐指令起进程造成延迟和丢点
        self.adb_conn = None

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

        self.target_app = ""
        self.last_app_ping = 0
        self.setup_ui()
    # ===================== UI =====================
    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(main_frame, text="🏃 校园跑自动刷步数 Pro",
                  font=("Microsoft YaHei", 15, "bold")).pack(pady=(0, 2))
        ttk.Label(main_frame, text="步道乐跑 / 闪动校园  |  多通道GPS注入 + 传感器模拟",
                  foreground="#888", font=("Microsoft YaHei", 9)).pack(pady=(0, 10))
        # === Device Panel ===
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
        ttk.Label(r2, text="Android：").pack(side=tk.LEFT, padx=(10, 2))
        self.android_ver_var = tk.StringVar(value="-")
        ttk.Label(r2, textvariable=self.android_ver_var, foreground="#2196F3").pack(side=tk.LEFT)
        ttk.Label(r2, text="  Root：").pack(side=tk.LEFT, padx=(10, 2))
        self.root_var = tk.StringVar(value="❌")
        ttk.Label(r2, textvariable=self.root_var).pack(side=tk.LEFT)
        # === Config Panel ===
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
        ttk.Label(g3, text="  GPS方式：", width=10).pack(side=tk.LEFT)
        self.gps_mode_var = tk.StringVar(value="auto")
        ttk.Combobox(g3, textvariable=self.gps_mode_var, width=18, state="readonly",
                     values=["auto (自动选择最佳)", "service_call (底层服务调用)",
                             "cmd_location (ADB新命令)", "provider (数据提供者)",
                             "all (全部通道同时注入)"]).pack(side=tk.LEFT, padx=2)
        g4 = ttk.Frame(cfg); g4.pack(fill=tk.X, pady=2)
        self.chk_keep_screen = tk.BooleanVar(value=True)
        ttk.Checkbutton(g4, text="保持屏幕常亮", variable=self.chk_keep_screen).pack(side=tk.LEFT, padx=3)
        self.chk_wake = tk.BooleanVar(value=True)
        ttk.Checkbutton(g4, text="点亮屏幕解锁", variable=self.chk_wake).pack(side=tk.LEFT, padx=3)
        self.chk_accel = tk.BooleanVar(value=True)
        ttk.Checkbutton(g4, text="模拟加速度传感器", variable=self.chk_accel).pack(side=tk.LEFT, padx=3)
        self.chk_gyro = tk.BooleanVar(value=False)
        ttk.Checkbutton(g4, text="模拟陀螺仪", variable=self.chk_gyro).pack(side=tk.LEFT, padx=3)
        self.chk_press = tk.BooleanVar(value=True)
        ttk.Checkbutton(g4, text="定期唤醒APP（点击模拟）", variable=self.chk_press).pack(side=tk.LEFT, padx=3)

        g5 = ttk.Frame(cfg); g5.pack(fill=tk.X, pady=2)
        ttk.Label(g5, text="跑步APP包名：", width=14).pack(side=tk.LEFT)
        self.app_pkg_var = tk.StringVar(value="com.lexiangpao.app")
        ttk.Entry(g5, textvariable=self.app_pkg_var, width=30).pack(side=tk.LEFT, padx=2)
        self.known_apps = {
            "com.lptiyu.tanke": "运动世界校园",
            "com.lexiangpao.app": "步道乐跑",
            "com.qufenghudong.run": "闪动校园 / 校园跑",
            "com.huajunsf.hjex": "华军校园跑",
            "com.xsyd.run": "新赛道",
        }
        app_names = list(self.known_apps.keys())
        self.app_combo = ttk.Combobox(g5, values=app_names, width=20, state="readonly")
        self.app_combo.set(app_names[0])
        self.app_combo.pack(side=tk.LEFT, padx=4)
        self.app_combo.bind("<<ComboboxSelected>>", lambda e: self.app_pkg_var.set(self.app_combo.get()))
        ttk.Button(g5, text="📋 列出已装APP", command=self.list_installed_running_apps).pack(side=tk.LEFT, padx=4)
        ttk.Button(g5, text="▶ 启动APP", command=self.launch_target_app).pack(side=tk.LEFT, padx=4)

        g6 = ttk.Frame(cfg); g6.pack(fill=tk.X, pady=2)
        self.chk_verify = tk.BooleanVar(value=True)
        ttk.Checkbutton(g6, text="逐点读回确认（手机确认接收后才计进度，强烈建议开启）",
                        variable=self.chk_verify).pack(side=tk.LEFT, padx=3)
        self.chk_uiauto = tk.BooleanVar(value=True)
        ttk.Checkbutton(g6, text="每30秒读取手机APP显示的成绩",
                        variable=self.chk_uiauto).pack(side=tk.LEFT, padx=3)

        # === Status ===
        st = ttk.LabelFrame(main_frame, text="③ 运行状态", padding=8)
        st.pack(fill=tk.X, pady=3)

        st_row = ttk.Frame(st); st_row.pack(fill=tk.X)
        for i, label in enumerate(["估算步数", "已跑距离", "用时", "当前速度"]):
            ttk.Label(st_row, text=label, font=("Microsoft YaHei", 9)).grid(row=0, column=i, padx=12)
        self.step_lbl = ttk.Label(st_row, text="0 步", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.step_lbl.grid(row=1, column=0, padx=12)
        self.dist_lbl = ttk.Label(st_row, text="0.00 km", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.dist_lbl.grid(row=1, column=1, padx=12)
        self.time_lbl = ttk.Label(st_row, text="00:00", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.time_lbl.grid(row=1, column=2, padx=12)
        self.curr_speed_lbl = ttk.Label(st_row, text="0.0 km/h", font=("Microsoft YaHei", 18, "bold"), foreground="#2196F3")
        self.curr_speed_lbl.grid(row=1, column=3, padx=12)

        self.prog = ttk.Progressbar(st, mode="determinate")
        self.prog.pack(fill=tk.X, pady=(8, 2))
        self.prog_lbl = ttk.Label(st, text="进度：0%  |  等待开始")
        self.prog_lbl.pack(anchor=tk.W)
        self.phone_var = tk.StringVar(value="📱 手机端：等待开始（开始后逐点读回确认 + 每30秒读取APP成绩）")
        ttk.Label(st, textvariable=self.phone_var, foreground="#2E7D32",
                  font=("Microsoft YaHei", 9)).pack(anchor=tk.W, pady=(1, 0))

        # === Buttons ===
        btns = ttk.Frame(main_frame); btns.pack(fill=tk.X, pady=5)
        self.start_btn = ttk.Button(btns, text="▶ 开始刷步", style="Big.TButton", command=self.start_run)
        self.start_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.stop_btn = ttk.Button(btns, text="■ 停止", style="Big.TButton", command=self.stop_run, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)
        self.test_btn = ttk.Button(btns, text="🧪 测试GPS注入", command=self.test_gps)
        self.test_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=3)

        # === Log ===
        logf = ttk.LabelFrame(main_frame, text="④ 实时日志", padding=5)
        logf.pack(fill=tk.BOTH, expand=True, pady=3)
        self.log_box = scrolledtext.ScrolledText(logf, height=8, font=("Consolas", 9), state=tk.DISABLED)
        self.log_box.pack(fill=tk.BOTH, expand=True)

        # === Tips ===
        tip = ttk.Label(main_frame,
                        text="⚠️ 请确保：开发者选项 → 允许USB调试 ✅  → 允许模拟位置 ✅  → 选择本程序(或无)  ⚠️ 部分手机需开启「允许USB模拟定位」开关",
                        foreground="#E65100", font=("Microsoft YaHei", 9), wraplength=790, justify=tk.LEFT)
        tip.pack(pady=(5, 0))

        self.scan_device()

    # ===================== ADB Helpers =====================
    def adb(self, cmd, timeout=15, show_output=False):
        adb_exe = self.adb_var.get().strip() or "adb"
        target = f"-s {self.device_id}" if self.device_id else ""
        full = f"{adb_exe} {target} {cmd}"
        try:
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=timeout, startupinfo=startupinfo)
            out, err, code = r.stdout.strip(), r.stderr.strip(), r.returncode
            if show_output and (out or err):
                self.log(f"  > {cmd[:60]}")
                if out:
                    for line in out.split("\n")[:5]:
                        self.log(f"    out: {line}")
                if err:
                    for line in err.split("\n")[:3]:
                        self.log(f"    err: {line}")
            return out, err, code
        except subprocess.TimeoutExpired:
            return "", "TIMEOUT", -1
        except FileNotFoundError:
            return "", f"找不到 adb: {adb_exe}", -1
        except Exception as e:
            return "", str(e), -1

    def log(self, msg):
        # 线程安全：后台刷步线程也会调用，统一交给Tk主线程执行
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, lambda: self.log(msg))
            return
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        self.log_box.configure(state=tk.NORMAL)
        self.log_box.insert(tk.END, line)
        self.log_box.see(tk.END)
        self.log_box.configure(state=tk.DISABLED)

    # ===================== Device Scan =====================
    def scan_device(self):
        adb_exe = self.adb_var.get().strip() or "adb"
        # 重新扫描前先释放旧通道
        if self.adb_conn:
            try:
                self.adb_conn.close()
            except Exception:
                pass
            self.adb_conn = None
        try:
            startupinfo = None
            if os.name == "nt":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            r = subprocess.run(f"{adb_exe} devices", shell=True, capture_output=True, text=True, timeout=10, startupinfo=startupinfo)
            lines = [l for l in r.stdout.strip().split("\n") if l.strip()]
            devs = [l for l in lines[1:] if "\tdevice" in l and "unauthorized" not in l]
            if devs:
                self.device_id = devs[0].split("\t")[0]
                self.device_var.set(f"✅ {self.device_id}")
                self.android_ver = self._detect_android()
                self.android_ver_var.set(f"{self.android_ver}")
                self.has_root = self._check_root()
                self.root_var.set("✅" if self.has_root else "❌")
                self.log(f"设备已连接: {self.device_id}, Android {self.android_ver}, Root={self.has_root}")
                self._prepare_device()
                # 建立常驻注入通道（实时注入/读回确认全走它）
                self.adb_conn = AdbConnection(adb_exe, self.device_id, self.log)
                if self.adb_conn.alive:
                    self.log("✅ 实时注入通道已建立（单通道批量下发 + 执行回执）")
                self._auto_select_app()
            else:
                self.device_id = None
                self.device_var.set("❌ 未检测到设备")
                self.log("未检测到设备，请检查USB连接/授权")
        except Exception as e:
            self.device_id = None
            self.device_var.set(f"❌ ADB错误")
            self.log(f"ADB扫描失败: {e}")

    def _detect_android(self):
        out, _, _ = self.adb("shell getprop ro.build.version.release")
        return out if out else "未知"

    def _check_root(self):
        out, err, code = self.adb("shell su -c 'id'")
        if code == 0 and "uid=0" in out:
            return True
        out2, _, _ = self.adb("shell which su")
        if out2:
            out3, _, c3 = self.adb("shell su 0 id")
            if c3 == 0:
                return True
        return False

    # ===================== Location 命令风格适配 =====================
    def _detect_location_style(self):
        """探测 cmd location 的命令风格。

        Android 13+（如本机 vivo Android 13）改为：
          cmd location providers add-test-provider ...
          cmd location providers set-test-provider-location gps --location lat,lng --accuracy x
        且不再提供 get-location / inject-location；dumpsys 中坐标还被脱敏。
        旧风格（Android 12-及多数ROM）：
          cmd location set-test-provider-location gps lat lng alt acc speed bearing
          cmd location get-location gps
        返回 'new' 或 'legacy'，结果缓存。
        """
        cached = getattr(self, "_loc_style", None)
        if cached:
            return cached
        out, _, _ = self.adb("shell cmd location")
        style = "new" if ("--location" in out and "providers" in out) else "legacy"
        self._loc_style = style
        self.log(f"  定位命令风格: {'Android13+ 新语法(providers)' if style == 'new' else '经典语法'}")
        return style

    @staticmethod
    def _parse_et_ms(text):
        """解析 dumpsys 中 Location 的 et=+8d15h40m39s835ms 为总毫秒数。"""
        m = re.search(r'et=\+?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?(?:(\d+)ms)?',
                      text or "")
        if not m:
            return None
        d, h, mi, s, ms = m.groups()
        total = 0
        if d:
            total += int(d) * 86400000
        if h:
            total += int(h) * 3600000
        if mi:
            total += int(mi) * 60000
        if s:
            total += int(float(s) * 1000)
        if ms:
            total += int(ms)
        return total

    def _read_gps_mock(self):
        """从 dumpsys 读取 gps 提供者当前 mock 定位，返回 (et_ms, hAcc, 原始行)。"""
        if self.adb_conn and self.adb_conn.alive:
            out, _ = self.adb_conn.execute(
                "dumpsys location | grep -F 'Location[gps ' | grep -F 'mock'", timeout=8)
        else:
            out, _, _ = self.adb("shell dumpsys location")
        for line in (out or "").splitlines():
            if "Location[gps " in line and "mock" in line:
                et = self._parse_et_ms(line)
                acc_m = re.search(r'hAcc=([\d.]+)', line)
                acc = float(acc_m.group(1)) if acc_m else None
                return et, acc, line.strip()
        return None, None, None

    def _prepare_device(self):
        self.log("🔧 正在初始化设备环境...")

        self.adb("shell settings put secure enable_mock_location 1")
        self.adb("shell settings put global enable_mock_location 1")
        self.adb("shell settings put secure location_mode 3")
        self.adb("shell settings put secure location_providers_allowed gps,network")

        self.adb("shell settings put secure mock_location_app com.android.shell")
        self.adb("shell settings put global mock_location_app com.android.shell")
        self.adb("shell settings put system mock_location_app com.android.shell")
        self.adb("shell appops set com.android.shell MOCK_LOCATION allow")
        self.adb("shell appops set shell MOCK_LOCATION allow")
        self.adb("shell appops set com.android.settings MOCK_LOCATION allow")
        self.adb("shell appops set 2000 MOCK_LOCATION allow")
        self.adb("shell appops set 1000 MOCK_LOCATION allow")

        if self.target_app:
            self.adb(f"shell appops set {self.target_app} ACCESS_FINE_LOCATION allow")
            self.adb(f"shell appops set {self.target_app} ACCESS_COARSE_LOCATION allow")
            self.adb(f"shell appops set {self.target_app} MOCK_LOCATION allow")
            self.adb(f"shell settings put secure mock_location_app {self.target_app}")

        brand, _, _ = self.adb("shell getprop ro.product.manufacturer")
        model, _, _ = self.adb("shell getprop ro.product.model")
        self.log(f"  检测到: {brand} {model}")

        if "xiaomi" in brand.lower() or "mi" in model.lower():
            self.log("  → 小米特化")
            self.adb("shell settings put system enable_mock_location 1")
            self.adb("shell settings put global miui_opt_switch 1")
            self.adb("shell settings put secure mock_location_app com.android.shell")

        if "huawei" in brand.lower() or "honor" in brand.lower():
            self.log("  → 华为特化")
            self.adb("shell settings put secure enable_hw_location_simulate 1")
            self.adb("shell settings put global enable_hw_location_simulate 1")

        if any(x in brand.lower() for x in ["oppo", "realme", "oneplus"]):
            self.log("  → OPPO特化")
            self.adb("shell settings put oppo_enable_virtual_location 1")

        if "vivo" in brand.lower() or "iqoo" in brand.lower():
            self.log("  → vivo特化")
            self.adb("shell settings put secure enable_virtual_location 1")
            self.adb("shell settings put global enable_virtual_location 1")

        # 探测本机 cmd location 语法风格（Android13+ 与旧版参数完全不同）
        style = self._detect_location_style()

        # 清理可能残留的旧测试提供者（remove-test-provider 只移除模拟源，不会关闭真实GPS）
        # 重要：全程不关闭真实GPS/网络定位，保持高精度模式，避免APP检测到GPS关闭而不收点。
        self.adb("shell settings put secure location_mode 3")
        if style == "new":
            self.adb("shell cmd location set-location-enabled true")
            for p in ("gps", "network"):
                self.adb(f"shell cmd location providers remove-test-provider {p}")
            time.sleep(0.3)
            for p in ("gps", "network"):
                self.adb(f"shell cmd location providers add-test-provider {p}")
                self.adb(f"shell cmd location providers set-test-provider-enabled {p} true")
        else:
            self.adb("shell settings put secure location_providers_allowed +gps")
            self.adb("shell settings put secure location_providers_allowed +network")
            for p in ("gps", "network", "fused", "passive"):
                self.adb(f"shell cmd location remove-test-provider {p}")
            time.sleep(0.3)
            self.adb("shell cmd location set-location-enabled true gps")
            self.adb("shell cmd location set-location-enabled true network")
            for p in ("gps", "network", "fused", "passive"):
                self.adb(f"shell cmd location add-test-provider {p} enabled true has-monitors true")
                self.adb(f"shell cmd location set-test-provider-enabled {p} true")
            self.adb("shell cmd location set-location-enabled true gps")
            self.adb("shell cmd location set-location-enabled true network")
            self.adb("shell cmd location set-location-enabled true fused")
            self.adb("shell cmd location set-location-enabled true passive")

        time.sleep(0.2)

        out5, _, _ = self.adb("shell settings get secure enable_mock_location")
        out6, _, _ = self.adb("shell settings get secure mock_location_app")
        out7, _, _ = self.adb("shell settings get global mock_location_app")
        loc_on, _, _ = self.adb("shell cmd location is-location-enabled")
        self.log(f"  Location总开关: {loc_on or '未知'}  | enable_mock_location: {out5}")
        self.log(f"  mock_location_app(secure): {out6}  (global): {out7}")

        if style == "new":
            # 新ROM坐标在dumpsys脱敏，检查mock提供者是否就绪 + 注入起点探针确认链路
            probe_lat = round(float(self.base_lat), 6)
            probe_lng = round(float(self.base_lng), 6)
            self.adb(f"shell cmd location providers set-test-provider-location gps "
                     f"--location {probe_lat},{probe_lng} --accuracy 5.0")
            time.sleep(0.4)
            et, acc, line = self._read_gps_mock()
            self.log(f"  gps mock提供者: {'✅ 已就绪' if et is not None else '⚠️ 未读到mock定位（开跑后仍会重试确认）'}")
            if line:
                self.log(f"    {line[:100]}")
        else:
            out, _, _ = self.adb("shell cmd location get-test-provider-location gps")
            out2, _, _ = self.adb("shell cmd location get-test-provider-location fused")
            self.log(f"  test-provider gps: {out[:80] if out else '无返回'}")
            self.log(f"  test-provider fused: {out2[:80] if out2 else '无返回'}")

        if self.has_root:
            self.log("  → Root强化")
            self.adb("shell su -c 'settings put secure enable_mock_location 1'")
            self.adb("shell su -c 'settings put global enable_mock_location 1'")
            self.adb("shell su -c 'settings put secure mock_location_app com.android.shell'")
            if style == "new":
                self.adb("shell su -c 'cmd location providers set-test-provider-enabled gps true'")
            else:
                self.adb("shell su -c 'cmd location set-test-provider-enabled gps true'")
                self.adb("shell su -c 'cmd location set-test-provider-enabled fused true'")

        self.log("🔧 初始化完成\n")

    def full_diagnose(self):
        self.log("=== 开始完整诊断 ===")
        self.scan_device()
        if not self.device_id:
            return
        checks = [
            ("Android版本", "shell getprop ro.build.version.release"),
            ("手机品牌", "shell getprop ro.product.manufacturer"),
            ("手机型号", "shell getprop ro.product.model"),
            ("Location模式", "shell settings get secure location_mode"),
            ("Mock开关(global)", "shell settings get global enable_mock_location"),
            ("Mock开关(secure)", "shell settings get secure enable_mock_location"),
            ("Location启用", "shell cmd location is-location-enabled"),
            ("GPS启用", "shell cmd location is-provider-enabled gps"),
            ("Network启用", "shell cmd location is-provider-enabled network"),
            ("Screen状态", "shell dumpsys power | grep Display Power: | head -1"),
        ]
        for name, cmd in checks:
            out, err, code = self.adb(cmd)
            self.log(f"  {name}: {out or err}")
        self.log("=== 诊断完成 ===")

    @staticmethod
    def calc_bearing(lat1, lng1, lat2, lng2):
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlng = math.radians(lng2 - lng1)
        y = math.sin(dlng) * math.cos(lat2_r)
        x = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlng)
        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360

    # ===================== App Management =====================
    def _auto_select_app(self):
        """连接设备后，自动把目标APP选为机身已安装的已知跑步APP（避免默认包名未安装）。"""
        try:
            out, _, _ = self.adb("shell pm list packages")
            installed = {l.replace("package:", "").strip() for l in out.splitlines()}
            for pkg, label in self.known_apps.items():
                if pkg in installed:
                    self.app_pkg_var.set(pkg)
                    self.app_combo.set(pkg)
                    self.target_app = pkg
                    self.log(f"🎯 检测到已安装的目标APP：{label} ({pkg})，已自动选中")
                    return
            self.log("⚠️ 未在已知列表中检测到已安装的跑步APP，请手动确认包名")
        except Exception as e:
            self.log(f"自动识别APP失败: {e}")

    def list_installed_running_apps(self):
        if not self.device_id:
            messagebox.showwarning("提示", "请先连接设备！")
            return
        self.log("📋 正在扫描已安装的跑步类APP...")
        out, _, _ = self.adb("shell pm list packages | grep -E 'run|sport|walk|paobu|lexiang|qufeng|xsyd|hjex|fit|health|tanke|lptiyu'")
        if out:
            pkgs = out.split("\n")
            self.log(f"  找到 {len(pkgs)} 个可能的运动APP:")
            for p in pkgs:
                pkg = p.replace("package:", "").strip()
                label = self.known_apps.get(pkg, "")
                self.log(f"    → {pkg}  {f'[{label}]' if label else ''}")
        else:
            self.log("  未找到匹配关键词的APP，显示所有已安装的第3方APP...")
            out2, _, _ = self.adb("shell pm list packages -3")
            for line in out2.split("\n")[:20]:
                self.log(f"    {line.replace('package:', '')}")

    def launch_target_app(self):
        if not self.device_id:
            messagebox.showwarning("提示", "请先连接设备！")
            return
        pkg = self.app_pkg_var.get().strip()
        if not pkg:
            messagebox.showwarning("提示", "请先输入或选择APP包名！")
            return
        self.target_app = pkg
        self.log(f"▶ 正在启动 {pkg} ...")

        self.adb("shell input keyevent 224")
        self.adb("shell wm dismiss-keyguard")

        self.adb(f"shell monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        time.sleep(1.5)

        pid_out, _, _ = self.adb(f"shell pidof {pkg}")
        if pid_out and pid_out.strip():
            self.log(f"  ✅ APP运行中 (pid={pid_out.strip()})")
        else:
            out3, _, _ = self.adb(f"shell cmd package resolve-activity --brief {pkg}")
            activity_name = ""
            for line in out3.split("\n"):
                if "/" in line and pkg in line:
                    activity_name = line.split("/")[-1].strip()
                    break
            if activity_name:
                self.adb(f"shell am start -n {pkg}/{activity_name}")
                time.sleep(1)
            pid_out2, _, _ = self.adb(f"shell pidof {pkg}")
            if pid_out2 and pid_out2.strip():
                self.log(f"  ✅ APP运行中 (pid={pid_out2.strip()})")
            else:
                self.log(f"  ⚠️ 自动启动可能失败，但GPS注入不受APP前台影响")

        self.last_app_ping = time.time()
        self._app_warned = False

    def _is_app_running(self):
        if not self.target_app:
            return False
        out, _, _ = self.adb(f"shell pidof {self.target_app}")
        return bool(out and out.strip())

    def ensure_app_foreground(self, force=False):
        if not self.target_app:
            return
        now = time.time()
        if not force and (now - self.last_app_ping) < 30:
            return

        self.last_app_ping = now

        if self._is_app_running():
            return

        self.adb(f"shell monkey -p {self.target_app} -c android.intent.category.LAUNCHER 1")
        self.adb("shell input keyevent 224")
        self.adb("shell wm dismiss-keyguard")
        time.sleep(2)

        if self._is_app_running():
            self.log(f"  ✅ APP进程已恢复运行")
        elif not getattr(self, '_app_warned', False):
            self.log(f"  ⚠️ {self.target_app} 未检测到进程，但GPS注入仍会继续")
            self.log(f"  💡 建议：手动打开一次跑步APP的开始跑步界面")
            self._app_warned = True

    # ===================== Multi-channel GPS Inject =====================
    def inject_gps_all(self, lat, lng, alt=50.0, speed=1.4, bearing=0.0):
        alt_j = alt + random.uniform(-0.3, 0.3)
        lat_r = round(lat, 8)
        lng_r = round(lng, 8)
        speed_ms = speed / 3.6
        acc_gps = random.uniform(3.0, 6.0)
        acc_net = random.uniform(15.0, 30.0)
        acc_fused = random.uniform(5.0, 15.0)

        self.adb("shell cmd location set-test-provider-enabled gps true")
        self.adb("shell cmd location set-test-provider-enabled network true")
        self.adb("shell cmd location set-test-provider-enabled fused true")
        self.adb("shell cmd location set-test-provider-enabled passive true")
        self.adb("shell cmd location set-location-enabled true gps")
        self.adb("shell cmd location set-location-enabled true network")

        self.adb(f"shell cmd location set-test-provider-location gps "
                 f"{lat_r} {lng_r} {alt_j:.1f} {acc_gps:.1f} {speed_ms:.2f} {bearing:.1f}")
        self.adb(f"shell cmd location set-test-provider-location network "
                 f"{lat_r} {lng_r} {alt_j:.1f} {acc_net:.1f} {speed_ms:.2f} {bearing:.1f}")
        self.adb(f"shell cmd location set-test-provider-location fused "
                 f"{lat_r} {lng_r} {alt_j:.1f} {acc_fused:.1f} {speed_ms:.2f} {bearing:.1f}")
        self.adb(f"shell cmd location set-test-provider-location passive "
                 f"{lat_r} {lng_r} {alt_j:.1f} {acc_fused:.1f} {speed_ms:.2f} {bearing:.1f}")

        self.adb(f"shell cmd location inject-location gps "
                 f"{lat_r} {lng_r} {alt_j:.1f} {acc_gps:.1f} {speed_ms:.2f} {bearing:.1f}")
        self.adb(f"shell cmd location inject-location fused "
                 f"{lat_r} {lng_r} {alt_j:.1f} {acc_fused:.1f} {speed_ms:.2f} {bearing:.1f}")

        self.adb(f"shell cmd location set-location gps {lat_r} {lng_r} {acc_gps:.1f}")
        self.adb(f"shell cmd location set-location network {lat_r} {lng_r} {acc_net:.1f}")

        self.adb(f"shell service call location 3 "
                 f"i 1 i 1 d {lat_r} d {lng_r} f {alt_j:.1f} f {acc_gps:.1f} f {speed_ms:.2f} f {bearing:.1f}")
        self.adb(f"shell service call location 10 "
                 f"i 1 i 1 d {lat_r} d {lng_r} f {alt_j:.1f} f {acc_fused:.1f} f {speed_ms:.2f} f {bearing:.1f}")

        if self.has_root:
            self.adb(f"shell su -c 'cmd location inject-location gps "
                     f"{lat_r} {lng_r} {alt_j:.1f} {acc_gps:.1f} {speed_ms:.2f} {bearing:.1f}'")
            self.adb(f"shell su -c 'cmd location set-test-provider-location gps "
                     f"{lat_r} {lng_r} {alt_j:.1f} {acc_gps:.1f} {speed_ms:.2f} {bearing:.1f}'")
            self.adb(f"shell su -c 'cmd location inject-location fused "
                     f"{lat_r} {lng_r} {alt_j:.1f} {acc_fused:.1f} {speed_ms:.2f} {bearing:.1f}'")

        return True

    # ===================== Verified Inject (端到端ACK) =====================
    def _ensure_conn(self):
        """确保常驻通道可用（断了就重建一次）。"""
        if self.adb_conn and self.adb_conn.alive:
            return True
        if self.adb_conn:
            try:
                self.adb_conn.close()
            except Exception:
                pass
        adb_exe = self.adb_var.get().strip() or "adb"
        if self.device_id:
            self.adb_conn = AdbConnection(adb_exe, self.device_id, self.log)
            return self.adb_conn.alive
        return False

    @staticmethod
    def _match_location(text, exp_lat, exp_lng, tol_m=30.0):
        """从手机回读文本中找到与期望坐标吻合的定位，返回 (lat,lng,偏差米)，否则None。"""
        if not text:
            return None
        # 经纬度在回读中都是6~8位小数，借此过滤掉 accuracy/altitude/bearing 等数值
        nums = re.findall(r'-?\d{1,3}\.\d{4,}', text)
        seen = set()
        for i in range(len(nums) - 1):
            pair = (nums[i], nums[i + 1])
            if pair in seen:
                continue
            seen.add(pair)
            try:
                la, lo = float(pair[0]), float(pair[1])
            except ValueError:
                continue
            if not (-90 <= la <= 90 and -180 <= lo <= 180):
                continue
            if abs(la - exp_lat) < 0.01 and abs(lo - exp_lng) < 0.01:
                d = EnhancedGPSRunner.haversine(exp_lat, exp_lng, la, lo)
                if d <= tol_m:
                    return la, lo, d
        return None

    def inject_point(self, lat, lng, alt=50.0, speed=5.0, bearing=0.0,
                     verify=True, retries=3):
        """注入单个轨迹点并要求手机端回读确认。

        只有手机位置服务确认接收了该点才算成功，否则重试，仍失败返回False，
        由调用方中断并如实提示——电脑端绝不虚报完成。
        两种ROM语法：
          - new (Android13+): providers set-test-provider-location --location
            该类ROM dumpsys坐标脱敏，用 mock定位的 et时间戳刷新 作为ACK；
          - legacy: set-test-provider-location 位置参数 + get-location 经纬度回读。
        返回 (是否确认, 本次重试次数, 确认信息)。
        """
        style = self._detect_location_style()
        lat_r = round(lat, 8)
        lng_r = round(lng, 8)
        speed_ms = max(0.0, speed / 3.6)
        alt_j = alt + random.uniform(-0.3, 0.3)
        acc_gps = round(random.uniform(3.0, 6.0), 1)
        acc_net = round(random.uniform(15.0, 30.0), 1)
        acc_fused = round(random.uniform(5.0, 15.0), 1)

        if style == "new":
            # 新语法只支持 --location/--accuracy/--time，速度/方向由APP按相邻点差分
            inject_cmd = " ; ".join([
                "cmd location providers set-test-provider-enabled gps true",
                f"cmd location providers set-test-provider-location gps "
                f"--location {lat_r},{lng_r} --accuracy {acc_gps}",
                "cmd location providers set-test-provider-enabled network true",
                f"cmd location providers set-test-provider-location network "
                f"--location {lat_r},{lng_r} --accuracy {acc_net}",
            ])
            read_cmd = "dumpsys location | grep -F 'Location[gps ' | grep -F 'mock'"
            script = inject_cmd + " ; " + read_cmd if verify else inject_cmd
        else:
            cmds = [
                "cmd location set-test-provider-enabled gps true",
                "cmd location set-test-provider-enabled fused true",
                f"cmd location set-test-provider-location gps "
                f"{lat_r} {lng_r} {alt_j:.1f} {acc_gps:.1f} {speed_ms:.2f} {bearing:.1f}",
                f"cmd location set-test-provider-location fused "
                f"{lat_r} {lng_r} {alt_j:.1f} {acc_fused:.1f} {speed_ms:.2f} {bearing:.1f}",
                f"cmd location inject-location gps "
                f"{lat_r} {lng_r} {alt_j:.1f} {acc_gps:.1f} {speed_ms:.2f} {bearing:.1f}",
                f"cmd location inject-location fused "
                f"{lat_r} {lng_r} {alt_j:.1f} {acc_fused:.1f} {speed_ms:.2f} {bearing:.1f}",
                f"cmd location set-location gps {lat_r} {lng_r} {acc_gps:.1f}",
            ]
            if self.has_root:
                cmds += [
                    f"su -c 'cmd location inject-location gps "
                    f"{lat_r} {lng_r} {alt_j:.1f} {acc_gps:.1f} {speed_ms:.2f} {bearing:.1f}'",
                    f"su -c 'cmd location set-test-provider-location gps "
                    f"{lat_r} {lng_r} {alt_j:.1f} {acc_gps:.1f} {speed_ms:.2f} {bearing:.1f}'",
                ]
            if verify:
                cmds += ["cmd location get-location gps",
                         "cmd location get-test-provider-location gps"]
            script = " ; ".join(cmds)

        last_out = ""
        before_et = getattr(self, "_last_ack_et", None)

        for attempt in range(retries):
            if self.adb_conn and self.adb_conn.alive:
                # 注入+回读在同一条shell脚本里完成，一次管道往返
                out, rc = self.adb_conn.execute(script, timeout=8)
                last_out = out
            else:
                # 兼容回退：常驻通道不可用时逐进程执行（实时性较差）
                if style == "new":
                    self.adb("shell " + inject_cmd)
                    last_out = ""
                    if verify:
                        et, acc, line = self._read_gps_mock()
                        last_out = line or ""
                else:
                    self.inject_gps_all(lat, lng, alt=alt, speed=speed, bearing=bearing)
                    last_out = ""
                    if verify:
                        o1, _, _ = self.adb("shell cmd location get-location gps")
                        o2, _, _ = self.adb("shell cmd location get-test-provider-location gps")
                        last_out = (o1 or "") + "\n" + (o2 or "")

            if not verify:
                return True, 0, None

            if style == "new":
                et, acc, line = (None, None, None)
                for ln in (last_out or "").splitlines():
                    if "Location[gps " in ln and "mock" in ln:
                        et = self._parse_et_ms(ln)
                        am = re.search(r'hAcc=([\d.]+)', ln)
                        acc = float(am.group(1)) if am else None
                        break
                # ACK：mock定位时间戳相对上一确认点刷新（首次则出现mock行即可）
                et_ok = et is not None and (before_et is None or et > before_et)
                acc_ok = acc is None or abs(acc - acc_gps) <= 0.15
                if et_ok and acc_ok:
                    self._last_ack_et = et
                    return True, attempt, {"style": "new", "et": et, "hAcc": acc}
            else:
                hit = self._match_location(last_out, lat, lng)
                if hit:
                    return True, attempt, {"style": "legacy", "lat": hit[0],
                                           "lng": hit[1], "diff_m": hit[2]}

            # 手机端尚未刷新该点，短暂等待后重试同一坐标
            time.sleep(0.3)

        return False, retries - 1, last_out

    def _heartbeat(self):
        """周期性重新使能 provider 并回读 mock 定位，确认整条接收链路活着。"""
        style = self._detect_location_style()
        if style == "new":
            script = " ; ".join([
                "cmd location providers set-test-provider-enabled gps true",
                "settings put secure enable_mock_location 1",
                "settings put global enable_mock_location 1",
                "dumpsys location | grep -F 'Location[gps ' | grep -F 'mock'",
            ])
            if self.adb_conn and self.adb_conn.alive:
                out, _ = self.adb_conn.execute(script, timeout=8)
            else:
                self.adb("shell cmd location providers set-test-provider-enabled gps true")
                self.adb("shell settings put secure enable_mock_location 1")
                self.adb("shell settings put global enable_mock_location 1")
                _, _, out = self._read_gps_mock()
            tail = ""
            for ln in (out or "").splitlines():
                if "Location[gps " in ln:
                    tail = ln.strip()[:90]
                    break
            self.log(f"  🔄 Provider心跳 + mock回读: {tail or '未读到mock定位'}")
            return

        script = " ; ".join([
            "cmd location set-test-provider-enabled gps true",
            "cmd location set-test-provider-enabled fused true",
            "cmd location set-location-enabled true gps",
            "settings put secure enable_mock_location 1",
            "settings put global enable_mock_location 1",
            "cmd location get-test-provider-location gps",
        ])
        if self.adb_conn and self.adb_conn.alive:
            out, _ = self.adb_conn.execute(script, timeout=8)
        else:
            self.adb("shell cmd location set-test-provider-enabled gps true")
            self.adb("shell cmd location set-test-provider-enabled fused true")
            self.adb("shell settings put secure enable_mock_location 1")
            self.adb("shell settings put global enable_mock_location 1")
            out, _, _ = self.adb("shell cmd location get-test-provider-location gps")
        tail = ""
        if out and out.strip():
            tail = out.strip().splitlines()[-1][:80]
        self.log(f"  🔄 Provider心跳 + 手机端回读: {tail or '无返回'}")

    def read_phone_app_display(self):
        """读取跑步APP界面实际显示的距离/步数（端到端的最后一环证据）。

        通过 uiautomator dump 当前界面XML，在设备端grep出“x.xx公里 / x步”等文本，
        只读取、不点击。读不到（部分APP用自绘View）时返回空列表，不影响主流程。
        """
        if not (self.adb_conn and self.adb_conn.alive and self.target_app):
            return []
        out, _ = self.adb_conn.execute(f"pidof {self.target_app} ; true", timeout=5)
        if not out.strip():
            self.adb_conn.execute(
                f"monkey -p {self.target_app} -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; "
                "input keyevent 224; wm dismiss-keyguard", timeout=8)
            time.sleep(2)
        script = (
            "uiautomator dump /sdcard/.uidump.xml >/dev/null 2>&1 ; "
            "grep -oE '[0-9]+(\\.[0-9]+)?(公里|千米|km|KM|步)' /sdcard/.uidump.xml | head -12"
        )
        out, _ = self.adb_conn.execute(script, timeout=12)
        vals = []
        for line in out.splitlines():
            v = line.strip()
            if v and v not in vals:
                vals.append(v)
        return vals[:8]

    # ===================== Sensor Simulation =====================
    def inject_accelerometer(self, walking=True):
        if not self.chk_accel.get():
            return
        if not self.has_root:
            # 无Root无法真正注入传感器。旧实现在这里随机按 keyevent 26(电源键，会熄屏)
            # 和 keyevent 82(菜单键，会把跑步APP切后台)，正是手机端中途丢点的元凶之一，
            # 已彻底移除——无Root环境下步数由APP依据GPS轨迹自行计算。
            return
        base = 9.81
        t = time.time()
        step_freq = 1.7
        phase = (t * step_freq * 2 * math.pi) % (2 * math.pi)
        z = base + 2.5 * abs(math.sin(phase))
        x = random.uniform(-0.3, 0.3)
        y = random.uniform(-0.2, 0.2)
        # best-effort：不同ROM的sensorservice事务码不一致，失败不影响GPS主通道
        if self.adb_conn and self.adb_conn.alive:
            self.adb_conn.execute(
                f"su -c 'service call sensorservice 1 {x:.2f} {y:.2f} {z:.2f}' ; true",
                timeout=3)

    def inject_gyroscope(self):
        if not self.chk_gyro.get():
            return
        if self.has_root and self.adb_conn and self.adb_conn.alive:
            rx = random.uniform(-0.1, 0.1)
            ry = random.uniform(-0.15, 0.15)
            rz = random.uniform(-0.05, 0.05)
            self.adb_conn.execute(
                f"su -c 'service call sensorservice 2 {rx:.3f} {ry:.3f} {rz:.3f}' ; true",
                timeout=3)

    # ===================== Screen & Wake =====================
    def keep_screen_alive(self):
        if self.chk_keep_screen.get():
            self.adb("shell svc power stayon true")
            self.adb("shell settings put system screen_off_timeout 120000")
        if self.chk_wake.get():
            self.adb("shell input keyevent 224")
            self.adb("shell wm dismiss-keyguard")

    def _keep_screen_alive_conn(self):
        """运行期保活走常驻通道；只在检测到熄屏时才唤醒，平时零打扰。"""
        if not (self.adb_conn and self.adb_conn.alive):
            return
        if self.chk_wake.get():
            script = ("st=$(dumpsys power | grep -E 'mWakefulness=|Display Power' | head -1); "
                      "case $st in *Asleep*|*Sleeping*|*OFF*) "
                      "input keyevent 224; wm dismiss-keyguard;; esac; svc power stayon true")
        else:
            script = "svc power stayon true"
        if self.chk_keep_screen.get():
            self.adb_conn.execute(script, timeout=5)

    def periodic_app_activity(self):
        """仅在APP进程丢失时重新拉起。不再随机按 MENU 等会把APP切后台的按键。"""
        if not self.chk_press.get():
            return
        if not (self.target_app and self.adb_conn and self.adb_conn.alive):
            return
        out, _ = self.adb_conn.execute(f"pidof {self.target_app} ; true", timeout=4)
        if not out.strip():
            self.adb_conn.execute(
                f"monkey -p {self.target_app} -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; "
                "input keyevent 224; wm dismiss-keyguard", timeout=8)
            self.log(f"  ⚠️ 检测到 {self.target_app} 进程丢失，已重新拉起")

    # ===================== Route Generation =====================
    def generate_route(self, lat, lng, distance_km, route_type, speed_kmh=5.0, interval_sec=2.0):
        points = []
        total_m = distance_km * 1000

        # 每点距离严格按 速度×间隔 计算（下限2m），避免被8m下限撑快到14km/h
        seg_m = max(2.0, speed_kmh / 3.6 * interval_sec)
        seg_deg = seg_m / 111000.0

        if route_type == "circle":
            r_m = total_m / (2 * math.pi)
            r_deg = r_m / 111000.0
            circumference_deg = 2 * math.pi * r_deg
            n = max(40, int(circumference_deg / seg_deg))
            cx = lat - r_deg
            cy = lng
            points.append((lat, lng))
            for i in range(1, n):
                a = (i / n) * 2 * math.pi
                pl = cx + r_deg * math.cos(a)
                pn = cy + r_deg * math.sin(a) / math.cos(math.radians(lat))
                points.append((pl, pn))

        elif route_type == "figure8":
            r_m = total_m / (4 * math.pi)
            r_deg = r_m / 111000.0
            full_deg = 8 * math.pi * r_deg
            n = max(50, int(full_deg / seg_deg))
            points.append((lat, lng))
            for i in range(1, n):
                t = (i / n) * 2 * math.pi
                pl = lat + r_deg * math.sin(t) * 0.5
                pn = lng + r_deg * math.sin(2 * t) / math.cos(math.radians(lat))
                points.append((pl, pn))

        elif route_type == "zigzag":
            side_m = total_m / 2
            side_deg = side_m / 111000.0
            total_path_deg = side_deg * 4
            n = max(40, int(total_path_deg / seg_deg))
            points.append((lat, lng))
            for i in range(1, n):
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
            n = max(30, int(half_deg * 2 / seg_deg))
            points.append((lat, lng))
            for i in range(1, n):
                t = i / n
                if t <= 0.5:
                    pl = lat + half_deg * (t / 0.5)
                    pn = lng
                else:
                    pl = lat + half_deg * (1 - (t - 0.5) / 0.5)
                    pn = lng
                points.append((pl, pn))

        return points

    # ===================== Haversine =====================
    @staticmethod
    def haversine(lat1, lng1, lat2, lng2):
        R = 6371000
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ===================== GPS Test =====================
    def test_gps(self):
        if not self.device_id:
            messagebox.showwarning("提示", "请先扫描并连接设备！")
            return
        try:
            lat = float(self.lat_var.get())
            lng = float(self.lng_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的经纬度！")
            return
        # 初始化涉及几十条ADB指令，放后台线程执行，避免窗口冻结
        self.test_btn.configure(state=tk.DISABLED)
        threading.Thread(target=self._test_gps_worker, args=(lat, lng), daemon=True).start()

    def _test_gps_worker(self, lat, lng):
        try:
            self.log(f"🧪 === 开始GPS注入测试 ({lat}, {lng}) ===")
            self._prepare_device()
            self._ensure_conn()
            style = self._detect_location_style()

            ok, tries, info = self.inject_point(lat, lng, speed=0.0, bearing=0.0,
                                                verify=True, retries=3)
            self.inject_accelerometer()
            self.inject_gyroscope()
            if ok and info and info.get("style") == "new":
                self.log(f"✅ 注入成功：手机位置服务已刷新 mock 定位"
                         f"（重试{tries}次, et={info['et']}, hAcc={info['hAcc']}）")
            elif ok and info and info.get("style") == "legacy":
                self.log(f"✅ 注入成功：回读偏差 {info['diff_m']:.1f}m（重试{tries}次）")
            elif ok:
                self.log(f"✅ 注入完成（重试{tries}次）")
            else:
                self.log("❌ 注入后手机端未确认（正式刷步时这种点会触发重试/中断）")

            self.log("🔍 回读验证 (dumpsys location)...")
            et, acc, line = self._read_gps_mock()
            if line:
                self.log(f"  gps mock => {line[:120]}")
            else:
                self.log("  未读到 gps mock 定位行")

            if style == "legacy":
                out, _, _ = self.adb("shell cmd location get-location gps")
                self.log(f"  cmd location gps => {out[:120] if out else '无返回'}")

            # 投递记录：确认定位是否真正送达到了跑步APP
            out_d, _, _ = self.adb("shell dumpsys location")
            deliveries = [l.strip() for l in out_d.splitlines()
                          if "delivered location" in l and self.target_app in l]
            if deliveries:
                self.log(f"  � 最近送达 {self.target_app} 的记录:")
                for dl in deliveries[-3:]:
                    self.log(f"    {dl[:120]}")

            if ok:
                self.log("  ✅ 链路正常，可以开始刷步")
            else:
                self.log("  💡 建议：检查模拟位置授权 / 重新插拔USB / 换GPS信号好的位置")
            self.log("🧪 === 测试完成 ===\n")
        finally:
            self.root.after(0, lambda: self.test_btn.configure(state=tk.NORMAL))

    # ===================== Start / Stop =====================
    def start_run(self):
        if not self.device_id:
            messagebox.showwarning("提示", "请先扫描并连接设备！")
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

        self.base_lat = lat
        self.base_lng = lng
        self.target_distance = dist
        self.speed = spd
        self.interval = interval
        self.route_type = self.route_var.get()

        self.target_app = self.app_pkg_var.get().strip()
        self.log(f"=== 开始刷步: {dist}km @ {spd}km/h, 轨迹={self.route_type}, 目标APP={self.target_app} ===")

        self.total_points = 0
        self.covered_points = 0
        self.step_count = 0
        self._last_ack_et = None
        self.running = True

        # 按钮立即切换，设备初始化/APP启动放到后台线程，避免点击后窗口冻结1-2分钟
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.prog_lbl.configure(text="⏳ 正在初始化设备环境并启动APP，请稍候...")

        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        try:
            # ---- 设备初始化 + APP启动（后台线程内，不卡UI）----
            self._prepare_device()
            self.keep_screen_alive()
            if self.target_app:
                self.log(f"🚀 自动启动跑步APP: {self.target_app}")
                self.launch_target_app()
                time.sleep(2)
            else:
                self.log("⚠️ 未配置APP包名，将跳过自动启动")

            self._run_route()
        except Exception as e:
            self.log(f"❌ 运行异常: {e}")
            self.root.after(0, lambda: self._reset_buttons())

    def _run_route(self):
        if not self._ensure_conn():
            self.log("⚠️ 实时通道不可用，使用兼容模式（逐进程ADB，点间隔可能偏大）")
        self.start_time = time.time()

        route = self.generate_route(self.base_lat, self.base_lng, self.target_distance,
                                    self.route_type, speed_kmh=self.speed, interval_sec=self.interval)
        self.total_points = len(route)
        self.root.after(0, lambda: self.prog.configure(value=0))

        verify = self.chk_verify.get()

        cum_dist = 0.0
        retries_total = 0
        acked = 0
        last_keep = 0.0
        last_phone_read = 0.0

        # ---- 起点：必须手机端确认后才开跑，避免一开始就丢点 ----
        lat0, lng0 = route[0]
        ok, tries, _ = self.inject_point(lat0, lng0, alt=50.0, speed=0.0,
                                         bearing=0.0, verify=verify)
        retries_total += tries
        if not ok:
            self._abort_run(0, self.total_points, lat0, lng0)
            return
        acked = 1
        prev_lat, prev_lng = lat0, lng0
        t_prev = time.time()
        self.root.after(0, lambda: self.phone_var.set("📱 手机端：位置服务已确认起点，开始移动"))
        time.sleep(self.interval)

        for i in range(1, len(route)):
            if not self.running:
                break
            t_loop = time.time()

            plat, plng = route[i]
            seg_d = self.haversine(prev_lat, prev_lng, plat, plng)
            brg = self.calc_bearing(prev_lat, prev_lng, plat, plng)
            brg = (brg + random.uniform(-5, 5) + 360) % 360

            # 用“手机端上一个确认点 -> 当前点”的真实墙钟时间反推速度，
            # 保证 距离/真实时间 与轨迹一致，APP不会因注入延迟误判瞬移而丢点
            dt = max(0.2, t_loop - t_prev)
            cur_spd = max(2.0, min(12.0, seg_d / dt * 3.6))

            ok, tries, _ = self.inject_point(plat, plng,
                                             alt=random.uniform(48, 52),
                                             speed=cur_spd, bearing=brg,
                                             verify=verify)
            retries_total += tries
            if not ok:
                # 手机端连续重试仍未收到该点：如实中断，绝不让电脑端虚报完成
                self._abort_run(i, self.total_points, plat, plng)
                return

            now = time.time()
            cum_dist += seg_d
            prev_lat, prev_lng = plat, plng
            t_prev = now
            acked += 1
            self.covered_points = acked
            self.step_count = int(cum_dist / 0.7)

            self.inject_accelerometer(walking=True)
            self.inject_gyroscope()

            if i % 30 == 0:
                self._heartbeat()

            if now - last_keep > 15:
                self._keep_screen_alive_conn()
                self.periodic_app_activity()
                last_keep = now

            phone_text = None
            if self.chk_uiauto.get() and now - last_phone_read > 30:
                last_phone_read = now
                vals = self.read_phone_app_display()
                if vals:
                    phone_text = "📱 手机APP显示: " + "  ".join(vals[:4])
                    self.log("  " + phone_text)

            elapsed = now - self.start_time
            avg_speed = (cum_dist / elapsed) * 3.6 if elapsed > 0 else 0
            self.root.after(0, lambda d=cum_dist/1000, s=self.step_count, t=elapsed,
                                   cs=cur_spd, as_=avg_speed, a=acked,
                                   tot=self.total_points, r=retries_total,
                                   pt=phone_text:
                            self._update_ui(d, s, t, cs, as_, a, tot, r, pt))

            # 自适应节拍：扣除本次注入耗时，维持手机端收点间隔恒定
            work = time.time() - t_loop
            if work < self.interval:
                time.sleep(self.interval - work)
            elif i % 25 == 0:
                self.log(f"  ⚠️ 第{i}点注入耗时{work:.1f}s 超过间隔{self.interval}s，"
                         f"速度已按真实接收时间修正")

        if self.running:
            # ---- 尾点冲刷：最后1~2个点可能还在APP缓冲，重复确认并等待落盘 ----
            self.log("🔚 尾点冲刷，等待手机端缓存落盘...")
            for _ in range(2):
                if not self.running:
                    break
                self.inject_point(prev_lat, prev_lng, alt=50.0, speed=2.0,
                                  bearing=0.0, verify=verify)
                time.sleep(1.0)
            self._heartbeat()

            phone_vals = []
            if self.chk_uiauto.get():
                phone_vals = self.read_phone_app_display()
                if phone_vals:
                    self.log("📱 手机端最终显示: " + "  ".join(phone_vals[:6]))

            self.running = False
            final_d = cum_dist / 1000
            self.root.after(0, lambda: self._finish(final_d, acked, self.total_points,
                                                     retries_total, phone_vals))

    def _update_ui(self, dist, steps, elapsed, cur_speed, avg_speed,
                   acked, total, retries, phone_text=None):
        self.dist_lbl.configure(text=f"{dist:.2f} km")
        self.step_lbl.configure(text=f"{steps} 步")
        m = int(elapsed) // 60
        s = int(elapsed) % 60
        self.time_lbl.configure(text=f"{m:02d}:{s:02d}")
        self.curr_speed_lbl.configure(text=f"{avg_speed:.1f} km/h")
        pct = (acked / total * 100) if total > 0 else 0
        self.prog.configure(value=pct)
        mode = "" if self.chk_verify.get() else "（未开启读回确认）"
        self.prog_lbl.configure(
            text=f"进度：{pct:.1f}%  |  手机已确认 {acked}/{total} 点{mode}  |  "
                 f"重试 {retries} 次  |  平均 {avg_speed:.1f} km/h")
        if phone_text:
            self.phone_var.set(phone_text)

    def _reset_buttons(self):
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)

    def _abort_run(self, idx, total, lat, lng):
        self.running = False
        self.root.after(0, lambda: self._show_abort(idx, total, lat, lng))

    def _show_abort(self, idx, total, lat, lng):
        self._reset_buttons()
        self.prog_lbl.configure(
            text=f"❌ 第 {idx + 1}/{total} 点手机端未确认，已中断（电脑端未虚报完成）")
        self.log(f"❌ 端到端确认失败：第{idx + 1}个点({lat:.6f},{lng:.6f})连续重试后手机仍未回读")
        self.log("  请检查：USB连接是否稳定 / 屏幕是否熄灭 / APP是否被切后台或被系统杀进程 / "
                 "开发者选项中模拟位置是否仍有效")
        messagebox.showerror(
            "端到端确认失败",
            f"第 {idx + 1}/{total} 个轨迹点连续重试后，手机位置服务仍未回读到该位置。\n\n"
            f"已如实中断——此前 {idx} 个点是手机已确认的，电脑端不会虚报100%。\n\n"
            f"建议排查：\n"
            f"1. USB连接/授权是否正常（可点“完整诊断”）\n"
            f"2. 跑步APP是否在前台、是否被系统省电策略杀掉\n"
            f"3. 屏幕是否熄灭、是否有弹窗遮挡\n"
            f"4. 重新开始后观察“手机已确认 x/y”是否持续增长")

    def _finish(self, final_dist, acked, total, retries, phone_vals):
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.prog.configure(value=100)
        self.prog_lbl.configure(
            text=f"✅ 完成！已确认距离 {final_dist:.2f} km（手机确认 {acked}/{total} 点）")
        self.log(f"=== 完成刷步: 已确认距离={final_dist:.2f}km, "
                 f"手机确认点={acked}/{total}, 重试={retries}, 估算步数~{self.step_count} ===")
        msg = (f"🎉 全部轨迹点均已被手机位置服务确认接收\n\n"
               f"已确认距离：{final_dist:.2f} km\n"
               f"确认点：{acked}/{total}（重试 {retries} 次）\n"
               f"估算步数：~{self.step_count} 步\n")
        if phone_vals:
            msg += f"手机APP显示：{'  '.join(phone_vals[:6])}\n"
        msg += ("\n请在手机APP中点击「结束/停止跑步」，确认成绩上传成功后再点确定。\n"
                "（确定后才会关闭模拟位置，避免上传过程中轨迹中断）")
        messagebox.showinfo("完成（端到端已确认）", msg)
        self._post_finish_cleanup()

    def _post_finish_cleanup(self):
        if self.adb_conn and self.adb_conn.alive:
            self.adb_conn.execute(
                "settings put secure enable_mock_location 0 ; "
                "settings put global enable_mock_location 0 ; svc power stayon false",
                timeout=6)
        self.adb("shell svc power stayon false")

    def stop_run(self):
        self.running = False
        self.adb("shell svc power stayon false")
        self.adb("shell settings put secure enable_mock_location 0")
        self.adb("shell settings put global enable_mock_location 0")
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.prog_lbl.configure(text="已停止")
        self.log("=== 手动停止 ===")

    def get_current_location(self):
        if not self.device_id:
            messagebox.showwarning("提示", "请先连接设备！")
            return
        self.log("尝试获取当前GPS位置...")

        # 先尝试 cmd location
        out, _, _ = self.adb("shell cmd location get-location gps")
        if out and out not in ("TIMEOUT", ""):
            nums = re.findall(r'-?\d+\.\d+', out)
            if len(nums) >= 2:
                self.lat_var.set(nums[0])
                self.lng_var.set(nums[1])
                self.log(f"从cmd获取成功: {nums[0]}, {nums[1]}")
                return

        # 再尝试 dumpsys
        out, _, _ = self.adb("shell dumpsys location")
        for line in out.split("\n"):
            if "latitude" in line.lower() or "lat=" in line.lower():
                nums = re.findall(r'-?\d+\.\d+', line)
                if len(nums) >= 2:
                    self.lat_var.set(nums[0])
                    self.lng_var.set(nums[1])
                    self.log(f"从dumpsys获取成功: {nums[0]}, {nums[1]}")
                    return

        self.log("自动获取失败，请手动输入坐标（百度/高德地图可查到）")
        messagebox.showinfo("提示", "自动获取失败\n请手动输入经纬度")


def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    EnhancedGPSRunner(root)
    root.mainloop()
if __name__ == "__main__":
    main()