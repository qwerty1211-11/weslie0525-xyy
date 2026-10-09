#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小猿口算 - PK 模式自动答题
===========================
模式选择：
  [1] PK口算        识别算式(+ - × ÷) -> 计算 -> 点数字键盘输入
  [2] 比较大小      识别左右数字 -> 画 > < = 符号

核心策略：每次答题前动态扫描，从多个候选条带中找到算式
原理：ADB截图 -> 分条带OCR -> 找"数字+运算符+数字" -> 计算 -> 点击
速度：约 0.3~0.5秒/题
"""
import time
import os
import sys
import io
import re
import random
import subprocess
from PIL import Image
import numpy as np
import ddddocr
from ppadb.client import Client as AdbClient
ADB_HOST = "127.0.0.1"
ADB_PORT = 5037
ANSWER_DELAY = 0.1
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADB_PATH = os.path.join(SCRIPT_DIR, "platform-tools", "adb.exe")
EXPRESSION_RE = re.compile(r'(\d+)\s*([+\-*/xX×÷])\s*(\d+)')
COMPARE_RE = re.compile(r'(\d{1,2}).{0,8}(\d{1,2})')
def ensure_adb():
    if not os.path.exists(ADB_PATH):
        print("[-] 未找到ADB，请先下载 platform-tools 到:", ADB_PATH)
        return False
    subprocess.run([ADB_PATH, "start-server"], capture_output=True, timeout=10)
    time.sleep(0.5)
    return True
class XiaoYuanAuto:
    def __init__(self):
        self.device = None
        self.ocr = None
        self.running = False
        self.phone_w = None
        self.phone_h = None
        self.screen_ensured = False
        self._kb_region = None
        self._digit_positions = {}

    def connect_device(self):
        print("[*] 正在连接ADB设备...")
        try:
            client = AdbClient(host=ADB_HOST, port=ADB_PORT)
            devices = client.devices()
            if not devices:
                print("[-] 未找到设备")
                return False
            self.device = devices[0]
            print(f"[+] 设备: {self.device.serial}")
            self._get_screen_size()
            print("[*] 加载OCR模型...")
            self.ocr = ddddocr.DdddOcr(show_ad=False)
            print("[+] OCR就绪")
            return True
        except Exception as e:
            print(f"[-] 连接失败: {e}")
            return False
    def _get_screen_size(self):
        try:
            output = subprocess.run(
                [ADB_PATH, "-s", self.device.serial, "shell", "wm", "size"],
                capture_output=True, text=True, timeout=5
            ).stdout
            for word in output.replace("\n", " ").split():
                if "x" in word.lower():
                    parts = word.lower().split("x")
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        self.phone_w = int(parts[0])
                        self.phone_h = int(parts[1])
                        print(f"[+] 分辨率: {self.phone_w}x{self.phone_h}")
                        return
        except Exception:
            pass
        self.phone_w = self.phone_w or 1080
        self.phone_h = self.phone_h or 2400
        print(f"[!] 使用默认: {self.phone_w}x{self.phone_h}")
    def _tap_digits(self, digits):
        if not self._digit_positions:
            return
        cmds = []
        for ch in digits:
            pos = self._digit_positions.get(ch)
            if pos:
                jx = pos[0] + random.randint(-6, 6)
                jy = pos[1] + random.randint(-6, 6)
                dur = random.randint(20, 45)
                cmds.append(f"input swipe {jx} {jy} {jx} {jy} {dur}")
        if cmds:
            try:
                subprocess.run(
                    [ADB_PATH, "-s", self.device.serial, "shell", "; ".join(cmds)],
                    capture_output=True, timeout=5
                )
            except Exception:
                pass

    def _ensure_screen_on(self):
        if self.screen_ensured:
            return
        try:
            subprocess.run(
                [ADB_PATH, "-s", self.device.serial, "shell", "input", "keyevent", "224"],
                capture_output=True, timeout=5
            )
            time.sleep(0.15)
            subprocess.run(
                [ADB_PATH, "-s", self.device.serial, "shell", "input", "keyevent", "82"],
                capture_output=True, timeout=5
            )
            time.sleep(0.1)
        except Exception:
            pass
        self.screen_ensured = True

    def screenshot(self):
        self._ensure_screen_on()
        try:
            result = subprocess.run(
                [ADB_PATH, "-s", self.device.serial, "exec-out", "screencap", "-p"],
                capture_output=True, timeout=10
            )
            if result.returncode != 0 or not result.stdout:
                return None
            return Image.open(io.BytesIO(result.stdout))
        except Exception:
            return None

    def _scan_question_region(self, img, mode):
        W, H = self.phone_w, self.phone_h
        arr = np.array(img.convert('L'))

        row_contrasts = arr.std(axis=1)
        high_rows = np.where(row_contrasts > 12)[0]

        if len(high_rows) == 0:
            return None, None

        blocks = []
        start = high_rows[0]
        prev = start
        for y in high_rows[1:]:
            if y - prev > 15:
                blocks.append((int(start), int(prev)))
                start = y
            prev = y
        blocks.append((int(start), int(prev)))

        candidates = []

        for y1, y2 in blocks:
            h = y2 - y1
            if h < 40 or h > 300:
                continue

            sy1 = max(0, y1 - 8)
            sy2 = min(H, y2 + 8)
            strip = img.crop((0, sy1, W, sy2))
            gray = strip.convert('L')

            for thr in (170, 140, 200):
                bw = gray.point(lambda p: 255 if p < thr else 0)
                big = bw.resize((bw.width * 3, bw.height * 3), Image.NEAREST)
                try:
                    raw = self.ocr.classification(big)
                except Exception:
                    continue

                if not raw:
                    continue

                if mode == 1:
                    m = EXPRESSION_RE.search(raw)
                    if m:
                        op = m.group(2).replace('x', '+').replace('X', '+').replace('×', '*').replace('÷', '/')
                        candidates.append({
                            "y1": sy1, "y2": sy2, "raw": raw,
                            "a": int(m.group(1)), "op": op, "b": int(m.group(3)),
                            "score": len(raw)
                        })
                        break
                else:
                    nums = re.findall(r'\d', raw)
                    if len(nums) >= 2:
                        candidates.append({
                            "y1": sy1, "y2": sy2, "raw": raw,
                            "left": int(nums[0]), "right": int(nums[-1]),
                            "score": len(nums)
                        })
                        break

        if not candidates:
            return None, None

        candidates.sort(key=lambda c: c["score"], reverse=True)
        best = candidates[0]

        region = {"x": 0, "y": best["y1"], "w": W, "h": best["y2"] - best["y1"]}

        if mode == 1:
            result = (best["a"], best["op"], best["b"])
        else:
            result = (best["left"], best["right"])

        return region, result

    def _compute(self, a, op, b):
        if a is None or b is None or op is None:
            return None
        try:
            if op == '+':
                return a + b
            elif op == '-':
                return a - b
            elif op == '*':
                return a * b
            elif op == '/':
                return a // b if b != 0 and a % b == 0 else None
        except Exception:
            return None
        return None

    def _find_and_setup_keyboard(self, img):
        """动态找键盘区域并计算0-9按键坐标"""
        W, H = self.phone_w, self.phone_h
        arr = np.array(img.convert('L'))

        search_start = int(H * 0.40)
        search_end = int(H * 0.95)

        if search_start >= arr.shape[0]:
            return

        region = arr[search_start:search_end, :]
        row_stds = region.std(axis=1)
        row_means = region.mean(axis=1)

        button_rows = []
        for i in range(len(row_stds)):
            y = search_start + i
            if row_stds[i] > 12 and row_means[i] > 80:
                button_rows.append(y)

        if len(button_rows) < 20:
            self._kb_region = {
                "x": int(W * 0.05), "y": int(H * 0.55),
                "w": int(W * 0.90), "h": int(H * 0.38)
            }
        else:
            groups = []
            start = button_rows[0]
            prev = start
            for y in button_rows[1:]:
                if y - prev > 12:
                    groups.append((start, prev))
                    start = y
                prev = y
            groups.append((start, prev))
            groups.sort(key=lambda g: g[1] - g[0], reverse=True)

            if groups:
                kb_y1, kb_y2 = groups[0]
                col_stds = arr[kb_y1:kb_y2, :].std(axis=0)
                button_cols = [x for x in range(W) if col_stds[x] > 10]
                kb_x1 = min(button_cols) if button_cols else int(W * 0.05)
                kb_x2 = max(button_cols) if button_cols else int(W * 0.95)
                self._kb_region = {
                    "x": kb_x1, "y": kb_y1,
                    "w": kb_x2 - kb_x1, "h": kb_y2 - kb_y1
                }
            else:
                self._kb_region = {
                    "x": int(W * 0.05), "y": int(H * 0.55),
                    "w": int(W * 0.90), "h": int(H * 0.38)
                }

        self._calc_digit_positions()

    def _calc_digit_positions(self):
        if not self._kb_region:
            return
        kr = self._kb_region
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
        cols = 3
        rows = 4
        cell_w = kr["w"] / cols
        cell_h = kr["h"] / rows
        for i, k in enumerate(keys):
            col = i % cols
            row = i // cols
            cx = int(kr["x"] + cell_w * (col + 0.5))
            cy = int(kr["y"] + cell_h * (row + 0.5))
            self._digit_positions[k] = (cx, cy)

    def _draw_compare_symbol(self, q_region, symbol):
        W, H = self.phone_w, self.phone_h
        cx = W // 2 + random.randint(-10, 10)
        mid_y = (q_region["y"] + q_region["h"] + H * 0.55) // 2
        cy = mid_y + random.randint(-10, 10)
        size = max(min(W // 4, 120), 80)

        def _jitter(n):
            return n + random.randint(-8, 8)

        if symbol == ">":
            strokes = [
                (_jitter(cx-size), _jitter(cy-size), _jitter(cx+size), _jitter(cy)),
                (_jitter(cx+size), _jitter(cy+20), _jitter(cx-size), _jitter(cy+size)),
            ]
        elif symbol == "<":
            strokes = [
                (_jitter(cx+size), _jitter(cy-size), _jitter(cx-size), _jitter(cy)),
                (_jitter(cx-size), _jitter(cy+20), _jitter(cx+size), _jitter(cy+size)),
            ]
        elif symbol == "=":
            strokes = [
                (_jitter(cx-size), _jitter(cy-size//3), _jitter(cx+size), _jitter(cy-size//3)),
                (_jitter(cx-size), _jitter(cy+size//3), _jitter(cx+size), _jitter(cy+size//3)),
            ]
        else:
            return

        cmds = []
        for x1, y1, x2, y2 in strokes:
            dur = random.randint(160, 260)
            cmds.append(f"input swipe {x1} {y1} {x2} {y2} {dur}")

        try:
            subprocess.run(
                [ADB_PATH, "-s", self.device.serial, "shell", "; ".join(cmds)],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

    def run_pk_mode(self, max_count=999):
        print("\n" + "=" * 55)
        print("  PK口算自动答题 (动态扫描版)")
        print("=" * 55)
        print(f"  分辨率: {self.phone_w}x{self.phone_h}")
        print("  每道题都会动态扫描屏幕找算式")
        print("=" * 55)

        print("\n请确保手机已在 PK 答题界面（能看到算式和数字键盘）")
        input("按回车开始...")

        self.running = True
        count = 0
        last_expr = None
        fail_count = 0
        kb_setup = False

        try:
            while self.running and count < max_count:
                count += 1
                t0 = time.perf_counter()

                img = self.screenshot()
                if img is None:
                    time.sleep(0.2)
                    count -= 1
                    continue

                if not kb_setup:
                    self._find_and_setup_keyboard(img)
                    kb_setup = True
                    print(f"  [键盘] 区域={self._kb_region}")
                    print(f"  [键盘] 按键={self._digit_positions}")

                region, result = self._scan_question_region(img, mode=1)

                if region is None:
                    fail_count += 1
                    if fail_count >= 3:
                        print(f"[{count}] 扫描失败 (连续{fail_count})，可能不在答题界面")
                        img.save("debug_scan_fail.png")
                        time.sleep(0.5)
                    else:
                        time.sleep(0.15)
                    count -= 1
                    continue

                a, op, b = result
                fail_count = 0
                expr_str = f"{a}{op}{b}"

                if expr_str == last_expr:
                    time.sleep(random.uniform(0.06, 0.12))
                    count -= 1
                    continue

                answer = self._compute(a, op, b)
                if answer is None:
                    print(f"[{count}] {expr_str}=? 无法计算")
                    last_expr = expr_str
                    continue

                answer_str = str(answer)
                self._tap_digits(answer_str)

                elapsed = (time.perf_counter() - t0) * 1000
                print(f"[{count}] {expr_str}={answer}  [{elapsed:.0f}ms]")

                last_expr = expr_str
                time.sleep(random.uniform(0.08, 0.20))

        except KeyboardInterrupt:
            print(f"\n[!] 已停止，共完成 {count - 1} 题")
        finally:
            self.running = False

    def run_compare_mode(self, max_count=999):
        print("\n" + "=" * 55)
        print("  比较大小自动答题 (动态扫描版)")
        print("=" * 55)

        print("\n请确保手机已在比较大小答题界面")
        input("按回车开始...")

        self.running = True
        count = 0
        last_left, last_right = None, None
        fail_count = 0

        try:
            while self.running and count < max_count:
                count += 1

                img = self.screenshot()
                if img is None:
                    time.sleep(0.2)
                    count -= 1
                    continue

                region, result = self._scan_question_region(img, mode=2)

                if region is None:
                    fail_count += 1
                    if fail_count >= 3:
                        print(f"[{count}] 扫描失败 (连续{fail_count})")
                        img.save("debug_scan_fail.png")
                        time.sleep(random.uniform(0.3, 0.7))
                    else:
                        time.sleep(random.uniform(0.1, 0.2))
                    count -= 1
                    continue

                left, right = result
                fail_count = 0

                if left == last_left and right == last_right:
                    time.sleep(random.uniform(0.06, 0.12))
                    count -= 1
                    continue

                symbol = ">" if left > right else ("<" if left < right else "=")
                print(f"[{count}] {left} {symbol} {right}  ->  画 {symbol}")

                self._draw_compare_symbol(region, symbol)
                time.sleep(random.uniform(0.08, 0.20))

                last_left, last_right = left, right

        except KeyboardInterrupt:
            print(f"\n[!] 已停止，共完成 {count - 1} 题")
        finally:
            self.running = False

    def close(self):
        self.running = False


def main():
    if not ensure_adb():
        return

    auto = XiaoYuanAuto()
    if not auto.connect_device():
        return

    print("\n" + "=" * 55)
    print("  小猿口算自动答题 - 模式选择")
    print("=" * 55)
    print("  1. PK口算 (加减乘除, 点数字键盘)")
    print("  2. 比较大小 (画 > < =)")
    print("=" * 55)

    mode = input("请选择 [1/2]: ").strip()

    if mode not in ("1", "2"):
        print("无效选择")
        return

    try:
        if mode == "1":
            auto.run_pk_mode()
        elif mode == "2":
            auto.run_compare_mode()
    except Exception as e:
        print(f"[-] 出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        auto.close()


if __name__ == "__main__":
    main()