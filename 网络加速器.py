import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading
import time
import socket
import os
import re
import subprocess
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
import http.client
import math


def _run_cmd(args):
    result = subprocess.run(args, capture_output=True, timeout=15)
    return result.stdout.decode("utf-8", errors="ignore") + result.stderr.decode("utf-8", errors="ignore")


class NetworkAccelerator:
    DNS_SERVERS = {
        "阿里 DNS (223.5.5.5)": "223.5.5.5",
        "腾讯 DNS (119.29.29.29)": "119.29.29.29",
        "114 DNS (114.114.114.114)": "114.114.114.114",
        "百度 DNS (180.76.76.76)": "180.76.76.76",
        "Google DNS (8.8.8.8)": "8.8.8.8",
        "Cloudflare DNS (1.1.1.1)": "1.1.1.1",
        "OpenDNS (208.67.222.222)": "208.67.222.222",
    }

    TUNING_PRESETS = {
        "游戏加速（低延迟）": {
            "description": "优化 TCP 参数，降低游戏延迟",
            "commands": [
                'netsh int tcp set global ecn=disabled',
                'netsh int tcp set global autotuninglevel=disabled',
                'netsh int tcp set global dca=enabled',
            ]
        },
        "高速下载（大带宽）": {
            "description": "开启自动调优，充分利用大带宽",
            "commands": [
                'netsh int tcp set global autotuninglevel=normal',
                'netsh int tcp set global ecn=enabled',
                'netsh int tcp set global dca=enabled',
            ]
        },
        "网页浏览（平衡）": {
            "description": "平衡配置，适合日常使用",
            "commands": [
                'netsh int tcp set global autotuninglevel=normal',
                'netsh int tcp set global ecn=enabled',
            ]
        },
        "恢复默认": {
            "description": "恢复系统默认网络设置",
            "commands": [
                'netsh int tcp set global autotuninglevel=normal',
                'netsh int tcp set global ecn=enabled',
                'netsh int tcp set global dca=disabled',
            ]
        },
    }

    WIFI_TUNING_PRESETS = {
        "极速优先（推荐）": {
            "description": "强制优先 5GHz、禁用旧协议、重置适配器",
            "actions": ["prefer_5ghz", "disable_legacy", "reset_adapter"]
        },
        "稳定优先": {
            "description": "优化电源管理、重置适配器",
            "actions": ["optimize_power", "reset_adapter"]
        },
        "快速重置": {
            "description": "重置 WiFi 适配器 + 自动重连",
            "actions": ["reset_adapter"]
        },
        "解除优先 5GHz": {
            "description": "恢复默认自动选择频段",
            "actions": ["unprefer_5ghz"]
        },
    }

    CHANNEL_SCAN_2G = [1, 6, 11]
    CHANNEL_SCAN_5G = list(range(36, 149, 4))

    def __init__(self, root):
        self.root = root
        self.root.title("网络加速器 Pro v2.0")
        self.root.geometry("900x680")
        self.root.configure(bg="#f0f0f0")

        self.current_interface = None
        self.wifi_interface = "WLAN"
        self.speedtest_running = False
        self.download_running = False
        self.download_paused = False
        self.download_stop_event = threading.Event()
        self.download_pause_event = threading.Event()
        self.download_pause_event.set()

        self._setup_style()
        self._build_ui()
        self._detect_interface()

    def _setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background="#f0f0f0", padding=5)
        style.configure("TNotebook.Tab", padding=[20, 8], font=("微软雅黑", 10))
        style.configure("TButton", font=("微软雅黑", 10), padding=6)
        style.configure("Speed.TLabel", font=("Consolas", 24, "bold"), foreground="#0078d4",
                        background="#f0f0f0")
        style.configure("Wifi.TLabel", font=("Consolas", 18, "bold"), foreground="#00b050",
                        background="#f0f0f0")
        style.configure("Strong.Horizontal.TProgressbar", troughcolor='#eee', background='#28a745')

    def _build_ui(self):
        title_frame = tk.Frame(self.root, bg="#0078d4", height=50)
        title_frame.pack(fill=tk.X)
        tk.Label(title_frame, text="🚀 网络加速器 Pro v2.0", font=("微软雅黑", 16, "bold"),
                 bg="#0078d4", fg="white").pack(pady=10)

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._build_wifi_tab(notebook)
        self._build_speedtest_tab(notebook)
        self._build_dns_tab(notebook)
        self._build_tuning_tab(notebook)
        self._build_download_tab(notebook)

        status_frame = tk.Frame(self.root, bg="#e0e0e0", height=28)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = tk.Label(status_frame, text="就绪", font=("微软雅黑", 9),
                                     bg="#e0e0e0", fg="#555")
        self.status_label.pack(side=tk.LEFT, padx=10, pady=4)

    # ==================== WiFi 加速模块 ====================
    def _build_wifi_tab(self, notebook):
        tab = tk.Frame(notebook, bg="#f0f0f0")
        notebook.add(tab, text="  📶 WiFi 加速  ")

        status_frame = tk.LabelFrame(tab, text="当前连接状态", font=("微软雅黑", 10),
                                      bg="#f0f0f0", padx=10, pady=10)
        status_frame.pack(fill=tk.X, padx=15, pady=8)

        grid = tk.Frame(status_frame, bg="#f0f0f0")
        grid.pack(fill=tk.X)

        self.wifi_status_label = tk.Label(grid, text="状态: --", font=("微软雅黑", 11),
                                           bg="#f0f0f0", fg="#333")
        self.wifi_status_label.grid(row=0, column=0, padx=15, pady=4, sticky="w")

        self.wifi_ssid_label = tk.Label(grid, text="SSID: --", font=("微软雅黑", 11),
                                         bg="#f0f0f0", fg="#333")
        self.wifi_ssid_label.grid(row=0, column=1, padx=15, pady=4, sticky="w")

        self.wifi_band_label = tk.Label(grid, text="频段: --", font=("微软雅黑", 11),
                                         bg="#f0f0f0", fg="#333")
        self.wifi_band_label.grid(row=0, column=2, padx=15, pady=4, sticky="w")

        self.wifi_channel_label = tk.Label(grid, text="信道: --", font=("微软雅黑", 11),
                                            bg="#f0f0f0", fg="#333")
        self.wifi_channel_label.grid(row=1, column=0, padx=15, pady=4, sticky="w")

        self.wifi_signal_label = tk.Label(grid, text="信号: --", font=("微软雅黑", 11),
                                           bg="#f0f0f0", fg="#333")
        self.wifi_signal_label.grid(row=1, column=1, padx=15, pady=4, sticky="w")

        self.wifi_rate_label = tk.Label(grid, text="速率: --", font=("微软雅黑", 11),
                                         bg="#f0f0f0", fg="#333")
        self.wifi_rate_label.grid(row=1, column=2, padx=15, pady=4, sticky="w")

        self.wifi_signal_bar = ttk.Progressbar(status_frame, mode="determinate",
                                               style="Strong.Horizontal.TProgressbar")
        self.wifi_signal_bar.pack(fill=tk.X, pady=(8, 0))

        btn_row = tk.Frame(tab, bg="#f0f0f0")
        btn_row.pack(fill=tk.X, padx=15, pady=5)

        ttk.Button(btn_row, text="🔄 刷新状态", command=self._refresh_wifi_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="⚡ 一键加速", command=self._one_click_wifi_boost).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="📡 扫描信道", command=self._scan_channels).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="🔌 重置适配器", command=self._reset_wifi_adapter).pack(side=tk.LEFT, padx=5)

        preset_frame = tk.LabelFrame(tab, text="WiFi 优化方案", font=("微软雅黑", 10),
                                     bg="#f0f0f0", padx=10, pady=8)
        preset_frame.pack(fill=tk.X, padx=15, pady=5)

        self.wifi_preset_var = tk.StringVar(value="极速优先（推荐）")
        presets_row = tk.Frame(preset_frame, bg="#f0f0f0")
        presets_row.pack(fill=tk.X)
        for name in self.WIFI_TUNING_PRESETS:
            tk.Radiobutton(presets_row, text=name, variable=self.wifi_preset_var,
                           value=name, font=("微软雅黑", 10), bg="#f0f0f0").pack(side=tk.LEFT, padx=8)

        ttk.Button(preset_frame, text="应用此方案", command=self._apply_wifi_preset).pack(pady=5)

        scan_frame = tk.LabelFrame(tab, text="附近 WiFi 与信道分析", font=("微软雅黑", 10),
                                    bg="#f0f0f0", padx=5, pady=5)
        scan_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)

        columns = ("ssid", "signal", "band", "channel", "phy", "bssid")
        self.wifi_tree = ttk.Treeview(scan_frame, columns=columns, show="headings", height=8)
        self.wifi_tree.heading("ssid", text="SSID")
        self.wifi_tree.heading("signal", text="信号")
        self.wifi_tree.heading("band", text="频段")
        self.wifi_tree.heading("channel", text="信道")
        self.wifi_tree.heading("phy", text="协议")
        self.wifi_tree.heading("bssid", text="BSSID")
        self.wifi_tree.column("ssid", width=150)
        self.wifi_tree.column("signal", width=70, anchor=tk.CENTER)
        self.wifi_tree.column("band", width=80, anchor=tk.CENTER)
        self.wifi_tree.column("channel", width=60, anchor=tk.CENTER)
        self.wifi_tree.column("phy", width=80, anchor=tk.CENTER)
        self.wifi_tree.column("bssid", width=130)

        vsb = ttk.Scrollbar(scan_frame, orient="vertical", command=self.wifi_tree.yview)
        self.wifi_tree.configure(yscrollcommand=vsb.set)
        self.wifi_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.channel_log = tk.Label(tab, text="提示：扫描后会自动分析信道拥挤度",
                                     font=("微软雅黑", 9), bg="#f0f0f0", fg="#666")
        self.channel_log.pack(pady=2)

        self._refresh_wifi_status()
        self.root.after(3000, self._start_wifi_monitor)

    def _start_wifi_monitor(self):
        self._refresh_wifi_status(silent=True)
        self.root.after(5000, self._start_wifi_monitor)

    def _refresh_wifi_status(self, silent=False):
        def do():
            try:
                output = _run_cmd(["netsh", "wlan", "show", "interfaces"])
                info = self._parse_wifi_interfaces(output)
                if info:
                    self.wifi_interface = info.get("ifname", self.wifi_interface)
                    self.wifi_status_label.config(text=f"状态: {info.get('status', '--')}")
                    self.wifi_ssid_label.config(text=f"SSID: {info.get('ssid', '--')}")
                    self.wifi_band_label.config(text=f"频段: {info.get('band', '--')}")
                    self.wifi_channel_label.config(text=f"信道: {info.get('channel', '--')}")
                    sig = info.get("signal", 0)
                    self.wifi_signal_label.config(text=f"信号: {sig}%")
                    self.wifi_rate_label.config(
                        text=f"速率: {info.get('rx_rate', '--')} / {info.get('tx_rate', '--')} Mbps")
                    self.wifi_signal_bar.config(value=sig)
                elif not silent:
                    messagebox.showwarning("提示", "未找到 WiFi 接口，请确认已连接 WiFi")
            except Exception as e:
                if not silent:
                    self.channel_log.config(text=f"刷新失败: {e}")

        threading.Thread(target=do, daemon=True).start()

    @staticmethod
    def _parse_wifi_interfaces(output):
        info = {}
        m = re.search(r"名称\s*:\s*(.+)", output)
        if m:
            info["ifname"] = m.group(1).strip()
        m = re.search(r"状态\s*:\s*(.+)", output)
        if m:
            info["status"] = m.group(1).strip()
        m = re.search(r"SSID\s*:\s*(.+)", output)
        if m:
            info["ssid"] = m.group(1).strip()
        m = re.search(r"波段\s*:\s*(.+)", output)
        if m:
            info["band"] = m.group(1).strip()
        m = re.search(r"通道\s*:\s*(\d+)", output)
        if m:
            info["channel"] = m.group(1)
        m = re.search(r"接收速率\(Mbps\)\s*:\s*([\d.]+)", output)
        if m:
            info["rx_rate"] = m.group(1)
        m = re.search(r"传输速率.*?\(Mbps\)\s*:\s*([\d.]+)", output)
        if m:
            info["tx_rate"] = m.group(1)
        m = re.search(r"信号\s*:\s*(\d+)%", output)
        if m:
            info["signal"] = int(m.group(1))
        return info

    def _scan_channels(self):
        def run():
            self.channel_log.config(text="正在扫描附近 WiFi...")
            try:
                output = _run_cmd(["netsh", "wlan", "show", "networks", "mode=bssid"])
                networks = self._parse_wifi_networks(output)
                self._update_ui(lambda: self._fill_wifi_tree(networks))
                analysis = self._analyze_channels(networks)
                self._update_ui(lambda: self.channel_log.config(text=analysis))
            except Exception as e:
                self._update_ui(lambda: self.channel_log.config(text=f"扫描失败: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def _fill_wifi_tree(self, networks):
        for item in self.wifi_tree.get_children():
            self.wifi_tree.delete(item)
        seen = set()
        for net in networks:
            key = (net.get("ssid", ""), net.get("bssid", ""))
            if key in seen:
                continue
            seen.add(key)
            self.wifi_tree.insert("", tk.END, values=(
                net.get("ssid", ""),
                f"{net.get('signal', 0)}%",
                net.get("band", ""),
                net.get("channel", ""),
                net.get("phy", ""),
                net.get("bssid", ""),
            ))

    @staticmethod
    def _parse_wifi_networks(output):
        networks = []
        current_ssid = None
        for line in output.splitlines():
            line = line.strip()
            m = re.match(r"SSID \d+\s*:\s*(.+)", line)
            if m:
                current_ssid = m.group(1).strip()
                continue
            m = re.match(r"BSSID \d+\s*:\s*([0-9a-fA-F:]+)", line)
            if m and current_ssid:
                bssid = m.group(1).strip()
                net = {"ssid": current_ssid, "bssid": bssid}
                networks.append(net)
                continue
            if networks:
                last = networks[-1]
                m = re.match(r"信号\s*:\s*(\d+)%", line)
                if m:
                    last["signal"] = int(m.group(1))
                    continue
                m = re.match(r"无线电类型\s*:\s*(.+)", line)
                if m:
                    last["phy"] = m.group(1).strip()
                    continue
                m = re.match(r"波段\s*:\s*(.+)", line)
                if m:
                    last["band"] = m.group(1).strip()
                    continue
                m = re.match(r"频道\s*:\s*(\d+)", line)
                if m:
                    last["channel"] = int(m.group(1))
                    continue
        return networks

    def _analyze_channels(self, networks):
        count_2g = {}
        count_5g = {}
        for net in networks:
            band = net.get("band", "")
            ch = net.get("channel")
            if ch is None:
                continue
            if "2.4" in band:
                count_2g[ch] = count_2g.get(ch, 0) + 1
            elif "5" in band:
                count_5g[ch] = count_5g.get(ch, 0) + 1

        def best_channel(counts, preferred):
            best = None
            best_crowd = float("inf")
            for ch in preferred:
                c = counts.get(ch, 0)
                if c < best_crowd:
                    best_crowd = c
                    best = ch
            return best, best_crowd

        lines = [f"共扫描到 {len(networks)} 个 WiFi BSSID"]
        if count_2g:
            ch, crowd = best_channel(count_2g, self.CHANNEL_SCAN_2G)
            lines.append(f"2.4GHz 最佳信道: {ch} (拥挤度: {crowd})")
        if count_5g:
            ch, crowd = best_channel(count_5g, self.CHANNEL_SCAN_5G)
            lines.append(f"5GHz 最佳信道: {ch} (拥挤度: {crowd})")
        lines.append("建议：登录路由器后台修改信道")
        return "  |  ".join(lines)

    def _one_click_wifi_boost(self):
        if not messagebox.askyesno("确认", "将执行以下操作：\n1. 优先使用 5GHz\n2. 重置 WiFi 适配器\n3. 自动重连\n\n建议在联网状态良好时执行"):
            return
        def run():
            self.channel_log.config(text="正在执行一键加速...")
            steps = [
                ("优先 5GHz", self._set_prefer_5ghz),
                ("重置适配器", self._reset_wifi_adapter_impl),
            ]
            for name, fn in steps:
                try:
                    self._update_ui(lambda n=name: self.channel_log.config(text=f"正在 {n}..."))
                    fn()
                    time.sleep(2)
                except Exception as e:
                    self._update_ui(lambda n=name, err=e: self.channel_log.config(text=f"{n} 失败: {err}"))
            self._update_ui(lambda: self.channel_log.config(text="✅ 一键加速完成!"))
            self._refresh_wifi_status()
        threading.Thread(target=run, daemon=True).start()

    def _apply_wifi_preset(self):
        name = self.wifi_preset_var.get()
        preset = self.WIFI_TUNING_PRESETS[name]
        if not messagebox.askyesno("确认", f"应用「{name}」?\n{preset['description']}"):
            return

        def run():
            self.channel_log.config(text=f"应用: {name}")
            for action in preset["actions"]:
                try:
                    self._update_ui(lambda a=action: self.channel_log.config(text=f"执行 {a}..."))
                    if action == "prefer_5ghz":
                        self._set_prefer_5ghz()
                    elif action == "unprefer_5ghz":
                        self._unset_prefer_5ghz()
                    elif action == "disable_legacy":
                        self._disable_legacy_rates()
                    elif action == "optimize_power":
                        self._optimize_power_save()
                    elif action == "reset_adapter":
                        self._reset_wifi_adapter_impl()
                    time.sleep(1.5)
                except Exception as e:
                    self._update_ui(lambda a=action, err=e: self.channel_log.config(text=f"{a} 失败: {err}"))
            self._update_ui(lambda: self.channel_log.config(text="✅ 方案应用完成!"))
            self._refresh_wifi_status()

        threading.Thread(target=run, daemon=True).start()

    def _set_prefer_5ghz(self):
        self._run_netsh(["wlan", "set", "autoconfig", "setting",
                          f"interface={self.wifi_interface}",
                          "preferredband=prefer_5ghz"])

    def _unset_prefer_5ghz(self):
        self._run_netsh(["wlan", "set", "autoconfig", "setting",
                          f"interface={self.wifi_interface}",
                          "preferredband=prefer_2ghz"])

    def _disable_legacy_rates(self):
        self._run_netsh(["wlan", "set", "autoconfig", "setting",
                          f"interface={self.wifi_interface}",
                          "uselegacyrates=disabled"])

    def _optimize_power_save(self):
        self._run_netsh(["wlan", "set", "autoconfig", "setting",
                          f"interface={self.wifi_interface}",
                          "powersavemode=low"])

    def _reset_wifi_adapter(self):
        if not messagebox.askyesno("确认", "重置 WiFi 适配器会短暂断网，是否继续？"):
            return
        threading.Thread(target=self._reset_wifi_adapter_impl, daemon=True).start()

    def _reset_wifi_adapter_impl(self):
        self._update_ui(lambda: self.channel_log.config(text="正在禁用 WiFi 适配器..."))
        self._run_netsh(["interface", "set", "interface", f"name={self.wifi_interface}", "admin=disable"])
        time.sleep(3)
        self._update_ui(lambda: self.channel_log.config(text="正在启用 WiFi 适配器..."))
        self._run_netsh(["interface", "set", "interface", f"name={self.wifi_interface}", "admin=enable"])
        time.sleep(2)
        self._update_ui(lambda: self.channel_log.config(text="✅ WiFi 适配器已重置"))
        self._refresh_wifi_status()

    def _run_netsh(self, args):
        full = ["netsh"] + args
        return _run_cmd(full)

    # ==================== 测速模块 ====================
    def _build_speedtest_tab(self, notebook):
        tab = tk.Frame(notebook, bg="#f0f0f0")
        notebook.add(tab, text="  ⚡ 网络测速  ")

        top = tk.Frame(tab, bg="#f0f0f0")
        top.pack(pady=15)

        self.latency_label = tk.Label(top, text="延迟: -- ms", font=("微软雅黑", 12),
                                       bg="#f0f0f0", fg="#333")
        self.latency_label.grid(row=0, column=0, padx=30, pady=5)

        self.jitter_label = tk.Label(top, text="抖动: -- ms", font=("微软雅黑", 12),
                                      bg="#f0f0f0", fg="#333")
        self.jitter_label.grid(row=0, column=1, padx=30, pady=5)

        self.loss_label = tk.Label(top, text="丢包率: -- %", font=("微软雅黑", 12),
                                    bg="#f0f0f0", fg="#333")
        self.loss_label.grid(row=0, column=2, padx=30, pady=5)

        speed_frame = tk.Frame(tab, bg="#f0f0f0")
        speed_frame.pack(pady=20)

        tk.Label(speed_frame, text="↓ 下载速度", font=("微软雅黑", 12),
                 bg="#f0f0f0").grid(row=0, column=0, padx=40)
        self.download_speed_label = ttk.Label(speed_frame, text="0.00", style="Speed.TLabel")
        self.download_speed_label.grid(row=1, column=0, padx=40)
        self.download_unit_label = tk.Label(speed_frame, text="Mbps", font=("微软雅黑", 10),
                                             bg="#f0f0f0", fg="#666")
        self.download_unit_label.grid(row=2, column=0, padx=40)

        tk.Label(speed_frame, text="↑ 上传速度", font=("微软雅黑", 12),
                 bg="#f0f0f0").grid(row=0, column=1, padx=40)
        self.upload_speed_label = ttk.Label(speed_frame, text="0.00", style="Speed.TLabel")
        self.upload_speed_label.grid(row=1, column=1, padx=40)
        self.upload_unit_label = tk.Label(speed_frame, text="Mbps", font=("微软雅黑", 10),
                                           bg="#f0f0f0", fg="#666")
        self.upload_unit_label.grid(row=2, column=1, padx=40)

        self.progress = ttk.Progressbar(tab, mode="indeterminate", length=400)
        self.progress.pack(pady=10)

        self.test_btn = ttk.Button(tab, text="开始测速", command=self._start_speedtest)
        self.test_btn.pack(pady=10)

        self.test_log = scrolledtext.ScrolledText(tab, height=8, font=("Consolas", 9), state=tk.DISABLED)
        self.test_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def _start_speedtest(self):
        if self.speedtest_running:
            return
        self.speedtest_running = True
        self.test_btn.config(state=tk.DISABLED)
        self.progress.start(10)
        for label in [self.latency_label, self.jitter_label, self.loss_label,
                      self.download_speed_label, self.upload_speed_label]:
            label.config(text="--")
        self._log("开始网络测速...")
        threading.Thread(target=self._run_speedtest, daemon=True).start()

    def _run_speedtest(self):
        try:
            self._update_status("正在测试延迟...")
            latency, jitter, loss = self._test_latency()
            self._update_ui(lambda: self.latency_label.config(text=f"延迟: {latency:.1f} ms"))
            self._update_ui(lambda: self.jitter_label.config(text=f"抖动: {jitter:.1f} ms"))
            self._update_ui(lambda: self.loss_label.config(text=f"丢包率: {loss:.1f}%"))
            self._log(f"延迟: {latency:.1f}ms  抖动: {jitter:.1f}ms  丢包率: {loss:.1f}%")

            self._update_status("正在测试下载速度...")
            dl_speed = self._test_download_speed()
            self._update_ui(lambda: self.download_speed_label.config(text=f"{dl_speed:.2f}"))
            self._log(f"下载速度: {dl_speed:.2f} Mbps")

            self._update_status("正在测试上传速度...")
            ul_speed = self._test_upload_speed()
            self._update_ui(lambda: self.upload_speed_label.config(text=f"{ul_speed:.2f}"))
            self._log(f"上传速度: {ul_speed:.2f} Mbps")

            self._log("测速完成!")
            self._update_status("测速完成")
        except Exception as e:
            self._log(f"测速出错: {e}")
            self._update_status("测速失败")
        finally:
            self.speedtest_running = False
            self._update_ui(lambda: self.test_btn.config(state=tk.NORMAL))
            self._update_ui(self.progress.stop)

    def _test_latency(self):
        targets = ["www.baidu.com", "www.qq.com", "www.taobao.com"]
        times = []
        success = 0
        total = 0
        for target in targets:
            for _ in range(3):
                total += 1
                try:
                    start = time.time()
                    sock = socket.create_connection((target, 80), timeout=3)
                    sock.close()
                    elapsed = (time.time() - start) * 1000
                    times.append(elapsed)
                    success += 1
                except Exception:
                    pass
                time.sleep(0.2)
        if not times:
            return 0, 0, 100.0
        latency = sum(times) / len(times)
        jitter = math.sqrt(sum((t - latency) ** 2 for t in times) / len(times))
        loss = (total - success) / total * 100 if total > 0 else 0
        return latency, jitter, loss

    def _test_download_speed(self):
        urls = [
            "http://speedtest.tele2.net/1MB.zip",
            "http://speedtest.tele2.net/10MB.zip",
        ]
        total_bytes = 0
        start = time.time()
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        total_bytes += len(chunk)
            except Exception:
                continue
        elapsed = time.time() - start
        if elapsed < 0.5:
            elapsed = 0.5
        return (total_bytes * 8) / elapsed / 1_000_000

    def _test_upload_speed(self):
        test_data = b"x" * 1_000_000
        start = time.time()
        try:
            req = urllib.request.Request(
                "http://speedtest.tele2.net/upload.php",
                data=test_data,
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/octet-stream"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
        except Exception:
            try:
                http = http.client.HTTPConnection("httpbin.org", timeout=10)
                http.request("POST", "/post", body=test_data)
                http.getresponse()
                http.close()
            except Exception:
                return 0.0
        elapsed = time.time() - start
        if elapsed < 0.5:
            elapsed = 0.5
        return (len(test_data) * 8) / elapsed / 1_000_000

    # ==================== DNS 优化模块 ====================
    def _build_dns_tab(self, notebook):
        tab = tk.Frame(notebook, bg="#f0f0f0")
        notebook.add(tab, text="  🔧 DNS 优化  ")

        info_frame = tk.LabelFrame(tab, text="当前 DNS 配置", font=("微软雅黑", 10),
                                    bg="#f0f0f0", padx=10, pady=10)
        info_frame.pack(fill=tk.X, padx=20, pady=10)

        self.dns_info = tk.Text(info_frame, height=4, font=("Consolas", 10),
                                 state=tk.DISABLED, bg="white")
        self.dns_info.pack(fill=tk.X)

        refresh_btn = ttk.Button(info_frame, text="刷新", command=self._refresh_dns_info)
        refresh_btn.pack(pady=5)

        test_frame = tk.LabelFrame(tab, text="DNS 延迟测试", font=("微软雅黑", 10),
                                    bg="#f0f0f0", padx=10, pady=10)
        test_frame.pack(fill=tk.X, padx=20, pady=10)

        columns = ("dns", "primary", "secondary", "latency")
        self.dns_tree = ttk.Treeview(test_frame, columns=columns, show="headings", height=6)
        self.dns_tree.heading("dns", text="DNS 名称")
        self.dns_tree.heading("primary", text="主 DNS")
        self.dns_tree.heading("secondary", text="备 DNS")
        self.dns_tree.heading("latency", text="延迟(ms)")
        self.dns_tree.column("dns", width=180)
        self.dns_tree.column("primary", width=120)
        self.dns_tree.column("secondary", width=120)
        self.dns_tree.column("latency", width=100)
        self.dns_tree.pack(fill=tk.X)

        btn_frame = tk.Frame(tab, bg="#f0f0f0")
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="测试所有 DNS", command=self._test_all_dns).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="应用选中 DNS", command=self._apply_dns).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="自动选择最快", command=self._auto_best_dns).pack(side=tk.LEFT, padx=10)

        hint = tk.Label(tab, text="提示：应用 DNS 需要管理员权限",
                         font=("微软雅黑", 9), bg="#f0f0f0", fg="#888")
        hint.pack(pady=5)

        self._refresh_dns_info()
        self._load_dns_list()

    def _detect_interface(self):
        try:
            output = _run_cmd(["netsh", "interface", "show", "interface"])
            for line in output.split("\n"):
                if "已连接" in line or "connected" in line.lower():
                    parts = line.split()
                    if len(parts) >= 4:
                        self.current_interface = parts[-1]
                        break
        except Exception:
            pass

    def _refresh_dns_info(self):
        self.dns_info.config(state=tk.NORMAL)
        self.dns_info.delete("1.0", tk.END)
        try:
            output = _run_cmd(["netsh", "interface", "ipv4", "show", "dnsservers"])
            self.dns_info.insert(tk.END, output if output else "无法获取 DNS 信息")
        except Exception as e:
            self.dns_info.insert(tk.END, f"获取失败: {e}")
        self.dns_info.config(state=tk.DISABLED)

    def _load_dns_list(self):
        for item in self.dns_tree.get_children():
            self.dns_tree.delete(item)
        dns_pairs = list(self.DNS_SERVERS.items())
        for i in range(0, len(dns_pairs) - 1, 2):
            name1, ip1 = dns_pairs[i]
            ip2 = dns_pairs[i + 1][1] if i + 1 < len(dns_pairs) else ""
            self.dns_tree.insert("", tk.END, values=(name1, ip1, ip2, "未测试"))
        if len(dns_pairs) % 2 == 1:
            name, ip = dns_pairs[-1]
            self.dns_tree.insert("", tk.END, values=(name, ip, "", "未测试"))

    def _test_all_dns(self):
        threading.Thread(target=self._run_dns_test, daemon=True).start()

    def _run_dns_test(self):
        self._update_status("正在测试 DNS...")
        for item in self.dns_tree.get_children():
            values = list(self.dns_tree.item(item, "values"))
            ip = values[1]
            latency = self._ping_dns(ip)
            values[3] = f"{latency:.1f}" if latency > 0 else "超时"
            self._update_ui(lambda v=values, i=item: self.dns_tree.item(i, values=v))
        self._update_status("DNS 测试完成")

    def _ping_dns(self, ip, count=3):
        times = []
        for _ in range(count):
            try:
                start = time.time()
                sock = socket.create_connection((ip, 53), timeout=2)
                sock.close()
                times.append((time.time() - start) * 1000)
            except Exception:
                continue
        return sum(times) / len(times) if times else -1

    def _auto_best_dns(self):
        def run():
            self._update_status("自动选择最快 DNS...")
            best_item = None
            best_latency = float("inf")
            for item in self.dns_tree.get_children():
                values = list(self.dns_tree.item(item, "values"))
                ip = values[1]
                latency = self._ping_dns(ip)
                values[3] = f"{latency:.1f}" if latency > 0 else "超时"
                self._update_ui(lambda v=values, i=item: self.dns_tree.item(i, values=v))
                if 0 < latency < best_latency:
                    best_latency = latency
                    best_item = item
            if best_item:
                self.dns_tree.selection_set(best_item)
                self._apply_dns()
            else:
                messagebox.showwarning("提示", "没有可用的 DNS 服务器")
            self._update_status("自动选择完成")
        threading.Thread(target=run, daemon=True).start()

    def _apply_dns(self):
        selected = self.dns_tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一个 DNS 服务器")
            return
        if not self.current_interface:
            messagebox.showerror("错误", "未检测到活动网络接口")
            return
        item = self.dns_tree.item(selected[0])
        primary = item["values"][1]
        secondary = item["values"][2]
        try:
            _run_cmd(["netsh", "interface", "ipv4", "set", "dnsservers",
                      f"name={self.current_interface}", "static", primary, "primary"])
            if secondary:
                _run_cmd(["netsh", "interface", "ipv4", "add", "dnsservers",
                          f"name={self.current_interface}", secondary, "index=2"])
            messagebox.showinfo("成功", f"DNS 已设置为:\n主: {primary}\n备: {secondary}")
            self._refresh_dns_info()
        except Exception as e:
            messagebox.showerror("失败", f"设置 DNS 失败: {e}\n请以管理员身份运行")

    # ==================== TCP 调优模块 ====================
    def _build_tuning_tab(self, notebook):
        tab = tk.Frame(notebook, bg="#f0f0f0")
        notebook.add(tab, text="  ⚙️ TCP 调优  ")

        tk.Label(tab, text="选择优化方案：", font=("微软雅黑", 11), bg="#f0f0f0").pack(pady=10)

        self.tuning_var = tk.StringVar(value="游戏加速（低延迟）")
        for name in self.TUNING_PRESETS:
            preset = self.TUNING_PRESETS[name]
            frame = tk.Frame(tab, bg="#f0f0f0")
            frame.pack(fill=tk.X, padx=30, pady=4)
            tk.Radiobutton(frame, text=name, variable=self.tuning_var, value=name,
                           font=("微软雅黑", 11), bg="#f0f0f0",
                           command=self._update_tuning_desc).pack(side=tk.LEFT)

        self.tuning_desc = tk.Label(tab, text="", font=("微软雅黑", 10),
                                     bg="#e8e8e8", fg="#555", wraplength=600,
                                     justify=tk.LEFT, padx=10, pady=10)
        self.tuning_desc.pack(fill=tk.X, padx=30, pady=10)

        ttk.Button(tab, text="应用优化", command=self._apply_tuning).pack(pady=5)

        log_frame = tk.LabelFrame(tab, text="执行日志", font=("微软雅黑", 10),
                                   bg="#f0f0f0", padx=5, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.tuning_log = scrolledtext.ScrolledText(log_frame, height=10,
                                                     font=("Consolas", 9), state=tk.DISABLED)
        self.tuning_log.pack(fill=tk.BOTH, expand=True)

        self._update_tuning_desc()

    def _update_tuning_desc(self):
        name = self.tuning_var.get()
        preset = self.TUNING_PRESETS[name]
        desc = preset["description"] + "\n\n执行命令：\n"
        for cmd in preset["commands"]:
            desc += f"  {cmd}\n"
        self.tuning_desc.config(text=desc)

    def _apply_tuning(self):
        name = self.tuning_var.get()
        preset = self.TUNING_PRESETS[name]
        if not messagebox.askyesno("确认", f"确定要应用「{name}」方案吗？\n{preset['description']}"):
            return
        self._update_tuning_log(f"正在应用: {name}...\n")
        success_count = 0
        for cmd in preset["commands"]:
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
                status = "✓" if result.returncode == 0 else "✗"
                self._update_tuning_log(f"{status} {cmd}\n")
                if result.returncode == 0:
                    success_count += 1
                err = (result.stderr or b"").decode("utf-8", errors="ignore").strip()
                if err:
                    self._update_tuning_log(f"  输出: {err}\n")
            except Exception as e:
                self._update_tuning_log(f"✗ {cmd} - {e}\n")
        self._update_tuning_log(f"\n完成！成功 {success_count}/{len(preset['commands'])}\n")
        messagebox.showinfo("完成", "优化已应用。建议重启浏览器或电脑以获得最佳效果。")

    def _update_tuning_log(self, msg):
        self.tuning_log.config(state=tk.NORMAL)
        self.tuning_log.insert(tk.END, msg)
        self.tuning_log.see(tk.END)
        self.tuning_log.config(state=tk.DISABLED)

    # ==================== 多线程下载模块 ====================
    def _build_download_tab(self, notebook):
        tab = tk.Frame(notebook, bg="#f0f0f0")
        notebook.add(tab, text="  ⬇️ 多线程下载  ")

        url_frame = tk.Frame(tab, bg="#f0f0f0")
        url_frame.pack(fill=tk.X, padx=20, pady=10)
        tk.Label(url_frame, text="下载链接:", font=("微软雅黑", 10), bg="#f0f0f0").pack(side=tk.LEFT)
        self.download_url = tk.StringVar()
        tk.Entry(url_frame, textvariable=self.download_url, width=55,
                 font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)

        save_frame = tk.Frame(tab, bg="#f0f0f0")
        save_frame.pack(fill=tk.X, padx=20, pady=5)
        tk.Label(save_frame, text="保存路径:", font=("微软雅黑", 10), bg="#f0f0f0").pack(side=tk.LEFT)
        self.save_path = tk.StringVar(value=os.path.expanduser("~"))
        tk.Entry(save_frame, textvariable=self.save_path, width=48,
                 font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        ttk.Button(save_frame, text="浏览", command=self._choose_path).pack(side=tk.LEFT)

        thread_frame = tk.Frame(tab, bg="#f0f0f0")
        thread_frame.pack(fill=tk.X, padx=20, pady=5)
        tk.Label(thread_frame, text="线程数:", font=("微软雅黑", 10), bg="#f0f0f0").pack(side=tk.LEFT)
        self.thread_count = tk.IntVar(value=8)
        tk.Scale(thread_frame, from_=1, to=32, orient=tk.HORIZONTAL,
                 variable=self.thread_count, bg="#f0f0f0",
                 length=300, showvalue=True).pack(side=tk.LEFT, padx=10)

        btn_frame = tk.Frame(tab, bg="#f0f0f0")
        btn_frame.pack(pady=10)
        self.dl_start_btn = ttk.Button(btn_frame, text="开始下载", command=self._start_download)
        self.dl_start_btn.pack(side=tk.LEFT, padx=5)
        self.dl_pause_btn = ttk.Button(btn_frame, text="暂停", command=self._pause_download,
                                        state=tk.DISABLED)
        self.dl_pause_btn.pack(side=tk.LEFT, padx=5)
        self.dl_stop_btn = ttk.Button(btn_frame, text="取消", command=self._stop_download,
                                       state=tk.DISABLED)
        self.dl_stop_btn.pack(side=tk.LEFT, padx=5)

        progress_frame = tk.LabelFrame(tab, text="下载进度", font=("微软雅黑", 10),
                                        bg="#f0f0f0", padx=5, pady=5)
        progress_frame.pack(fill=tk.X, padx=20, pady=5)
        self.download_progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.download_progress.pack(fill=tk.X, pady=5)
        self.download_info = tk.Label(progress_frame, text="等待开始...",
                                       font=("微软雅黑", 10), bg="#f0f0f0")
        self.download_info.pack()

        log_frame = tk.LabelFrame(tab, text="下载日志", font=("微软雅黑", 10),
                                   bg="#f0f0f0", padx=5, pady=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        self.download_log = scrolledtext.ScrolledText(log_frame, height=10,
                                                       font=("Consolas", 9), state=tk.DISABLED)
        self.download_log.pack(fill=tk.BOTH, expand=True)

    def _choose_path(self):
        path = filedialog.askdirectory(initialdir=self.save_path.get())
        if path:
            self.save_path.set(path)

    def _start_download(self):
        url = self.download_url.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入下载链接")
            return
        if self.download_running:
            return
        self.download_running = True
        self.download_stop_event.clear()
        self.download_pause_event.set()
        self.dl_start_btn.config(state=tk.DISABLED)
        self.dl_pause_btn.config(state=tk.NORMAL)
        self.dl_stop_btn.config(state=tk.NORMAL)
        threading.Thread(target=self._run_download, args=(url,), daemon=True).start()

    def _pause_download(self):
        if self.download_paused:
            self.download_pause_event.set()
            self.dl_pause_btn.config(text="暂停")
            self.download_paused = False
            self._log_dl("继续下载...")
        else:
            self.download_pause_event.clear()
            self.dl_pause_btn.config(text="继续")
            self.download_paused = True
            self._log_dl("下载已暂停")

    def _stop_download(self):
        self.download_stop_event.set()
        self.download_pause_event.set()
        self._log_dl("正在取消下载...")

    def _run_download(self, url):
        try:
            filename = url.split("/")[-1] or "download.bin"
            if "." not in filename:
                filename += ".bin"
            save_path = os.path.join(self.save_path.get(), filename)

            req = urllib.request.Request(url, method="HEAD",
                                          headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                total_size = int(resp.headers.get("Content-Length", 0))
                accept_ranges = resp.headers.get("Accept-Ranges", "") == "bytes"

            if total_size == 0 or not accept_ranges:
                self._log_dl("服务器不支持多线程，使用单线程下载")
                self._single_thread_download(url, save_path)
                return

            threads = min(self.thread_count.get(), max(1, total_size // (1024 * 1024) + 1))
            part_size = total_size // threads
            self._log_dl(f"文件大小: {self._format_size(total_size)}, 使用 {threads} 线程")

            with open(save_path, "wb") as f:
                f.truncate(total_size)

            downloaded = [0]
            lock = threading.Lock()
            start_time = time.time()

            def download_part(thread_id, start, end):
                if self.download_stop_event.is_set():
                    return
                headers = {"User-Agent": "Mozilla/5.0", "Range": f"bytes={start}-{end}"}
                try:
                    req_part = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req_part, timeout=60) as resp:
                        part_data = resp.read()
                    with open(save_path, "r+b") as f:
                        f.seek(start)
                        f.write(part_data)
                    with lock:
                        downloaded[0] += len(part_data)
                except Exception as e:
                    self._log_dl(f"线程 {thread_id} 错误: {e}")

            ranges = []
            for i in range(threads):
                s = i * part_size
                e = s + part_size - 1 if i < threads - 1 else total_size - 1
                ranges.append((i, s, e))

            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = [executor.submit(download_part, tid, s, e) for tid, s, e in ranges]

                while not all(f.done() for f in futures):
                    if self.download_stop_event.is_set():
                        executor.shutdown(wait=False)
                        break
                    self.download_pause_event.wait()
                    done = downloaded[0]
                    pct = done / total_size * 100 if total_size > 0 else 0
                    elapsed = time.time() - start_time
                    speed = done / elapsed if elapsed > 0 else 0
                    self._update_ui(lambda p=pct, d=done, t=total_size,
                                     s=speed: self._update_download_ui(p, d, t, s))
                    time.sleep(0.3)

            if self.download_stop_event.is_set():
                self._log_dl("下载已取消")
                try:
                    os.remove(save_path)
                except Exception:
                    pass
            else:
                self._log_dl(f"下载完成: {save_path}")
                self._update_ui(lambda: self.download_progress.config(value=100))
                self._update_ui(lambda: self.download_info.config(text="下载完成 ✓"))

        except Exception as e:
            self._log_dl(f"下载失败: {e}")
        finally:
            self.download_running = False
            self.download_paused = False
            self._update_ui(lambda: self.dl_start_btn.config(state=tk.NORMAL))
            self._update_ui(lambda: self.dl_pause_btn.config(state=tk.DISABLED, text="暂停"))
            self._update_ui(lambda: self.dl_stop_btn.config(state=tk.DISABLED))

    def _single_thread_download(self, url, save_path):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                start = time.time()
                with open(save_path, "wb") as f:
                    while True:
                        if self.download_stop_event.is_set():
                            break
                        self.download_pause_event.wait()
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        pct = downloaded / total * 100 if total > 0 else 0
                        speed = downloaded / (time.time() - start)
                        self._update_ui(lambda p=pct, d=downloaded, t=total,
                                         s=speed: self._update_download_ui(p, d, t, s))
                if self.download_stop_event.is_set():
                    os.remove(save_path)
                    self._log_dl("下载已取消")
                else:
                    self._log_dl(f"下载完成: {save_path}")
        except Exception as e:
            self._log_dl(f"下载失败: {e}")

    def _update_download_ui(self, pct, done, total, speed):
        self.download_progress.config(value=pct)
        info = f"{pct:.1f}%  |  {self._format_size(done)} / {self._format_size(total)}"
        info += f"  |  速度: {self._format_size(speed)}/s"
        self.download_info.config(text=info)

    @staticmethod
    def _format_size(size):
        if size < 1024:
            return f"{size:.1f} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.2f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.2f} GB"

    # ==================== 工具方法 ====================
    def _log(self, msg):
        def do():
            self.test_log.config(state=tk.NORMAL)
            self.test_log.insert(tk.END, msg + "\n")
            self.test_log.see(tk.END)
            self.test_log.config(state=tk.DISABLED)
        self._update_ui(do)

    def _log_dl(self, msg):
        def do():
            self.download_log.config(state=tk.NORMAL)
            self.download_log.insert(tk.END, msg + "\n")
            self.download_log.see(tk.END)
            self.download_log.config(state=tk.DISABLED)
        self._update_ui(do)

    def _update_status(self, msg):
        self._update_ui(lambda: self.status_label.config(text=msg))

    def _update_ui(self, func):
        self.root.after(0, func)


if __name__ == "__main__":
    root = tk.Tk()
    app = NetworkAccelerator(root)
    root.mainloop()