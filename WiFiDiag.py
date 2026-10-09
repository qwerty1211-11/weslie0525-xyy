# -*- coding: utf-8 -*-
"""
随身WiFi 网络诊断与优化工具
单文件 GUI 程序，仅标准库。
启动：python WiFiDiag.py
"""

import os
import sys
import socket
import struct
import time
import threading
import subprocess
import re
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_cmd(cmd, timeout=15):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, encoding='gbk', errors='replace'
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[超时]"
    except Exception as e:
        return f"[错误: {e}]"


def ping_once(host, timeout_ms=2000):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        sock.settimeout(timeout_ms / 1000.0)
        icmp_id = os.getpid() & 0xFFFF
        packet = struct.pack('!BBHHH', 8, 0, 0, icmp_id, 1) + b'A' * 56
        checksum = 0
        for i in range(0, len(packet), 2):
            checksum += (packet[i] << 8) + packet[i + 1]
        checksum = (checksum >> 16) + (checksum & 0xFFFF)
        checksum = (~checksum) & 0xFFFF
        packet = struct.pack('!BBHHH', 8, 0, socket.htons(checksum), icmp_id, 1) + b'A' * 56
        start = time.time()
        sock.sendto(packet, (host, 1))
        sock.recvfrom(1024)
        rtt = (time.time() - start) * 1000
        sock.close()
        return rtt
    except Exception:
        return None


def ping_aggregate(host, count=4):
    times = []
    for _ in range(count):
        t = ping_once(host)
        if t is not None:
            times.append(t)
        time.sleep(0.2)
    if not times:
        return None
    return {
        'min': min(times), 'max': max(times),
        'avg': sum(times) / len(times),
        'loss': (count - len(times)) / count * 100,
    }


def parse_wlan_show_all():
    raw = run_cmd("netsh wlan show interfaces")
    info = {}
    for line in raw.splitlines():
        line = line.strip()
        if ':' in line:
            k, v = line.split(':', 1)
            info[k.strip()] = v.strip()
    return info


def parse_wlan_channels():
    raw = run_cmd("netsh wlan show networks mode=bssid")
    networks = []
    current = {}
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith('SSID') and not line.startswith('SSID 名称'):
            if current:
                networks.append(current)
            ssid = line.split(':', 1)[1].strip()
            current = {'SSID': ssid}
        elif line.startswith('BSSID'):
            current['BSSID'] = line.split(':', 1)[1].strip()
        elif line.startswith('信道'):
            current['信道'] = line.split(':', 1)[1].strip()
        elif line.startswith('信号'):
            sig = line.split(':', 1)[1].strip()
            try:
                current['信号%'] = int(sig.replace('%', '').strip())
            except:
                current['信号%'] = sig
        elif line.startswith('无线电类型'):
            current['无线电'] = line.split(':', 1)[1].strip()
    if current:
        networks.append(current)
    return networks


SPEED_SERVERS = [
    {'name': 'Speedtest-UK', 'url': 'http://speedtest.tele2.net/10MB.zip', 'size': 10 * 1024 * 1024},
    {'name': 'Hetzner-DE', 'url': 'https://speed.hetzner.de/10MB.bin', 'size': 10 * 1024 * 1024},
    {'name': 'Speedtest-1MB', 'url': 'http://speedtest.tele2.net/1MB.zip', 'size': 1 * 1024 * 1024},
]


def speed_test_download(server):
    try:
        from urllib.request import urlopen, Request
        req = Request(server['url'], headers={'User-Agent': 'Mozilla/5.0'})
        start = time.time()
        downloaded = 0
        with urlopen(req, timeout=20) as resp:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                downloaded += len(chunk)
        elapsed = time.time() - start
        speed_mbps = (downloaded * 8) / elapsed / 1_000_000 if elapsed > 0 else 0
        return {'server': server['name'], 'speed_mbps': round(speed_mbps, 2),
                'size_mb': round(downloaded / 1024 / 1024, 2), 'time_s': round(elapsed, 2)}
    except Exception as e:
        return {'server': server['name'], 'speed_mbps': 0, 'error': str(e)}


def speed_test_upload():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect(('speedtest.tele2.net', 80))
        data = b'X' * (1024 * 1024)
        sent = 0
        start = time.time()
        for _ in range(10):
            sock.sendall(data)
            sent += len(data)
        elapsed = time.time() - start
        speed_mbps = (sent * 8) / elapsed / 1_000_000 if elapsed > 0 else 0
        sock.close()
        return round(speed_mbps, 2)
    except Exception:
        return 0


def build_dns_query(domain):
    txid = struct.pack('!H', 0x1234)
    flags = struct.pack('!H', 0x0100)
    header = txid + flags + struct.pack('!HHHH', 1, 0, 0, 0)
    qname = b''
    for label in domain.split('.'):
        qname += struct.pack('!B', len(label)) + label.encode()
    qname += b'\x00'
    return header + qname + struct.pack('!HH', 1, 1)


DNS_SERVERS = [
    ('默认 DNS', None),
    ('阿里 DNS', '223.5.5.5'),
    ('114 DNS', '114.114.114.114'),
    ('腾讯 DNS', '119.29.29.29'),
    ('Google DNS', '8.8.8.8'),
    ('Cloudflare', '1.1.1.1'),
]


def dns_query_speed(name, dns_ip, domain='www.baidu.com'):
    times = []
    for _ in range(3):
        try:
            start = time.time()
            if dns_ip:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(3)
                sock.sendto(build_dns_query(domain), (dns_ip, 53))
                sock.recvfrom(1024)
                sock.close()
            else:
                socket.getaddrinfo(domain, 80)
            times.append((time.time() - start) * 1000)
        except Exception:
            times.append(None)
    valid = [t for t in times if t is not None]
    avg = sum(valid) / len(valid) if valid else float('inf')
    return {'name': name, 'avg_ms': round(avg, 1) if valid else None,
            'loss': (3 - len(valid)) / 3 * 100}


def detect_gateway():
    raw = run_cmd("ipconfig")
    for block in raw.split('\n\n'):
        if '无线局域网' in block or 'WLAN' in block:
            for line in block.splitlines():
                if '默认网关' in line and ':' in line:
                    ip = line.split(':', 1)[1].strip()
                    if ip and ip != '0.0.0.0':
                        return ip
    for line in raw.splitlines():
        if '默认网关' in line and ':' in line:
            ip = line.split(':', 1)[1].strip()
            if ip and ip != '0.0.0.0':
                return ip
    return None


def simple_traceroute(target, max_hops=15):
    results = []
    for ttl in range(1, max_hops + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            sock.settimeout(2)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
            icmp_id = os.getpid() & 0xFFFF
            packet = struct.pack('!BBHHH', 8, 0, 0, icmp_id, ttl) + b'A' * 56
            start = time.time()
            sock.sendto(packet, (target, 1))
            data, (addr, _) = sock.recvfrom(1024)
            rtt = (time.time() - start) * 1000
            results.append({'hop': ttl, 'ip': addr, 'rtt_ms': round(rtt, 1)})
            sock.close()
            if addr == target:
                break
        except socket.timeout:
            results.append({'hop': ttl, 'ip': '*', 'rtt_ms': None})
        except Exception:
            results.append({'hop': ttl, 'ip': '?', 'rtt_ms': None})
    return results


def run_full_diagnostic(log):
    log("=" * 55)
    log("   随身 WiFi 网络诊断报告")
    log(f"   生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 55)

    # 1. WiFi
    log("\n【1/6】WiFi 信号与接口信息")
    log("-" * 40)
    wlan = parse_wlan_show_all()
    fields = [
        ('SSID', 'SSID'), ('信号强度', '信号'), ('无线电类型', '无线电类型'),
        ('协议', '协议'), ('接收速率', '接收速率'), ('发送速率', '发送速率'),
        ('IPv4', 'IPv4 地址'), ('网关', '默认网关'),
    ]
    for label, key in fields:
        val = wlan.get(key, '(未连接)')
        log(f"  {label:<14} : {val}")

    channels = parse_wlan_channels()
    cur_ssid = wlan.get('SSID', '')
    log(f"\n  周围可见网络 ({len(channels)} 个):")
    for n in channels:
        mark = ' ◀ 当前' if n.get('SSID') == cur_ssid else ''
        log(f"    [{n.get('信道','?'):>3}ch] {n.get('信号%','?'):>3}%  {n.get('SSID','')}{mark}")

    # 2. Ping
    log("\n【2/6】Ping 连通性")
    log("-" * 40)
    gateway = detect_gateway()
    targets = [
        ('本地网关', gateway), ('阿里 DNS', '223.5.5.5'),
        ('114 DNS', '114.114.114.114'), ('百度', 'www.baidu.com'),
        ('Google', '8.8.8.8'), ('Cloudflare', '1.1.1.1'),
    ]
    ping_res = {}
    for name, host in targets:
        if not host:
            log(f"  {name:<10} : 未连接")
            continue
        h = host
        try:
            if not re.match(r'^\d+\.\d+\.\d+\.\d+$', host):
                h = socket.gethostbyname(host)
        except:
            log(f"  {name:<10} : DNS 解析失败")
            continue
        r = ping_aggregate(h)
        ping_res[name] = r
        if r:
            log(f"  {name:<10} : {r['avg']:>6.1f}ms  丢包 {r['loss']:.0f}%")
        else:
            log(f"  {name:<10} : 全部丢包")

    # 3. DNS
    log("\n【3/6】DNS 解析速度对比")
    log("-" * 40)
    dns_res = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(dns_query_speed, n, ip): n for n, ip in DNS_SERVERS}
        for fut in as_completed(futures):
            dns_res.append(fut.result())
    dns_res.sort(key=lambda x: x['avg_ms'] if x['avg_ms'] is not None else 9999)
    for r in dns_res:
        if r['avg_ms'] is not None:
            log(f"  {r['name']:<12} : {r['avg_ms']:>6.1f}ms  丢包 {r['loss']:.0f}%")
        else:
            log(f"  {r['name']:<12} : 解析失败")

    # 4. 下载
    log("\n【4/6】下载测速（多服务器）")
    log("-" * 40)
    speed_res = []
    for srv in SPEED_SERVERS[:3]:
        log(f"  ↻ 测试 {srv['name']} ...")
        r = speed_test_download(srv)
        speed_res.append(r)
        if 'error' in r:
            log(f"    ✗ 失败: {r['error']}")
        else:
            bar_len = min(20, int(r['speed_mbps'] / 2))
            bar = '█' * bar_len + '░' * (20 - bar_len)
            log(f"    ✓ {r['speed_mbps']:>7.2f} Mbps  {bar}")

    valid = [s for s in speed_res if 'error' not in s and s['speed_mbps'] > 0]
    if valid:
        avg = sum(s['speed_mbps'] for s in valid) / len(valid)
        log(f"\n  平均下载: {avg:.2f} Mbps")

    # 5. 上传
    log("\n【5/6】上传测速")
    log("-" * 40)
    up = speed_test_upload()
    if up > 0:
        bar_len = min(20, int(up / 2))
        bar = '█' * bar_len + '░' * (20 - bar_len)
        log(f"  ✓ {up:.2f} Mbps  {bar}")
    else:
        log("  ✗ 上传测速失败（防火墙可能拦截，不影响判断）")

    # 6. Traceroute
    log("\n【6/6】路由追踪 (www.baidu.com)")
    log("-" * 40)
    try:
        ip = socket.gethostbyname('www.baidu.com')
        hops = simple_traceroute(ip)
        for h in hops:
            if h['rtt_ms'] is not None:
                log(f"  {h['hop']:>2}. {h['ip']:<18} {h['rtt_ms']:>7.1f} ms")
            else:
                log(f"  {h['hop']:>2}. * * *")
    except Exception as e:
        log(f"  追踪失败: {e}")

    # 综合建议
    log("\n" + "=" * 55)
    log("  综合诊断结论与优化建议")
    log("=" * 55)
    _advise(log, wlan, ping_res, speed_res, up, dns_res, channels, cur_ssid)
    log("\n诊断完成 ✓")


def _advise(log, wlan, ping_res, speed_res, up, dns_res, channels, cur_ssid):
    n = 1
    try:
        sig = int(wlan.get('信号', '0%').replace('%', '').strip())
    except:
        sig = 0
    if sig < 60:
        log(f"\n{n}. ⚠️ WiFi 信号偏弱 ({sig}%)")
        log("   → 靠近设备 / 避开金属 / 换 5G 频段")
        n += 1

    my_ch = None
    for c in channels:
        if c.get('SSID') == cur_ssid:
            try:
                my_ch = int(c.get('信道', '0'))
            except:
                pass
            break
    if my_ch:
        overlap = sum(1 for c in channels
                      if str(c.get('信道')) == str(my_ch) and c.get('SSID') != cur_ssid)
        if overlap >= 2:
            log(f"\n{n}. ⚠️ 信道 {my_ch} 有 {overlap} 个重叠网络")
            log("   → 2.4G 建议换 1/6/11，5G 建议换 149/157")
            n += 1

    gw = ping_res.get('本地网关')
    if gw and gw['avg'] > 5:
        log(f"\n{n}. ⚠️ 网关延迟偏高 ({gw['avg']:.1f}ms) → 重启路由器")
        n += 1

    for name, r in ping_res.items():
        if r and r['loss'] > 30:
            log(f"\n{n}. ❌ 到 {name} 丢包 {r['loss']:.0f}%")
            log("   → 运营商信号差 / 联系客服")
            n += 1
            break

    gd = [d for d in dns_res if d['avg_ms'] is not None]
    if gd:
        best = min(gd, key=lambda x: x['avg_ms'])
        default = next((d for d in gd if d['name'] == '默认 DNS'), None)
        if default and default['avg_ms'] - best['avg_ms'] > 20:
            log(f"\n{n}. 💡 DNS 可优化")
            log(f"   默认 {default['avg_ms']:.1f}ms → 建议 {best['name']} ({best['avg_ms']:.1f}ms)")
            log("   改 DNS: 网卡属性 → IPv4 → 手动 → 223.5.5.5")
            n += 1

    valid = [s for s in speed_res if 'error' not in s and s['speed_mbps'] > 0]
    if valid:
        mx = max(valid, key=lambda x: x['speed_mbps'])['speed_mbps']
        if mx < 5:
            log(f"\n{n}. ⚠️ 下载 {mx:.2f} Mbps，极可能已被限速！")
            log("   → 检查套餐流量 / 尝试切换 APN / 联系客服")
            n += 1
        elif mx < 15:
            log(f"\n{n}. ℹ️ 下载 {mx:.2f} Mbps，速度一般")
            n += 1

    log(f"\n共 {n - 1} 条建议")


class WiFiDiagApp:
    def __init__(self, root):
        self.root = root
        root.title("随身 WiFi 网络诊断工具 v1.0")
        root.geometry("820x640")
        root.minsize(720, 540)
        self._build_ui()

    def _build_ui(self):
        try:
            ttk.Style().theme_use('clam')
        except:
            pass

        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(top, text="📡 随身 WiFi 网络诊断工具",
                  font=("Microsoft YaHei", 16, "bold")).pack(side=tk.LEFT)

        bf = ttk.Frame(top)
        bf.pack(side=tk.RIGHT)
        self.btn_run = ttk.Button(bf, text="▶ 全面诊断", command=self._full)
        self.btn_run.pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="📶 WiFi", command=self._wifi).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="⏱ Ping", command=self._ping).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="⚡ 测速", command=self._speed).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="🔗 DNS", command=self._dns).pack(side=tk.LEFT, padx=3)

        mid = ttk.Frame(self.root, padding=(10, 0))
        mid.pack(fill=tk.BOTH, expand=True)
        self.text = scrolledtext.ScrolledText(
            mid, wrap=tk.WORD, font=("Consolas", 10),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white"
        )
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.tag_configure("title", foreground="#569cd6", font=("Consolas", 11, "bold"))
        self.text.tag_configure("ok", foreground="#4ec9b0")
        self.text.tag_configure("warn", foreground="#dcdcaa")
        self.text.tag_configure("err", foreground="#f44747")
        self.text.tag_configure("info", foreground="#9cdcfe")

        bot = ttk.Frame(self.root, padding=10)
        bot.pack(fill=tk.X)
        self.status = ttk.Label(bot, text="就绪")
        self.status.pack(side=tk.LEFT)
        ttk.Button(bot, text="清空", command=lambda: self.text.delete('1.0', tk.END)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bot, text="保存报告", command=self._save).pack(side=tk.RIGHT, padx=4)

        self._log("欢迎使用随身 WiFi 网络诊断工具\n", "title")
        self._log("点击「全面诊断」一键跑完所有项目，或用右侧按钮做单项检测。\n\n", "info")

    def _log(self, msg, tag=None):
        def _do():
            self.text.insert(tk.END, msg + "\n" if not msg.endswith("\n") else msg, tag)
            self.text.see(tk.END)
        self.root.after(0, _do)

    def _status(self, t):
        self.root.after(0, lambda: self.status.config(text=t))

    def _run(self, fn):
        for b in [self.btn_run]:
            b.state(['disabled'])
        def _wrap():
            try:
                fn()
            except Exception as e:
                self._log(f"异常: {e}", "err")
            finally:
                self._status("就绪")
                self.root.after(0, lambda: self.btn_run.state(['!disabled']))
        threading.Thread(target=_wrap, daemon=True).start()

    def _full(self):
        self.text.delete('1.0', tk.END)
        self._status("诊断中...")
        self._run(lambda: run_full_diagnostic(self._log))

    def _wifi(self):
        self._status("获取WiFi信息...")
        def _do():
            self._log("【WiFi 接口信息】", "title")
            w = parse_wlan_show_all()
            for k, v in w.items():
                self._log(f"  {k:<14} : {v}")
            self._log("\n【周围WiFi】", "title")
            for n in parse_wlan_channels():
                self._log(f"  [{n.get('信道','?'):>3}ch] {n.get('信号%','?'):>3}%  {n.get('无线电',''):<8} {n.get('SSID','')}")
        self._run(_do)

    def _ping(self):
        self._status("Ping测试中...")
        def _do():
            self._log("【Ping 连通性】", "title")
            gw = detect_gateway()
            targets = [('本地网关', gw), ('阿里 DNS', '223.5.5.5'),
                       ('百度', 'www.baidu.com'), ('Google', '8.8.8.8')]
            for name, host in targets:
                if not host:
                    self._log(f"  {name:<10} : 未连接", "warn")
                    continue
                h = host
                try:
                    if not re.match(r'^\d+\.\d+\.\d+\.\d+$', host):
                        h = socket.gethostbyname(host)
                except:
                    continue
                r = ping_aggregate(h)
                if r:
                    tag = "ok" if r['avg'] < 50 else ("warn" if r['avg'] < 150 else "err")
                    self._log(f"  {name:<10} : {r['avg']:>6.1f}ms  丢包{r['loss']:.0f}%", tag)
                else:
                    self._log(f"  {name:<10} : 全部丢包", "err")
        self._run(_do)

    def _speed(self):
        self._status("测速中...")
        def _do():
            self._log("【下载测速】", "title")
            for s in SPEED_SERVERS[:3]:
                self._log(f"  ↻ 测试 {s['name']} ...", "info")
                r = speed_test_download(s)
                if 'error' in r:
                    self._log(f"    ✗ {r['error']}", "err")
                else:
                    self._log(f"    ✓ {r['speed_mbps']:.2f} Mbps ({r['size_mb']}MB/{r['time_s']}s)", "ok")
            self._log("\n【上传测速】", "title")
            up = speed_test_upload()
            if up > 0:
                self._log(f"  ✓ {up:.2f} Mbps", "ok")
            else:
                self._log("  ✗ 失败", "warn")
        self._run(_do)

    def _dns(self):
        self._status("DNS测试中...")
        def _do():
            self._log("【DNS 解析速度】", "title")
            res = []
            with ThreadPoolExecutor(max_workers=6) as ex:
                futures = {ex.submit(dns_query_speed, n, ip): n for n, ip in DNS_SERVERS}
                for f in as_completed(futures):
                    res.append(f.result())
            res.sort(key=lambda x: x['avg_ms'] if x['avg_ms'] is not None else 9999)
            for r in res:
                if r['avg_ms'] is not None:
                    tag = "ok" if r['avg_ms'] < 50 else ("warn" if r['avg_ms'] < 150 else "err")
                    self._log(f"  {r['name']:<12} : {r['avg_ms']:>6.1f}ms", tag)
                else:
                    self._log(f"  {r['name']:<12} : 失败", "err")
        self._run(_do)

    def _save(self):
        c = self.text.get('1.0', tk.END)
        if not c.strip():
            messagebox.showinfo("提示", "报告为空")
            return
        fn = f"WiFi诊断_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        try:
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), fn)
            with open(p, 'w', encoding='utf-8') as f:
                f.write(c)
            messagebox.showinfo("保存成功", f"已保存:\n{p}")
        except Exception as e:
            messagebox.showerror("失败", str(e))


if __name__ == '__main__':
    root = tk.Tk()
    WiFiDiagApp(root)
    root.mainloop()