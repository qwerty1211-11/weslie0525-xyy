#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小猿口算 PK 自动抓包改包程序
=============================
原理：mitmproxy 做 HTTPS 中间人代理，拦截小猿口算的请求和响应，
      按用户自定义的规则修改 JSON 数据。

使用步骤：
  1. 电脑连 WiFi，手机连同一个 WiFi
  2. 手机 WiFi 设置代理 -> 电脑局域网 IP : 8080
  3. 手机浏览器访问 http://mitm.it 下载并安装证书
     (或: adb install cert.pem)
  4. 运行本程序： python 小袁口算自动抓包程序.py
  5. 打开小猿口算 PK 模式，程序会自动捕获所有接口

  如果小猿口算有 SSL Pinning 导致抓不到包：
    用 Magisk + frida 绕过，或使用 Android 7+ 的网络安全配置

依赖：pip install mitmproxy requests
"""

import json
import re
import os
import sys
import threading
import time
import socket
import subprocess
from datetime import datetime

RULES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modify_rules.json")
PACKETS_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "packets_log.jsonl")
MITMDUMP_SCRIPT = os.path.abspath(__file__)


def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def load_rules():
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"rules": []}
    return {"rules": []}


def save_rules(rules):
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def set_json_value(obj, path_str, new_value):
    keys = re.split(r'[.\[\]]+', path_str.strip())
    keys = [k for k in keys if k]
    current = obj
    for i, key in enumerate(keys[:-1]):
        if isinstance(current, list):
            idx = int(key)
            while len(current) <= idx:
                current.append({})
            current = current[idx]
        elif isinstance(current, dict):
            if key not in current:
                try:
                    int(keys[i + 1])
                    current[key] = []
                except (ValueError, IndexError):
                    current[key] = {}
            current = current[key]
    last_key = keys[-1]
    if isinstance(current, list):
        idx = int(last_key)
        while len(current) <= idx:
            current.append(None)
        current[idx] = new_value
    elif isinstance(current, dict):
        try:
            current[last_key] = json.loads(new_value)
        except Exception:
            current[last_key] = new_value
    return obj


def match_rule(url, method, rule):
    if rule.get("enabled", True) is False:
        return False
    pat = rule.get("url_pattern", "")
    if pat and not re.search(pat, url):
        return False
    rmethod = rule.get("method", "").upper()
    if rmethod and rmethod != method.upper():
        return False
    return True


class PacketRecorder:
    def __init__(self):
        self._lock = threading.Lock()

    def add(self, entry):
        try:
            with open(PACKETS_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def read_all(self):
        entries = []
        try:
            with open(PACKETS_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            pass
        except FileNotFoundError:
            pass
        return entries

    def read_tail(self, n=20):
        return self.read_all()[-n:]

    def clear(self):
        try:
            os.remove(PACKETS_LOG_FILE)
        except FileNotFoundError:
            pass


recorder = PacketRecorder()


class ModifyAddon:
    def __init__(self):
        self.rules = load_rules()
        self._last_reload = 0

    def _maybe_reload(self):
        now = time.time()
        if now - self._last_reload > 0.5:
            self.rules = load_rules()
            self._last_reload = now

    def request(self, flow):
        self._maybe_reload()
        try:
            url = flow.request.pretty_url
            method = flow.request.method

            entry = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "direction": "REQUEST",
                "method": method,
                "url": url,
            }

            body_text = None
            if flow.request.content:
                try:
                    body_text = flow.request.content.decode("utf-8")
                except Exception:
                    body_text = flow.request.content.hex()

            for rule in self.rules.get("rules", []):
                if rule.get("apply_to") == "request" and match_rule(url, method, rule):
                    if "set_field" in rule and body_text:
                        try:
                            body_json = json.loads(body_text)
                            set_json_value(body_json, rule["set_field"], rule["new_value"])
                            flow.request.content = json.dumps(body_json, ensure_ascii=False).encode("utf-8")
                            entry["modified"] = f"{rule['set_field']}={rule['new_value']}"
                        except Exception:
                            pass

            entry["body"] = body_text[:500] if body_text else None
            recorder.add(entry)
        except Exception:
            pass

    def response(self, flow):
        self._maybe_reload()
        try:
            url = flow.request.pretty_url
            method = flow.request.method
            status = flow.response.status_code

            entry = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "direction": "RESPONSE",
                "method": method,
                "url": url,
                "status": status,
            }

            body_text = None
            if flow.response.content:
                try:
                    body_text = flow.response.content.decode("utf-8")
                except Exception:
                    body_text = flow.response.content.hex()

            for rule in self.rules.get("rules", []):
                if rule.get("apply_to", "response") == "response" and match_rule(url, method, rule):
                    if body_text:
                        try:
                            body_json = json.loads(body_text)
                            modified_fields = []
                            for mf in rule.get("modify_fields", []):
                                set_json_value(body_json, mf["field"], mf["value"])
                                modified_fields.append(f"{mf['field']}={mf['value']}")
                            if modified_fields:
                                flow.response.content = json.dumps(body_json, ensure_ascii=False).encode("utf-8")
                                flow.response.headers["Content-Length"] = str(len(flow.response.content))
                                entry["modified"] = "; ".join(modified_fields)
                        except Exception:
                            pass
                    elif rule.get("raw_body"):
                        flow.response.content = rule["raw_body"].encode("utf-8")
                        flow.response.headers["Content-Length"] = str(len(flow.response.content.encode("utf-8")))
                        entry["modified"] = "raw_body"

            entry["body"] = body_text[:800] if body_text else None
            recorder.add(entry)
        except Exception:
            pass


addons = [ModifyAddon()]


def print_banner():
    print()
    print("=" * 60)
    print("  小猿口算 PK 抓包改包程序")
    print("=" * 60)
    print(f"  代理地址:  {get_lan_ip()}:8080")
    print(f"  规则文件:  {RULES_FILE}")
    print(f"  抓包日志:  {PACKETS_LOG_FILE}")
    print()
    print("  手机设置:")
    print("  1. 连同一 WiFi")
    print("  2. WiFi代理 -> 手动 -> 主机:" + get_lan_ip() + " 端口:8080")
    print("  3. 浏览器访问 http://mitm.it 安装证书")
    print("  4. 打开小猿口算 PK 开始游戏")
    print("=" * 60)
    print()


_console_running = True


def interactive_console():
    global _console_running
    while _console_running:
        try:
            cmd = input("[抓包运行中] 输入命令 (?查看帮助): ").strip()
        except (EOFError, KeyboardInterrupt):
            _console_running = False
            break

        if cmd in ("?", "help", "h"):
            print()
            print("  命令列表:")
            print("  ls          列出最近抓到的 20 个包")
            print("  ls N        列出最近 N 个包")
            print("  show N      查看第 N 个包的完整内容")
            print("  rules       查看当前所有修改规则")
            print("  add         交互式添加一条规则")
            print("  del N       删除第 N 条规则")
            print("  enable N    启用第 N 条规则")
            print("  disable N   禁用第 N 条规则")
            print("  clear       清空抓包列表")
            print("  edit        直接编辑 modify_rules.json")
            print("  q/quit      退出程序")
            print()
            continue

        if cmd in ("q", "quit", "exit"):
            _console_running = False
            os._exit(0)

        if cmd == "clear":
            recorder.clear()
            print("  ✓ 已清空抓包日志")
            continue

        if cmd.startswith("ls"):
            try:
                n = int(cmd.split()[1]) if len(cmd.split()) > 1 else 20
            except ValueError:
                n = 20
            all_packets = recorder.read_all()
            packets = recorder.read_tail(n)
            if not packets:
                print("  (还没抓到任何包)")
                continue
            print()
            offset = len(all_packets) - len(packets)
            for i, p in enumerate(packets):
                idx = offset + i
                mod = " [已修改]" if p.get("modified") else ""
                body_preview = ""
                if p.get("body"):
                    b = p["body"].replace("\n", " ")[:60]
                    body_preview = f"  body={b}"
                print(f"  [{idx}] {p['time']} {p['direction']} {p['method']} {p['url'][:80]}{mod}")
                if mod:
                    print(f"         {p['modified']}{body_preview}")
                elif body_preview:
                    print(f"         {body_preview}")
            print(f"  共 {len(all_packets)} 个包")
            print()
            continue

        if cmd.startswith("show"):
            try:
                n = int(cmd.split()[1])
            except (ValueError, IndexError):
                print("  用法: show <序号>  (序号见 ls)")
                continue
            all_packets = recorder.read_all()
            if 0 <= n < len(all_packets):
                p = all_packets[n]
                print()
                for k, v in p.items():
                    print(f"  {k}:")
                    if k == "body" and v:
                        try:
                            j = json.loads(v)
                            print(json.dumps(j, ensure_ascii=False, indent=2))
                        except Exception:
                            print(v[:2000])
                    else:
                        print(f"    {v}")
                print()
            else:
                print(f"  序号 {n} 超出范围 (0-{len(all_packets)-1})")
            continue

        if cmd == "rules":
            rules = load_rules().get("rules", [])
            if not rules:
                print("  (还没有任何规则)  输入 'add' 添加")
                continue
            print()
            for i, r in enumerate(rules):
                status = "✓" if r.get("enabled", True) else "✗"
                print(f"  [{i}] {status} url~{r.get('url_pattern','*')}")
                print(f"      方向={r.get('apply_to','response')} method={r.get('method','*')}")
                if "modify_fields" in r:
                    for mf in r["modify_fields"]:
                        print(f"      修改: {mf['field']} = {mf['value']}")
                if "raw_body" in r:
                    print(f"      替换为: {r['raw_body'][:100]}")
                print()
            continue

        if cmd == "add":
            rule = _interactive_add_rule()
            if rule:
                current = load_rules()
                current.setdefault("rules", []).append(rule)
                save_rules(current)
                print("  ✓ 规则已添加并自动生效")
            continue

        if cmd.startswith("del"):
            try:
                n = int(cmd.split()[1])
            except (ValueError, IndexError):
                print("  用法: del <序号>")
                continue
            current = load_rules()
            if 0 <= n < len(current.get("rules", [])):
                current["rules"].pop(n)
                save_rules(current)
                print(f"  ✓ 已删除规则 #{n}")
            else:
                print(f"  序号超出范围")
            continue

        if cmd.startswith("enable") or cmd.startswith("disable"):
            try:
                n = int(cmd.split()[1])
            except (ValueError, IndexError):
                print(f"  用法: {cmd.split()[0]} <序号>")
                continue
            val = cmd.startswith("enable")
            current = load_rules()
            if 0 <= n < len(current.get("rules", [])):
                current["rules"][n]["enabled"] = val
                save_rules(current)
                print(f"  ✓ 规则 #{n} 已{'启用' if val else '禁用'}")
            else:
                print(f"  序号超出范围")
            continue

        if cmd == "edit":
            try:
                os.startfile(RULES_FILE)
            except Exception as e:
                print(f"  打开失败: {e}")
            continue

        print(f"  未知命令: {cmd}  (输入 ? 查看帮助)")


def _interactive_add_rule():
    print()
    print("  --- 添加修改规则 ---")
    print()
    url_pat = input("  URL 匹配正则 (留空=所有): ").strip()
    method = input("  HTTP 方法 (GET/POST/留空=所有): ").strip()
    direction = input("  修改方向 [response/request] (默认 response): ").strip() or "response"

    rule = {
        "url_pattern": url_pat,
        "method": method,
        "apply_to": direction,
        "enabled": True,
    }

    if direction == "response":
        mode = input("  修改模式 [1=改字段值 / 2=替换整个响应体] (默认1): ").strip() or "1"
        if mode == "1":
            fields = []
            while True:
                field = input(f"  字段路径 (如 data.result, 空=结束): ").strip()
                if not field:
                    break
                value = input(f"    改成什么值: ").strip()
                fields.append({"field": field, "value": value})
            if not fields:
                print("  (没有输入任何字段，取消)")
                return None
            rule["modify_fields"] = fields
        else:
            raw = input("  整个响应体内容 (留空=取消): ").strip()
            if not raw:
                return None
            rule["raw_body"] = raw
    else:
        field = input("  请求体字段路径: ").strip()
        if not field:
            return None
        value = input("  改成什么值: ").strip()
        rule["set_field"] = field
        rule["new_value"] = value

    print()
    return rule


def run_proxy():
    print_banner()

    from mitmproxy.tools.main import mitmdump

    console_thread = threading.Thread(target=interactive_console, args=(), daemon=True)
    console_thread.start()

    print("[*] 启动代理...\n")

    try:
        mitmdump([
            "-p", "8080",
            "--set", "block_global=false",
            "--quiet",
            "-s", MITMDUMP_SCRIPT,
        ])
    except SystemExit:
        pass
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n[-] 代理启动/运行出错: {e}")

    print("[*] 程序退出")


if __name__ == "__main__":
    run_proxy()