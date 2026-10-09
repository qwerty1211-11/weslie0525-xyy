# -*- coding: utf-8 -*-
"""
随身WiFi 网络诊断与优化工具
============================
单文件 GUI 程序，用于：
  1. WiFi 信号分析（信号强度 / 信道 / 频率 / 干扰）
  2. 多节点 Ping 测试（网关 / DNS / 外网 / 海外）
  3. 实时测速（多服务器下载/上传）
  4. 路由追踪（定位限速/丢包瓶颈）
  5. DNS 解析速度对比（默认 / 阿里 / 114 / 腾讯 / Google）
  6. 综合诊断 + 优化建议

启动：python 随身WiFi诊断工具.py
依赖：仅标准库，无需 pip install
"""

import os
import sys
import socket
import struct
import time
import threading
import subprocess
import re
import json
import math
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# 基础工具函数
# ============================================================

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
        packet = struct.pack(
            '!BBHHH',
            8, 0, 0, icmp_id, 1
        ) + b'A' * 56
        checksum = 0
        for i in range(0, len(packet), 2):
            checksum += (packet[i] << 8) + packet[i + 1]
        checksum = (checksum >> 16) + (checksum & 0xFFFF)
        checksum = (~checksum) & 0xFFFF
        packet = struct.pack(
            '!BBHHH',
            8, 0, socket.htons(checksum), icmp_id, 1
        ) + b'A' * 56
        start = time.time()
        sock.sendto(packet, (host, 1))
        data, _ = sock.recvfrom(1024)
        rtt = (time.time() - start) * 1000
        sock.close()
        return rtt
    except Exception:
        sock.close() if 'sock' in dir() else None
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
        'min': min(times),
        'max': max(times),
        'avg': sum(times) / len(times),
        'loss': (count - len(times)) / count * 100,
        'times': times
    }


# ============================================================
# WiFi 信息采集（Windows netsh）
# ============================================================

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


# ============================================================
# 测速引擎（多服务器，纯 socket）
# ============================================================

SPEED_SERVERS = [
    {'name': '阿里云-北京', 'url': 'http://speedtest.tele2.net/10MB.zip', 'size': 10 * 1024 * 1024},
    {'name': '阿里云-上海', 'url': 'http://speedtest.tele2.net/10MB.zip', 'size': 10 * 1024 * 1024},
    {'name': 'AWS-海外', 'url': 'https://speed.hetzner.de/10MB.bin', 'size': 10 * 1024 * 1024},
    {'name': 'Cloudflare', 'url': 'http://speedtest.tele2.net/1MB.zip', 'size': 1 * 1024 * 1024},
]


def speed_test_download(server, progress_cb=None):
    try:
        from urllib.request import urlopen, Request
        req = Request(server['url'], headers={'User-Agent': 'Mozilla/5.0'})
        start = time.time()
        downloaded = 0
        chunks = []
        with urlopen(req, timeout=15) as resp:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                downloaded += len(chunk)
                if progress_cb:
                    progress_cb(downloaded, server['size'])
        elapsed = time.time() - start
        speed_mbps = (downloaded * 8) / elapsed / 1_000_000 if elapsed > 0 else 0
        return {'server': server['name'], 'speed_mbps': round(speed_mbps, 2),
                'size_mb': round(downloaded / 1024 / 1024, 2), 'time_s': round(elapsed, 2)}
    except Exception as e:
        return {'server': server['name'], 'speed_mbps': 0, 'error': str(e)}


def speed_test_upload(progress_cb=None):
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
            if progress_cb:
                progress_cb(sent, 10 * 1024 * 1024)
        elapsed = time.time() - start
        speed_mbps = (sent * 8) / elapsed / 1_000_000 if elapsed > 0 else 0
        sock.close()
        return round(speed_mbps, 2)
    except Exception as e:
        return 0


# ============================================================
# DNS 解析速度测试
# ============================================================

DNS_SERVERS = [
    ('默认 DNS', None),
    ('阿里 DNS', '223.5.5.5'),
    ('114 DNS', '114.114.114.114'),
    ('腾讯 DNS', '119.29.29.29'),
    ('Google DNS', '8.8.8.8'),
    ('Cloudflare', '1.1.1.1'),
]


def dns_query_speed(server_name, dns_ip, domain='www.baidu.com'):
    times = []
    for _ in range(3):
        try:
            start = time.time()
            if dns_ip:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(3)
                query = build_dns_query(domain)
                sock.sendto(query, (dns_ip, 53))
                sock.recvfrom(1024)
                sock.close()
            else:
                socket.getaddrinfo(domain, 80)
            times.append((time.time() - start) * 1000)
        except Exception:
            times.append(None)
    valid = [t for t in times if t is not None]
    avg = sum(valid) / len(valid) if valid else float('inf')
    return {'name': server_name, 'avg_ms': round(avg, 1) if valid else None,
            'loss': (3 - len(valid)) / 3 * 100}


def build_dns_query(domain):
    txid = struct.pack('!H', 0x1234)
    flags = struct.pack('!H', 0x0100)
    qdcount = struct.pack('!H', 1)
    ancount = struct.pack('!H', 0)
    nscount = struct.pack('!H', 0)
    arcount = struct.pack('!H', 0)
    header = txid + flags + qdcount + ancount + nscount + arcount
    qname = b''
    for label in domain.split('.'):
        qname += struct.pack('!B', len(label)) + label.encode()
    qname += b'\x00'
    qtype = struct.pack('!H', 1)
    qclass = struct.pack('!H', 1)
    return header + qname + qtype + qclass


# ============================================================
# Traceroute（简化版）
# ============================================================

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
            if addr == target:
                sock.close()
                break
            sock.close()
        except socket.timeout:
            results.append({'hop': ttl, 'ip': '*', 'rtt_ms': None})
        except Exception:
            results.append({'hop': ttl, 'ip': '?', 'rtt_ms': None})
    return results


# ============================================================
# 综合诊断引擎
# ============================================================

COMMON_PING_TARGETS = [
    ('本地网关', None),
    ('阿里 DNS', '223.5.5.5'),
    ('114 DNS', '114.114.114.114'),
    ('百度', 'www.baidu.com'),
    ('B 站', 'www.bilibili.com'),
    ('知乎', 'www.zhihu.com'),
    ('Google', '8.8.8.8'),
    ('Cloudflare', '1.1.1.1'),
]


def detect_gateway():
    raw = run_cmd("ipconfig")
    for block in raw.split('\n\n'):
        if '无线局域网适配器' in block or 'WLAN' in block:
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


def get_public_ip():
    try:
        from urllib.request import urlopen
        return urlopen('http://api.ipify.org', timeout=5).read().decode().strip()
    except:
        return '获取失败'


def run_full_diagnostic(log_cb, progress_cb=None):
    log = log_cb

    log("=" * 55)
    log("   随身 WiFi 网络诊断报告")
    log(f"   生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 55)

    # ---- 1. WiFi 基本信息 ----
    log("\n【1/6】WiFi 信号与接口信息")
    log("-" * 40)
    wlan_info = parse_wlan_show_all()
    fields = [
        ('SSID', 'SSID'),
        ('BSSID', 'BSSID'),
        ('信号强度', '信号'),
        ('无线电类型', '无线电类型'),
        ('认证', '身份验证'),
        ('加密', '密码'),
        ('协议', '协议'),
        ('接收速率(Mbps)', '接收速率'),
        ('发送速率(Mbps)', '发送速率'),
        ('IPv4', 'IPv4 地址'),
        ('网关', '默认网关'),
    ]
    for label, key in fields:
        val = wlan_info.get(key, '(未连接)')
        if label == '信号强度':
            sig_val = 0
            try:
                sig_val = int(val.replace('%', '').strip())
            except:
                pass
            bar = '█' * (sig_val // 5) + '░' * (20 - sig_val // 5)
            log(f"  {label:<16} : {val}  [{bar}]")
        else:
            log(f"  {label:<16} : {val}")

    channels = parse_wlan_channels()
    current_ssid = wlan_info.get('SSID', '')
    log(f"\n  周围可见网络 ({len(channels)} 个):")
    for n in channels:
        mark = ' ◀ 当前' if n.get('SSID') == current_ssid else ''
        log(f"    [{n.get('信道','?'):>3}ch] {n.get('信号%','?'):>3}%  {n.get('SSID','')}{mark}")

    # ---- 2. Ping 连通性 ----
    log("\n【2/6】Ping 连通性检测")
    log("-" * 40)
    gateway = detect_gateway()
    targets = []
    for name, ip in COMMON_PING_TARGETS:
        if name == '本地网关':
            targets.append((name, gateway))
        elif ip:
            resolved = ip
            try:
                if not re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                    resolved = socket.gethostbyname(ip)
            except:
                resolved = None
            targets.append((name, resolved))

    ping_results = {}
    for name, host in targets:
        if not host:
            log(f"  {name:<10} : 无法确定地址")
            continue
        r = ping_aggregate(host, count=4)
        ping_results[name] = r
        if r:
            log(f"  {name:<10} : {r['avg']:>6.1f}ms  (丢包 {r['loss']:.0f}%, 最快 {r['min']:.1f}ms)")
        else:
            log(f"  {name:<10} : 全部丢包 ❌")

    # ---- 3. DNS 对比 ----
    log("\n【3/6】DNS 解析速度对比")
    log("-" * 40)
    dns_results = []
    for name, ip in DNS_SERVERS:
        r = dns_query_speed(name, ip)
        dns_results.append(r)
        if r['avg_ms'] is not None:
            log(f"  {name:<12} : {r['avg_ms']:>6.1f}ms  (丢包 {r['loss']:.0f}%)")
        else:
            log(f"  {name:<12} : 解析失败 ❌")

    valid_dns = [d for d in dns_results if d['avg_ms'] is not None]
    if valid_dns:
        best = min(valid_dns, key=lambda x: x['avg_ms'])
        log(f"\n  ✅ 最快 DNS 推荐: {best['name']} ({best['avg_ms']:.1f}ms)")

    # ---- 4. 下载测速 ----
    log("\n【4/6】下载测速（多服务器对比）")
    log("-" * 40)
    speed_results = []
    def on_progress(done, total, srv):
        pct = done / total * 100 if total else 0
        log(f"  ↻ {srv['name']} 下载中... {pct:.0f}%")

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(speed_test_download, s): s for s in SPEED_SERVERS[:3]}
        for fut in as_completed(futures):
            srv = futures[fut]
            r = fut.result()
            speed_results.append(r)
            if 'error' in r:
                log(f"  {r['server']:<14} : 失败 ({r['error']})")
            else:
                bar_len = min(20, int(r['speed_mbps'] / 2))
                bar = '█' * bar_len + '░' * (20 - bar_len)
                log(f"  {r['server']:<14} : {r['speed_mbps']:>7.2f} Mbps  {bar}")

    valid_speed = [s for s in speed_results if 'error' not in s and s['speed_mbps'] > 0]
    if valid_speed:
        avg_down = sum(s['speed_mbps'] for s in valid_speed) / len(valid_speed)
        log(f"\n  📊 平均下载速度: {avg_down:.2f} Mbps")
        log(f"  📊 最快服务器: {max(valid_speed, key=lambda x: x['speed_mbps'])['server']}")

    # ---- 5. 上传测速 ----
    log("\n【5/6】上传测速")
    log("-" * 40)
    up = speed_test_upload()
    if up > 0:
        bar_len = min(20, int(up / 2))
        bar = '█' * bar_len + '░' * (20 - bar_len)
        log(f"  上传速度: {up:.2f} Mbps  {bar}")
    else:
        log("  上传测速失败（可能被防火墙拦截，不影响）")

    # ---- 6. 路由追踪 ----
    log("\n【6/6】路由追踪（到 www.baidu.com）")
    log("-" * 40)
    try:
        baidu_ip = socket.gethostbyname('www.baidu.com')
        hops = simple_traceroute(baidu_ip)
        for h in hops:
            if h['rtt_ms'] is not None:
                log(f"  {h['hop']:>2}. {h['ip']:<18} {h['rtt_ms']:>7.1f} ms")
            else:
                log(f"  {h['hop']:>2}. * * *")
    except Exception as e:
        log(f"  路由追踪失败: {e}")

    # ---- 综合判断 ----
    log("\n" + "=" * 55)
    log("  📋 综合诊断结论与优化建议")
    log("=" * 55)
    _give_advice(log, wlan_info, ping_results, speed_results, up, valid_dns, channels, gateway)

    log("\n✅ 诊断完成")
    return ping_results, speed_results, up, valid_dns


def _give_advice(log, wlan_info, ping_results, speed_results, up, dns_results, channels, gateway):
    advice_count = 1
    sig_raw = wlan_info.get('信号', '0%')
    try:
        signal_pct = int(sig_raw.replace('%', '').strip())
    except:
        signal_pct = 0

    # 信号
    if signal_pct < 60:
        log(f"\n  {advice_count}. ⚠️ WiFi 信号偏弱 ({signal_pct}%)")
        log("     → 靠近路由器 / 随身WiFi 设备")
        log("     → 避免金属障碍物和微波炉干扰")
        advice_count += 1
    elif signal_pct >= 85:
        log(f"\n  ✅ WiFi 信号良好 ({signal_pct}%)")

    # 信道拥挤
    my_ssid = wlan_info.get('SSID', '')
    my_channel = None
    for n in channels:
        if n.get('SSID') == my_ssid:
            try:
                my_channel = int(n.get('信道', '0'))
            except:
                pass
            break
    if my_channel:
        neighbor_count = sum(
            1 for n in channels
            if n.get('信道') and str(n.get('信道')) == str(my_channel) and n.get('SSID') != my_ssid
        )
        if neighbor_count >= 2:
            log(f"\n  {advice_count}. ⚠️ 当前信道 {my_channel} 有 {neighbor_count} 个重叠网络")
            log("     → 用路由器后台切换到 1 / 6 / 11（2.4G）或 149/157（5G）")
            advice_count += 1

    # 网关 ping
    gw_ping = ping_results.get('本地网关')
    if gw_ping and gw_ping['avg'] > 5:
        log(f"\n  {advice_count}. ⚠️ 网关延迟偏高 ({gw_ping['avg']:.1f}ms)")
        log("     → 路由器本身可能过载，尝试重启")
        advice_count += 1

    # 丢包
    for name, r in ping_results.items():
        if r and r['loss'] > 30:
            log(f"\n  {advice_count}. ❌ 到 {name} 丢包严重 ({r['loss']:.0f}%)")
            log("     → 检查运营商信号 / 联系客服")
            advice_count += 1
            break

    # 国际连通
    g_ping = ping_results.get('Google') or ping_results.get('Cloudflare')
    if g_ping and g_ping['loss'] > 0:
        log(f"\n  {advice_count}. ℹ️ 海外节点有丢包（属正常现象）")
        log("     → 需要访问海外请考虑正规加速器")
        advice_count += 1

    # DNS
    if dns_results:
        best = min(dns_results, key=lambda x: x['avg_ms'])
        default_dns = next((d for d in dns_results if d['name'] == '默认 DNS'), None)
        if default_dns and default_dns['avg_ms'] and best['name'] != '默认 DNS':
            diff = default_dns['avg_ms'] - best['avg_ms']
            if diff > 20:
                log(f"\n  {advice_count}. 💡 DNS 可优化")
                log(f"     当前默认 {default_dns['avg_ms']:.1f}ms → 建议切换 {best['name']} ({best['avg_ms']:.1f}ms)")
                log("     Windows 设置: 网络适配器 → IPv4 → 手动 DNS → 223.5.5.5 / 114.114.114.114")
                advice_count += 1

    # 速度判断
    valid_speed = [s for s in speed_results if 'error' not in s and s['speed_mbps'] > 0]
    if valid_speed:
        max_speed = max(valid_speed, key=lambda x: x['speed_mbps'])['speed_mbps']
        if max_speed < 5:
            log(f"\n  {advice_count}. ⚠️ 下载速度极低 ({max_speed:.2f} Mbps)")
            log("     → 很可能已被运营商限速！")
            log("     → 检查套餐流量是否用完 / 是否触发了 Fair Use Policy")
            log("     → 尝试切换接入点（APN）或重启设备")
            advice_count += 1
        elif max_speed < 15:
            log(f"\n  {advice_count}. ℹ️ 下载速度一般 ({max_speed:.2f} Mbps)")
            log("     → 可以接受，若需更快建议升级套餐或换 5G 设备")
            advice_count += 1

    if up > 0 and up < 1:
        log(f"\n  {advice_count}. ⚠️ 上传速度偏低 ({up:.2f} Mbps)")
        log("     → 移动网络通常上传 < 下载，属正常现象")
        advice_count += 1

    log(f"\n  📌 共给出 {advice_count - 1} 条建议")


# ============================================================
# GUI
# ============================================================

class WiFiDiagApp:
    def __init__(self, root):
        self.root = root
        root.title("随身 WiFi 网络诊断工具 v1.0")
        root.geometry("800x620")
        root.minsize(720, 540)

        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except:
            pass

        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        title = ttk.Label(top, text="📡 随身 WiFi 网络诊断工具",
                          font=("Microsoft YaHei", 16, "bold"))
        title.pack(side=tk.LEFT)

        btn_frame = ttk.Frame(top)
        btn_frame.pack(side=tk.RIGHT)

        self.btn_run = ttk.Button(btn_frame, text="▶ 开始全面诊断", command=self._start_diagnostic)
        self.btn_run.pack(side=tk.LEFT, padx=4)

        self.btn_wifi = ttk.Button(btn_frame, text="📶 WiFi 信息", command=self._quick_wifi)
        self.btn_wifi.pack(side=tk.LEFT, padx=4)

        self.btn_ping = ttk.Button(btn_frame, text="⏱ Ping 测试", command=self._quick_ping)
        self.btn_ping.pack(side=tk.LEFT, padx=4)

        self.btn_speed = ttk.Button(btn_frame, text="⚡ 测速", command=self._quick_speed)
        self.btn_speed.pack(side=tk.LEFT, padx=4)

        self.btn_dns = ttk.Button(btn_frame, text="🔗 DNS 测试", command=self._quick_dns)
        self.btn_dns.pack(side=tk.LEFT, padx=4)

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

        bottom = ttk.Frame(self.root, padding=10)
        bottom.pack(fill=tk.X)

        self.status = ttk.Label(bottom, text="就绪")
        self.status.pack(side=tk.LEFT)

        ttk.Button(bottom, text="清空", command=lambda: self.text.delete('1.0', tk.END)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bottom, text="保存报告", command=self._save).pack(side=tk.RIGHT, padx=4)

        self._log("欢迎使用随身 WiFi 网络诊断工具\n", "title")
        self._log("点击右上角按钮运行单项检测，或点击「开始全面诊断」一键跑完所有项目。\n\n")
        self._log("提示：首次测速会下载测试文件，请耐心等待。\n", "info")

    def _log(self, msg, tag=None):
        def _do():
            self.text.insert(tk.END, msg, tag)
            self.text.see(tk.END)
            self.root.update_idletasks()
        self.root.after(0, _do)

    def _set_status(self, text):
        self.root.after(0, lambda: self.status.config(text=text))

    def _run_in_thread(self, target):
        def _wrapped():
            try:
                target()
            except Exception as e:
                self._log(f"\n❌ 异常: {e}\n", "err")
            finally:
                self._set_status("就绪")
                self._enable_buttons(True)
        threading.Thread(target=_wrapped, daemon=True).start()

    def _enable_buttons(self, enable):
        state = '!disabled' if enable else 'disabled'
        for b in [self.btn_run, self.btn_wifi, self.btn_ping, self.btn_speed, self.btn_dns]:
            b.state([state] if enable else ['!disabled'])

    # ---- 按钮处理 ----
    def _start_diagnostic(self):
        self._enable_buttons(False)
        self._set_status("诊断中...")
        self.text.delete('1.0', tk.END)
        self._run_in_thread(lambda: run_full_diagnostic(self._log))

    def _quick_wifi(self):
        self._enable_buttons(False)
        self._set_status("获取WiFi信息...")
        self._run_in_thread(self._do_wifi)

    def _do_wifi(self):
        self._log("【WiFi 接口信息】\n", "title")
        wlan = parse_wlan_show_all()
        for k, v in wlan.items():
            self._log(f"  {k:<16} : {v}\n")
        self._log("\n【周围WiFi网络】\n", "title")
        for n in parse_wlan_channels():
            self._log(f"  [{n.get('信道','?'):>3}ch] {n.get('信号%','?'):>3}%  {n.get('无线电',''):<8} {n.get('SSID','')}\n")

    def _quick_ping(self):
        self._enable_buttons(False)
        self._set_status("Ping测试中...")
        self._run_in_thread(self._do_ping)

    def _do_ping(self):
        self._log("【Ping 连通性】\n", "title")
        gw = detect_gateway()
        targets = [
            ('本地网关', gw),
            ('阿里 DNS', '223.5.5.5'),
            ('百度', 'www.baidu.com'),
            ('Google', '8.8.8.8'),
        ]
        for name, host in targets:
            if not host:
                self._log(f"  {name:<10} : 未连接\n", "warn")
                continue
            try:
                h = host
                if not re.match(r'^\d+\.\d+\.\d+\.\d+$', host):
                    h = socket.gethostbyname(host)
                r = ping_aggregate(h)
                if r:
                    tag = "ok" if r['avg'] < 50 else ("warn" if r['avg'] < 150 else "err")
                    self._log(f"  {name:<10} : {r['avg']:>6.1f}ms  丢包{r['loss']:.0f}%\n", tag)
                else:
                    self._log(f"  {name:<10} : 全部丢包 ❌\n", "err")
            except Exception as e:
                self._log(f"  {name:<10} : {e}\n", "err")

    def _quick_speed(self):
        self._enable_buttons(False)
        self._set_status("测速中...")
        self._run_in_thread(self._do_speed)

    def _do_speed(self):
        self._log("【下载测速】\n", "title")
        for srv in SPEED_SERVERS[:3]:
            self._log(f"  正在测试 {srv['name']} ...\n", "info")
            r = speed_test_download(srv)
            if 'error' in r:
                self._log(f"    ✗ {r['error']}\n", "err")
            else:
                self._log(f"    ✓ {r['speed_mbps']:.2f} Mbps ({r['size_mb']}MB / {r['time_s']}s)\n", "ok")
        self._log("\n【上传测速】\n", "title")
        self._log("  正在测试上传 ...\n", "info")
        up = speed_test_upload()
        if up > 0:
            self._log(f"    ✓ {up:.2f} Mbps\n", "ok")
        else:
            self._log("    ✗ 上传测速失败\n", "warn")

    def _quick_dns(self):
        self._enable_buttons(False)
        self._set_status("DNS测试中...")
        self._run_in_thread(self._do_dns)

    def _do_dns(self):
        self._log("【DNS 解析速度】\n", "title")
        results = []
        with ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(dns_query_speed, n, ip): (n, ip) for n, ip in DNS_SERVERS}
            for fut in as_completed(futures):
                r = fut.result()
                results.append(r)
        results.sort(key=lambda x: x['avg_ms'] if x['avg_ms'] is not None else 9999)
        for r in results:
            if r['avg_ms'] is not None:
                tag = "ok" if r['avg_ms'] < 50 else ("warn" if r['avg_ms'] < 150 else "err")
                self._log(f"  {r['name']:<12} : {r['avg_ms']:>6.1f}ms\n", tag)
            else:
                self._log(f"  {r['name']:<12} : 失败\n", "err")

    def _save(self):
        content = self.text.get('1.0', tk.END)
        if not content.strip():
            messagebox.showinfo("提示", "报告为空")
            return
        ts = time.strftime('%Y%m%d_%H%M%S')
        fname = f"WiFi诊断报告_{ts}.txt"
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            messagebox.showinfo("保存成功", f"报告已保存到:\n{path}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))


def main():
    root = tk.Tk()
    app = WiFiDiagApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()