import io
import os
import random
import re
import subprocess
import sys
import time
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
try:
    from ppadb.client import Client as AdbClient
except ImportError:
    print("[-] 缺少依赖: pip install pure-python-adb")
    raise
try:
    import ddddocr
except ImportError:
    print("[-] 缺少依赖: pip install ddddocr")
    raise
try:
    import cv2  # 可选：有 cv2 时用它的连通域/形态学，速度更快
except ImportError:
    cv2 = None
# =============================================
# 配置
# =============================================
ADB_HOST = "127.0.0.1"
ADB_PORT = 5037
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
import shutil as _shutil
if os.name == "nt":
    _local_adb = os.path.join(SCRIPT_DIR, "platform-tools", "adb.exe")
else:
    _local_adb = os.path.join(SCRIPT_DIR, "platform-tools", "adb")
if os.path.exists(_local_adb):
    ADB_PATH = _local_adb
else:
    ADB_PATH = _shutil.which("adb") or _local_adb
# 题目搜索带（相对屏幕高度）。键盘区域会在运行时被进一步排除。
# 收紧范围：跳过状态栏/标题栏，避免把"第 N 题"等小字拉进题目带
QUESTION_TOP_RATIO = 0.10
QUESTION_BOTTOM_RATIO = 0.52
# 比较模式的合法数字范围
COMPARE_MIN, COMPARE_MAX = 0, 999
# 速度倍率：1.0=正常  2.0=较快  4.0=极速
# 数值越大，答题越快，但过快可能导致 OCR 识别和 ADB 点击跟不上
SPEED_FACTOR = 1.0
# 目标字形高度（像素）：确保送给 OCR 的字形足够大
TARGET_GLYPH_H = 56
# 最小字形高度（放大后的像素）
MIN_GLYPH_H = 20
# 单字符识别结果 -> 数字 的兜底纠错表。
# 注意：仅在"该字形已被几何判定为数字位"且 OCR 返回非数字时才使用，
# 不再像旧版那样对整段文本无脑替换字母。
GLYPH_FALLBACK_DIGIT = {
    "o": "0", "O": "0", "q": "0", "D": "0",
    "l": "1", "I": "1", "|": "1", "!": "1", "i": "1",
    "z": "2", "Z": "2",
    "e": "3", "E": "3",
    "a": "4", "A": "4", "h": "4",
    "s": "5", "S": "5",
    "b": "6",
    "G": "6",
    "T": "7",
    "B": "8",
    "g": "9",
}

# 运算符归一化
OPERATOR_MAP = {
    "x": "*", "X": "*", "×": "*", "✕": "*", "＊": "*", "*": "*",
    "÷": "/", "／": "/", "/": "/",
    "+": "+", "＋": "+", "t": "+",
    "-": "-", "—": "-", "－": "-", "–": "-",
}

# 二值化方法列表（按优先级）
BIN_METHODS = ("otsu", "thr130", "thr150", "thr170", "adaptive", "nobig_otsu")


def ensure_adb():
    if not os.path.exists(ADB_PATH):
        print("[-] 未找到 ADB，请把 platform-tools 放到:", ADB_PATH)
        return False
    try:
        subprocess.run([ADB_PATH, "start-server"], capture_output=True, timeout=10)
    except Exception:
        return False
    time.sleep(0.4)
    return True


# =============================================
# 图像处理基础函数（无第三方强依赖，cv2 可选加速）
# =============================================

def otsu_threshold(arr):
    """Otsu 自动阈值：由图像直方图自行决定最佳分割点，替代旧版 4 个固定阈值。"""
    hist = np.bincount(arr.ravel(), minlength=256).astype(np.float64)
    total = arr.size
    if total == 0:
        return 128
    sum_all = float((np.arange(256) * hist).sum())
    sum_bg = 0.0
    weight_bg = 0.0
    best_thr, best_var = 128, -1.0
    for thr in range(256):
        weight_bg += hist[thr]
        if weight_bg == 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg == 0:
            break
        sum_bg += float(thr * hist[thr])
        mean_bg = sum_bg / weight_bg
        mean_fg = (sum_all - sum_bg) / weight_fg
        var_between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
        if var_between > best_var:
            best_var = var_between
            best_thr = thr
    return int(best_thr)


def _label_runs(mask):
    """
    纯 numpy 的行游程连通域标记（4 邻域），返回 [(x1, y1, x2, y2, area), ...]。
    mask: bool 数组。相比逐像素 BFS，游程法在小图上快一到两个数量级。
    """
    h, w = mask.shape
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    runs = []  # (label, y, x_start, x_end_exclusive)
    next_label = 1
    prev_row_runs = []

    for y in range(h):
        row = mask[y]
        if not row.any():
            prev_row_runs = []
            continue
        padded = np.concatenate(([0], row.view(np.int8), [0]))
        diff = np.diff(padded)
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        cur_row_runs = []
        for xs, xe in zip(starts, ends):
            lab = next_label
            next_label += 1
            parent[lab] = lab
            cur_row_runs.append((lab, int(xs), int(xe)))
        # 与上一行做重叠合并
        for lab, xs, xe in cur_row_runs:
            for plab, pxs, pxe in prev_row_runs:
                if xs < pxe and pxs < xe:
                    union(lab, plab)
        runs.extend([(lab, y, xs, xe) for lab, xs, xe in cur_row_runs])
        prev_row_runs = cur_row_runs

    boxes = {}
    for lab, y, xs, xe in runs:
        root = find(lab)
        cnt = xe - xs
        if root not in boxes:
            boxes[root] = [xs, y, xe - 1, y, cnt]
        else:
            b = boxes[root]
            if xs < b[0]:
                b[0] = xs
            if y < b[1]:
                b[1] = y
            if xe - 1 > b[2]:
                b[2] = xe - 1
            if y > b[3]:
                b[3] = y
            b[4] += cnt
    return [(b[0], b[1], b[2], b[3], b[4]) for b in boxes.values()]


def connected_components(mask):
    """连通域标记，优先 cv2，回退到纯 numpy 游程法。"""
    if mask.size == 0:
        return []
    if cv2 is not None:
        u8 = (mask.astype(np.uint8)) * 255
        n, _, stats, _ = cv2.connectedComponentsWithStats(u8, connectivity=8)
        out = []
        for i in range(1, n):
            x, y, w, h, area = stats[i]
            out.append((int(x), int(y), int(x + w - 1), int(y + h - 1), int(area)))
        return out
    return _label_runs(mask)


def to_foreground_mask(gray, step="otsu"):
    """灰度图 -> 前景（字形）布尔掩码。支持更多预处理方法。"""
    arr = np.array(gray, dtype=np.uint8)

    if step in ("thr100", "thr110", "thr120", "thr130", "thr140",
                "thr150", "thr160", "thr170", "thr180", "thr190"):
        thr = int(step[3:])
        mask = arr < thr
    elif step == "inverse_thr":
        thr = otsu_threshold(arr)
        mask = arr > thr
    elif step == "adaptive" and cv2 is not None:
        bw = cv2.adaptiveThreshold(
            arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10
        )
        mask = bw < 127
    elif step == "adaptive2" and cv2 is not None:
        bw = cv2.adaptiveThreshold(
            arr, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 21, 5
        )
        mask = bw < 127
    elif step == "nobig_otsu":
        rough_thr = otsu_threshold(arr)
        rough_mask = arr > rough_thr
        if rough_mask.mean() > 0.5:
            rough_mask = ~rough_mask
        rough_u8 = rough_mask.astype(np.uint8) * 255
        if cv2 is not None:
            n, labels = cv2.connectedComponents(rough_u8)
            cleaned = arr.copy()
            max_blob = max(arr.shape) * 0.4
            for lbl in range(1, n):
                ys, xs = np.where(labels == lbl)
                h = ys.max() - ys.min() + 1
                w = xs.max() - xs.min() + 1
                if h > max_blob or w > max_blob:
                    cleaned[labels == lbl] = 255
            thr = otsu_threshold(cleaned)
            mask = cleaned < thr
        else:
            thr = otsu_threshold(arr)
            mask = arr < thr
    else:
        thr = otsu_threshold(arr)
        mask = arr < thr

    if mask.mean() > 0.5:
        mask = ~mask

    mask[0, :] = False
    mask[-1, :] = False
    mask[:, 0] = False
    mask[:, -1] = False
    return mask


def morphology_clean(mask):
    """形态学去噪 + 断开粘连：开运算去小点，腐蚀断开粘连笔画。"""
    if cv2 is None:
        return mask
    u8 = mask.astype(np.uint8) * 255
    k_open = np.ones((2, 2), np.uint8)
    u8 = cv2.morphologyEx(u8, cv2.MORPH_OPEN, k_open)
    k_erode = np.ones((1, 3), np.uint8)
    u8 = cv2.erode(u8, k_erode, iterations=1)
    return u8 > 127


def morphology_reconnect(mask):
    """轻度闭运算：把过度断开的笔画重新连起来。"""
    if cv2 is None:
        return mask
    u8 = mask.astype(np.uint8) * 255
    k = np.ones((2, 2), np.uint8)
    u8 = cv2.morphologyEx(u8, cv2.MORPH_CLOSE, k)
    return u8 > 127


def upscale_band(band_img, target_glyph_h=TARGET_GLYPH_H):
    """
    自适应放大题目带：先粗略探测现有字形大小，按比例放大到目标高度。
    返回 (放大后的PIL灰度图, 放大比例float)。
    这是解决"识别准确率低"的最关键一步——高分辨率手机上数字像素小，
    放大后再分割+识别，准确率会有质的飞跃。
    """
    gray = band_img.convert("L")
    arr = np.array(gray)

    thr = otsu_threshold(arr)
    rough_mask = arr < thr
    if rough_mask.mean() > 0.5:
        rough_mask = ~rough_mask
    rough_mask[0, :] = False
    rough_mask[-1, :] = False
    rough_mask[:, 0] = False
    rough_mask[:, -1] = False

    comps = connected_components(rough_mask)
    if not comps:
        return gray, 1.0

    heights = [c[3] - c[1] + 1 for c in comps]
    heights.sort(reverse=True)
    if len(heights) >= 3:
        ref_h = float(np.median(heights[:5]))
    elif heights:
        ref_h = float(np.median(heights))
    else:
        ref_h = 30.0

    if ref_h < 20:
        scale = float(target_glyph_h) / max(ref_h, 10)
    elif ref_h < 40:
        scale = float(target_glyph_h) / ref_h
    else:
        scale = 1.0

    scale = max(1.0, min(scale, 4.0))

    if abs(scale - 1.0) < 0.05:
        return gray, 1.0

    new_w = max(1, int(gray.width * scale))
    new_h = max(1, int(gray.height * scale))

    if cv2 is not None:
        upscaled = cv2.resize(arr, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        upscaled_pil = Image.fromarray(upscaled, mode="L")
    else:
        upscaled_pil = gray.resize((new_w, new_h), Image.LANCZOS)

    return upscaled_pil, scale


# =============================================
# 主类
# =============================================

class XiaoYuanAuto:
    def __init__(self):
        self.device = None
        self.device_serial = None
        self.ocr = None
        self.running = False
        self.phone_w = None
        self.phone_h = None
        self.screen_ensured = False
        self._last_screen_on_check = 0
        self._kb_region = None
        self._digit_positions = {}
        self._fail_streak = 0
        self._kb_setup_done = False
        self.debug = False
        self._debug_dir = os.path.join(SCRIPT_DIR, "debug_glyphs")
        self.speed = SPEED_FACTOR
        self._last_band_fp = None
        self._answer_at = 0

    def _sleep(self, seconds):
        """按速度倍率缩短的 sleep；速度 <= 0 时跳过。"""
        if self.speed and self.speed > 0:
            time.sleep(seconds / self.speed)

    # ==================== 设备连接 ====================

    def _reconnect_device(self):
        try:
            subprocess.run([ADB_PATH, "kill-server"], capture_output=True, timeout=3)
            time.sleep(0.4)
            subprocess.run([ADB_PATH, "start-server"], capture_output=True, timeout=5)
            time.sleep(0.4)
            client = AdbClient(host=ADB_HOST, port=ADB_PORT)
            devices = client.devices()
            if devices:
                self.device = devices[0]
                self.device_serial = self.device.serial
                self._get_screen_size()
                self.screen_ensured = False
                self._kb_setup_done = False
                self._kb_region = None
                self._digit_positions = {}
                print(f"[+] 重连成功: {self.device_serial}")
                return True
            print("[-] 重连失败：未找到设备")
        except Exception as e:
            print(f"[-] 重连异常: {e}")
        return False

    def ensure_device(self):
        if self.device is None:
            return self._reconnect_device()
        try:
            r = subprocess.run(
                [ADB_PATH, "-s", self.device.serial, "shell", "echo", "ok"],
                capture_output=True, text=True, timeout=3,
            )
            if r.stdout.strip() == "ok":
                self._fail_streak = 0
                return True
        except Exception:
            pass
        self._fail_streak += 1
        if self._fail_streak >= 2:
            print("[!] 设备连续无响应，尝试重连...")
            self.device = None
            return self._reconnect_device()
        return True

    def connect_device(self):
        print("[*] 正在连接 ADB 设备...")
        try:
            client = AdbClient(host=ADB_HOST, port=ADB_PORT)
            devices = client.devices()
            if not devices:
                print("[-] 未找到设备（请确认已开启 USB 调试并授权）")
                return False
            self.device = devices[0]
            self.device_serial = self.device.serial
            print(f"[+] 设备: {self.device_serial}")
            self._get_screen_size()
            print("[*] 加载 OCR 模型...")
            self.ocr = ddddocr.DdddOcr(show_ad=False)
            print("[+] OCR 就绪")
            return True
        except Exception as e:
            print(f"[-] 连接失败: {e}")
            return False

    def _get_screen_size(self):
        try:
            out = subprocess.run(
                [ADB_PATH, "-s", self.device.serial, "shell", "wm", "size"],
                capture_output=True, text=True, timeout=5,
            ).stdout
            m = re.findall(r"(\d+)\s*x\s*(\d+)", out)
            if m:
                # 取最后一组（Override size 优先于 Physical size）
                self.phone_w, self.phone_h = int(m[-1][0]), int(m[-1][1])
                print(f"[+] 分辨率: {self.phone_w}x{self.phone_h}")
                return
        except Exception:
            pass
        self.phone_w = self.phone_w or 1080
        self.phone_h = self.phone_h or 2400
        print(f"[!] 未能读取分辨率，使用默认: {self.phone_w}x{self.phone_h}")

    # ==================== 截图 ====================

    def _ensure_screen_on(self):
        now = time.time()
        if self.screen_ensured and (now - self._last_screen_on_check) < 15:
            return
        try:
            subprocess.run(
                [ADB_PATH, "-s", self.device.serial, "shell", "input", "keyevent", "224"],
                capture_output=True, timeout=3,
            )
            time.sleep(0.08)
            subprocess.run(
                [ADB_PATH, "-s", self.device.serial, "shell", "input", "keyevent", "82"],
                capture_output=True, timeout=3,
            )
            time.sleep(0.06)
        except Exception:
            pass
        self.screen_ensured = True
        self._last_screen_on_check = now

    def screenshot(self):
        self._ensure_screen_on()
        for attempt in range(2):
            try:
                r = subprocess.run(
                    [ADB_PATH, "-s", self.device.serial, "exec-out", "screencap", "-p"],
                    capture_output=True, timeout=6,
                )
                if r.returncode == 0 and r.stdout:
                    return Image.open(io.BytesIO(r.stdout)).convert("RGB")
            except Exception:
                pass
            if attempt == 0:
                time.sleep(0.06)
        return None

    # ==================== 字形分割（替代旧的整行 OCR） ====================

    def _question_band(self, img):
        """裁出题目带，自动检测深色内容的纵向范围。"""
        W, H = self.phone_w, self.phone_h
        arr = np.array(img.convert("L"))
        y1_hint = int(H * QUESTION_TOP_RATIO)
        y2_hint = int(H * QUESTION_BOTTOM_RATIO)
        if self._kb_region:
            kb_top = self._kb_region["y"]
            y2_hint = min(y2_hint, max(y1_hint + 40, kb_top - int(H * 0.03)))
        y2_hint = min(y2_hint, H)

        search = arr[y1_hint:y2_hint, :]
        row_stds = search.std(axis=1)
        row_means = search.mean(axis=1)

        content_rows = np.where((row_stds > 8) & (row_means < 250))[0]
        if len(content_rows) >= 20:
            groups, start, prev = [], content_rows[0], content_rows[0]
            for yy in content_rows[1:]:
                if yy - prev > 15:
                    groups.append((int(start), int(prev)))
                    start = yy
                prev = yy
            groups.append((int(start), int(prev)))
            # 过滤太短的噪声组（少于 8 行的跳过）
            groups = [g for g in groups if (g[1] - g[0]) >= 8]
            if groups:
                # 对每个组，估算其内容的"字形平均高度"（行跨度）
                # 主算式的字远大于标题栏和倒计时的小字，取"跨度最大"的组
                # 但如果有多个组跨度接近，选中间位置的那个（标题通常靠上）
                groups.sort(key=lambda g: g[1] - g[0], reverse=True)
                best_span = groups[0][1] - groups[0][0]
                candidates = [g for g in groups if (g[1] - g[0]) >= best_span * 0.7]
                if len(candidates) >= 2:
                    # 多个相近跨度的组：选 y 居中的那个（避开顶部标题栏）
                    mid_y = (y1_hint + y2_hint) // 2
                    candidates.sort(key=lambda g: abs((g[0] + g[1]) // 2 - mid_y))
                    gy1, gy2 = candidates[0]
                else:
                    gy1, gy2 = groups[0]
                y1 = y1_hint + max(0, gy1 - 8)
                y2 = y1_hint + min(len(search), gy2 + 12)
            else:
                y1, y2 = y1_hint, y2_hint
        else:
            y1, y2 = y1_hint, y2_hint
        y2 = min(y2, H)
        return img.crop((0, y1, W, y2)), y1, y2

    def _band_fingerprint(self, img):
        """
        对题目带做一个快速指纹（numpy 计算，极快）。
        答完一题后，用这个指纹轮询判断屏幕是否真的切换了——只检测"题目带区域"的灰度布局变化，
        不做任何 OCR。变了才开始真正识别，替代原来的固定冷却时间。
        """
        W, H = self.phone_w, self.phone_h
        arr = np.array(img.convert("L"))
        y1_hint = int(H * QUESTION_TOP_RATIO)
        y2_hint = int(H * QUESTION_BOTTOM_RATIO)
        if self._kb_region:
            y2_hint = min(y2_hint, self._kb_region["y"] - int(H * 0.03))
        y2_hint = min(y2_hint, H)
        y1_hint = max(0, y1_hint)
        band = arr[y1_hint:y2_hint, :]
        if band.size == 0:
            return None
        # 缩放到 64x16，算一个 1024 字节的哈希（非常快，毫秒级）
        if cv2 is not None:
            small = cv2.resize(band, (64, 16), interpolation=cv2.INTER_AREA)
        else:
            from PIL import Image as PILImage
            small = np.array(PILImage.fromarray(band).resize((64, 16), Image.BILINEAR))
        return small.tobytes()

    def _wait_until_band_changes(self, timeout_sec=2.5):
        """
        快速轮询截图 + 指纹计算，直到题目带真的变了才返回。
        返回 (img, changed) — changed=False 表示超时或截图失败。
        """
        t_deadline = time.time() + timeout_sec
        while time.time() < t_deadline:
            img = self.screenshot()
            if img is None:
                self._sleep(0.02)
                continue
            fp = self._band_fingerprint(img)
            if fp is None:
                self._sleep(0.02)
                continue
            # 第一次调用时没有上一帧，直接返回
            if self._last_band_fp is None:
                self._last_band_fp = fp
                return img, True
            # 指纹变化幅度超过阈值才算真的变了（避免轻微噪声误触发）
            diff = np.frombuffer(fp, dtype=np.uint8)
            prev = np.frombuffer(self._last_band_fp, dtype=np.uint8)
            dist = float(np.abs(diff.astype(np.int16) - prev.astype(np.int16)).mean())
            if dist > 8.0:
                self._last_band_fp = fp
                return img, True
            self._sleep(0.04)
        return None, False

    def _segment_glyphs(self, band_img, step="otsu", min_h=None):
        """
        从题目带中分割出独立字形。
        返回按 x 排序的 [(x1, y1, x2, y2, area, crop_img), ...]（坐标为带内坐标）。
        关键改进：每次都做形态学去噪 + 断开粘连，min_h 动态计算。
        """
        gray = band_img.convert("L")

        if min_h is None:
            min_h = max(MIN_GLYPH_H, int(band_img.height * 0.08))

        mask = to_foreground_mask(np.array(gray), step=step)
        mask = morphology_clean(mask)

        comps = connected_components(mask)
        if not comps:
            return []

        bh = band_img.height
        bw = band_img.width
        h_floor = min_h
        h_ceil = bh * 0.90

        cands = []
        for x1, y1, x2, y2, area in comps:
            w = x2 - x1 + 1
            h = y2 - y1 + 1
            if h < h_floor:
                continue
            if h > h_ceil:
                continue
            if w < max(4, int(h * 0.08)):
                continue
            aspect = w / float(max(h, 1))
            if aspect > 3.2 or aspect < 0.05:
                continue
            if w > bw * 0.6:
                continue
            fill = area / float(max(w * h, 1))
            if fill < 0.03 or fill > 0.97:
                continue
            cands.append((x1, y1, x2, y2, area))

        if not cands:
            mask2 = morphology_reconnect(mask)
            comps2 = connected_components(mask2)
            for x1, y1, x2, y2, area in comps2:
                w = x2 - x1 + 1
                h = y2 - y1 + 1
                if h < h_floor or h > h_ceil:
                    continue
                aspect = w / float(max(h, 1))
                if aspect > 3.2 or aspect < 0.05:
                    continue
                fill = area / float(max(w * h, 1))
                if fill < 0.03 or fill > 0.97:
                    continue
                cands.append((x1, y1, x2, y2, area))

        if not cands:
            return []

        refined = []
        for x1, y1, x2, y2, area in cands:
            w = x2 - x1 + 1
            h = y2 - y1 + 1
            aspect = w / float(max(h, 1))
            if 1.8 <= aspect <= 3.0 and cv2 is not None and w >= h:
                mid = (x1 + x2) // 2
                refined.append((x1, y1, mid, y2, area // 2))
                refined.append((mid + 1, y1, x2, y2, area // 2))
            else:
                refined.append((x1, y1, x2, y2, area))

        mid_ys = sorted(((c[1] + c[3]) / 2.0, c) for c in refined)
        rows = []
        for my, c in mid_ys:
            placed = False
            h_c = c[3] - c[1]
            for row in rows:
                row_h = row["h"]
                if (abs(row["center"] - my) <= max(10, row_h * 0.25)
                        and abs(h_c - row_h) <= max(8, row_h * 0.35)):
                    row["items"].append(c)
                    row["center"] = float(np.mean([(i[1] + i[3]) / 2.0 for i in row["items"]]))
                    row["h"] = float(np.mean([i[3] - i[1] for i in row["items"]]))
                    placed = True
                    break
            if not placed:
                rows.append({"center": my, "h": float(c[3] - c[1]), "items": [c]})

        rows = [r for r in rows if len(r["items"]) >= 2]
        if not rows:
            return []
        rows.sort(key=lambda r: (
            len(r["items"])
            * r["h"]
            * sum((c[2] - c[0]) * (c[3] - c[1]) for c in r["items"])
        ), reverse=True)
        best = rows[0]["items"]
        best.sort(key=lambda c: c[0])

        out = []
        for x1, y1, x2, y2, area in best:
            pad = max(4, int(max(x2 - x1, y2 - y1) * 0.25))
            crop = gray.crop((
                max(0, x1 - pad), max(0, y1 - pad),
                min(gray.width, x2 + 1 + pad), min(gray.height, y2 + 1 + pad),
            ))
            out.append((x1, y1, x2, y2, area, crop))
        return out

    def _classify_glyph(self, crop, allowed_digits):
        """
        单字符 OCR：灰度 + 二值化，用 LANCZOS 缩放保证质量，多次尝试直到命中 allowed_digits。
        关键改进：先把字形做成干净的白底黑字/黑底白字二值图，再送去 OCR。
        """
        if crop is None:
            return None
        try:
            arr = np.array(crop, dtype=np.uint8)
            if arr.size == 0:
                return None

            is_dark_on_light = float(arr.mean()) > 128

            if not is_dark_on_light:
                arr = 255 - arr

            thr = otsu_threshold(arr)
            bw_arr = (arr > thr).astype(np.uint8) * 255
            bw_pil = Image.fromarray(bw_arr, mode="L")

            img0 = Image.fromarray(arr, mode="L")

            variants = [img0, bw_pil]

            target_h = 64
            canvas_size = 96
            best_raw = ""
            for img in variants:
                try:
                    ratio = target_h / float(max(img.height, 1))
                    new_w = max(12, int(img.width * ratio))
                    img_resized = img.resize((new_w, target_h), Image.LANCZOS)
                    canvas = Image.new("L", (canvas_size, canvas_size), 255)
                    if new_w > canvas_size - 8:
                        scale = (canvas_size - 8) / float(new_w)
                        new_w = canvas_size - 8
                        img_resized = img.resize((new_w, max(12, int(target_h * scale))), Image.LANCZOS)
                    canvas.paste(img_resized, ((canvas_size - new_w) // 2,
                                              (canvas_size - img_resized.height) // 2))
                    raw = (self.ocr.classification(canvas) or "").strip()
                    if raw:
                        best_raw = raw
                        for ch in raw:
                            if ch.isdigit():
                                d = int(ch)
                                if d in allowed_digits:
                                    return d
                        for ch in raw:
                            fixed = GLYPH_FALLBACK_DIGIT.get(ch)
                            if fixed is not None and int(fixed) in allowed_digits:
                                return int(fixed)
                except Exception:
                    continue

            if best_raw:
                for ch in best_raw:
                    if ch.isdigit():
                        d = int(ch)
                        if d in allowed_digits:
                            return d
                for ch in best_raw:
                    fixed = GLYPH_FALLBACK_DIGIT.get(ch)
                    if fixed is not None and int(fixed) in allowed_digits:
                        return int(fixed)
        except Exception:
            pass
        return None

    def _classify_operator(self, crop):
        """识别运算符字形。结合 OCR 与几何特征，二义时以几何为准。"""
        if crop is None:
            return None
        w, h = crop.size
        arr = np.array(crop, dtype=np.uint8)
        dark_ratio = float((arr < 128).mean())
        aspect = w / float(max(h, 1))

        raw = None
        try:
            if float(arr.mean()) < 110:
                arr2 = 255 - arr
            else:
                arr2 = arr
            img = Image.fromarray(arr2).convert("L")
            img = img.resize((max(8, int(img.width * (64 / float(img.height)))), 64), Image.BICUBIC)
            canvas = Image.new("L", (96, 96), 255)
            canvas.paste(img, ((96 - img.width) // 2, (96 - img.height) // 2))
            raw = self.ocr.classification(canvas)
        except Exception:
            raw = None

        # 几何优先：减号是明显的扁横条
        if aspect > 1.8 and h < 22 and dark_ratio < 0.5:
            return "-"
        # 除号：上下两点 + 中间横杠，暗像素占比低且分散
        if raw:
            for ch in raw:
                if ch in OPERATOR_MAP:
                    return OPERATOR_MAP[ch]
        if aspect > 1.6:
            return "-"
        return None

    # ==================== 识别：比较大小（0-5） ====================

    def recognize_compare(self, img):
        """
        返回 (left, right, band_offset_y, detail) 或 None。
        左右由字形的 x 坐标决定（空间关系），不再依赖 OCR 文本顺序。
        """
        band, oy1, oy2 = self._question_band(img)
        allowed = set(range(COMPARE_MIN, COMPARE_MAX + 1))

        upscaled, scale = upscale_band(band)

        for step in BIN_METHODS:
            glyphs = self._segment_glyphs(upscaled, step=step)
            if len(glyphs) < 2:
                continue

            digits = []
            for g in glyphs:
                d = self._classify_glyph(g[5], allowed)
                digits.append((g, d))

            valid = [(g, d) for g, d in digits if d is not None]
            if len(valid) < 2:
                if self.debug:
                    print(f"    [debug] step={step} 有效数字不足: {[(d) for _, d in digits]}")
                continue

            valid.sort(key=lambda t: t[0][0])
            best_gap, split_i = -1, None
            for i in range(1, len(valid)):
                gap = valid[i][0][0] - valid[i - 1][0][2]
                if gap > best_gap:
                    best_gap, split_i = gap, i

            if split_i is None or split_i == 0 or split_i >= len(valid):
                continue

            left_group = valid[:split_i]
            right_group = valid[split_i:]

            def pick(group):
                return max(group, key=lambda t: (t[0][3] - t[0][1]) * (t[0][2] - t[0][0]))[1]

            left, right = pick(left_group), pick(right_group)

            if not (COMPARE_MIN <= left <= COMPARE_MAX and COMPARE_MIN <= right <= COMPARE_MAX):
                continue

            detail = {
                "step": step,
                "scale": round(scale, 2),
                "glyphs": len(glyphs),
                "valid": len(valid),
                "gap": best_gap,
            }
            return left, right, oy1, detail

        return None

    # ==================== 识别：口算算式 ====================

    def recognize_expression(self, img):
        """返回 (a, op, b, band_offset_y, detail) 或 None。"""
        band, oy1, oy2 = self._question_band(img)
        allowed = set(range(0, 10))

        upscaled, scale = upscale_band(band)

        for step in BIN_METHODS:
            glyphs = self._segment_glyphs(upscaled, step=step)
            if len(glyphs) < 3:
                continue

            tokens = []
            prev_x2 = None
            cur_num_chars = []
            cur_num_hs = []
            cur_num_xs = []

            def flush_num():
                nonlocal cur_num_chars, cur_num_hs, cur_num_xs, tokens
                if cur_num_chars:
                    val = int("".join(cur_num_chars))
                    avg_h = float(np.mean(cur_num_hs))
                    mid_x = float(np.mean(cur_num_xs))
                    tokens.append(("num", val, avg_h, mid_x))
                    cur_num_chars, cur_num_hs, cur_num_xs = [], [], []

            for g in glyphs:
                x1, y1, x2, y2, area, crop = g
                h = y2 - y1
                w = x2 - x1

                if prev_x2 is not None and (x1 - prev_x2) > max(18 * scale, w * 1.2):
                    flush_num()

                d = self._classify_glyph(crop, allowed)
                if d is not None:
                    cur_num_chars.append(str(d))
                    cur_num_hs.append(float(h))
                    cur_num_xs.append(float((x1 + x2) / 2.0))
                else:
                    flush_num()
                    op = self._classify_operator(crop)
                    if op:
                        h_g = float(h)
                        mx = float((x1 + x2) / 2.0)
                        if not (tokens and tokens[-1][0] == "op"):
                            tokens.append(("op", op, h_g, mx))
                prev_x2 = x2

            flush_num()

            candidates = []
            for i in range(len(tokens) - 2):
                t0, t1, t2 = tokens[i], tokens[i + 1], tokens[i + 2]
                if t0[0] == "num" and t1[0] == "op" and t2[0] == "num":
                    avg_h = (t0[2] + t2[2]) / 2.0
                    h_consistency = 1.0 - abs(t0[2] - t2[2]) / max(t0[2], t2[2], 1)
                    center_x = (t0[3] + t2[3]) / 2.0
                    upscaled_center = upscaled.width / 2.0
                    x_score = 1.0 - abs(center_x - upscaled_center) / max(upscaled_center, 1)
                    score = avg_h * h_consistency * (0.5 + 0.5 * x_score)
                    candidates.append((score, i, (t0[1], t1[1], t2[1])))

            if not candidates:
                if self.debug:
                    print(f"    [debug] step={step} token 序列不合法: {[(t[0], t[1]) for t in tokens]}")
                continue

            candidates.sort(key=lambda c: c[0], reverse=True)
            _, _, seq = candidates[0]
            a, op, b = seq

            if not self._validate_expression(a, op, b):
                continue

            return a, op, b, oy1, {
                "step": step,
                "scale": round(scale, 2),
                "glyphs": len(glyphs),
                "tokens": [(t[0], t[1]) for t in tokens],
            }

        return None

    def _validate_expression(self, a, op, b):
        """算式合理性校验：拦掉明显不可能的识别结果。"""
        if not (0 <= a <= 9999 and 0 <= b <= 9999):
            return False
        if op == "/":
            if b == 0 or a % b != 0:
                return False
        if op == "-":
            # 小学口算一般不出现负数结果
            if a - b < 0:
                return False
        if op == "*":
            if a * b > 99999:
                return False
        return True

    def _compute(self, a, op, b):
        try:
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                return a // b if b != 0 and a % b == 0 else None
        except Exception:
            return None
        return None

    # ==================== 键盘定位 ====================

    def _find_and_setup_keyboard(self, img):
        W, H = self.phone_w, self.phone_h
        arr = np.array(img.convert("L"))
        search_start = int(H * 0.40)
        search_end = min(int(H * 0.98), arr.shape[0])
        if search_start >= search_end:
            return

        region = arr[search_start:search_end, :]
        row_stds = region.std(axis=1)
        row_means = region.mean(axis=1)
        button_rows = [
            search_start + i for i in range(len(row_stds))
            if row_stds[i] > 10 and row_means[i] > 80
        ]

        if len(button_rows) < 15:
            self._kb_region = {
                "x": int(W * 0.05), "y": int(H * 0.55),
                "w": int(W * 0.90), "h": int(H * 0.38),
            }
            self._calc_digit_positions()
            return

        groups, start, prev = [], button_rows[0], button_rows[0]
        for y in button_rows[1:]:
            if y - prev > 12:
                groups.append((start, prev))
                start = y
            prev = y
        groups.append((start, prev))
        groups.sort(key=lambda g: g[1] - g[0], reverse=True)

        kb_y1, kb_y2 = groups[0]
        col_stds = arr[kb_y1:kb_y2 + 1, :].std(axis=0)
        button_cols = [x for x in range(len(col_stds)) if col_stds[x] > 8]
        kb_x1 = min(button_cols) if button_cols else int(W * 0.05)
        kb_x2 = max(button_cols) if button_cols else int(W * 0.95)
        self._kb_region = {"x": kb_x1, "y": kb_y1, "w": kb_x2 - kb_x1, "h": kb_y2 - kb_y1}

        self._ocr_digit_positions(img)
        if not self._digit_positions:
            self._calc_digit_positions()

    def _ocr_digit_positions(self, img):
        """用字形分割定位键盘数字键（先放大再识别）。"""
        if not self._kb_region:
            return
        kr = self._kb_region
        x1, y1 = kr["x"], kr["y"]
        x2, y2 = x1 + kr["w"], y1 + kr["h"]
        x2 = min(x2, img.width)
        y2 = min(y2, img.height)
        if x2 <= x1 or y2 <= y1:
            return
        kb_img = img.crop((x1, y1, x2, y2))
        allowed = set(range(0, 10))

        kb_up, kb_scale = upscale_band(kb_img, target_glyph_h=40)

        glyphs = self._segment_glyphs(kb_up, step="otsu")
        found = {}
        for gx1, gy1, gx2, gy2, area, crop in glyphs:
            d = self._classify_glyph(crop, allowed)
            if d is None:
                continue
            key = str(d)
            if key in found:
                continue
            real_cx = x1 + int((gx1 + gx2) / 2.0 / kb_scale)
            real_cy = y1 + int((gy1 + gy2) / 2.0 / kb_scale)
            found[key] = (real_cx, real_cy)

        if len(found) >= 8:
            self._digit_positions = found
        else:
            self._digit_positions = {}

    def _calc_digit_positions(self):
        if not self._kb_region:
            return
        kr = self._kb_region
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]
        cols, rows = 3, 4
        cw, ch = kr["w"] / cols, kr["h"] / rows
        for i, k in enumerate(keys):
            col, row = i % cols, i // cols
            self._digit_positions[k] = (
                int(kr["x"] + cw * (col + 0.5)),
                int(kr["y"] + ch * (row + 0.5)),
            )

    # ==================== 操作 ====================

    def _tap_digits(self, digits):
        if not self._digit_positions:
            print("  [!] 未定位到键盘，无法输入")
            return
        for ch in digits:
            pos = self._digit_positions.get(ch)
            if not pos:
                continue
            jx = max(0, min(self.phone_w - 1, pos[0] + random.randint(-6, 6)))
            jy = max(0, min(self.phone_h - 1, pos[1] + random.randint(-6, 6)))
            try:
                subprocess.run(
                    [ADB_PATH, "-s", self.device.serial, "shell", "input", "tap", str(jx), str(jy)],
                    capture_output=True, timeout=3,
                )
            except Exception:
                pass
            self._sleep(0.015)

    def _draw_compare_symbol(self, q_region, symbol):
        W, H = self.phone_w, self.phone_h
        cx = W // 2 + random.randint(-10, 10)
        top = q_region["y"] + q_region["h"]
        mid_y = (top + int(H * 0.55)) // 2
        cy = max(top + 30, mid_y + random.randint(-10, 10))
        size = max(min(W // 4, 120), 80)

        def j(n):
            return n + random.randint(-6, 6)

        if symbol == ">":
            strokes = [(j(cx - size), j(cy - size), j(cx + size), j(cy)),
                       (j(cx + size), j(cy + 20), j(cx - size), j(cy + size))]
        elif symbol == "<":
            strokes = [(j(cx + size), j(cy - size), j(cx - size), j(cy)),
                       (j(cx - size), j(cy + 20), j(cx + size), j(cy + size))]
        elif symbol == "=":
            strokes = [(j(cx - size), j(cy - size // 3), j(cx + size), j(cy - size // 3)),
                       (j(cx - size), j(cy + size // 3), j(cx + size), j(cy + size // 3))]
        else:
            return

        for sx1, sy1, sx2, sy2 in strokes:
            try:
                subprocess.run(
                    [ADB_PATH, "-s", self.device.serial, "shell", "input", "swipe",
                     str(sx1), str(sy1), str(sx2), str(sy2), str(random.randint(60, 100))],
                    capture_output=True, timeout=3,
                )
            except Exception:
                pass
            time.sleep(0.02)

    # ==================== 调试模式 ====================

    def run_debug_once(self, mode):
        """截一张图，打印分割/识别明细并保存标注图，便于核对识别是否正确。"""
        img = self.screenshot()
        if img is None:
            print("[-] 截图失败")
            return
        os.makedirs(self._debug_dir, exist_ok=True)
        ts = time.strftime("%H%M%S")
        img.save(os.path.join(self._debug_dir, f"raw_{ts}.png"))

        band, oy1, oy2 = self._question_band(img)
        print(f"\n[debug] 题目带 y={oy1}~{oy2}，键盘区域={self._kb_region}")

        upscaled, scale = upscale_band(band)
        print(f"[debug] 题目带放大比例: {scale:.2f}x")

        for step in BIN_METHODS:
            glyphs = self._segment_glyphs(upscaled, step=step)
            print(f"\n[debug] 二值化={step}，分割出 {len(glyphs)} 个字形")
            allowed = set(range(0, 6)) if mode == 2 else set(range(0, 10))
            ann = upscaled.convert("RGB").copy()
            draw = ImageDraw.Draw(ann)
            for idx, (gx1, gy1, gx2, gy2, area, crop) in enumerate(glyphs):
                d = self._classify_glyph(crop, allowed)
                op = None if d is not None else self._classify_operator(crop)
                label = str(d) if d is not None else (op or "?")
                draw.rectangle([gx1, gy1, gx2, gy2], outline=(255, 0, 0), width=2)
                draw.text((gx1, max(0, gy1 - 12)), label, fill=(0, 128, 255))
                real_gx1 = int(gx1 / scale)
                real_gy1 = int(gy1 / scale)
                real_gx2 = int(gx2 / scale)
                real_gy2 = int(gy2 / scale)
                print(f"   #{idx} bbox=({real_gx1},{real_gy1})-({real_gx2},{real_gy2}) area={area} -> {label}")
                crop.save(os.path.join(self._debug_dir, f"glyph_{ts}_{step}_{idx}.png"))
            ann.save(os.path.join(self._debug_dir, f"seg_{ts}_{step}.png"))
            if mode == 2:
                r = self.recognize_compare(img)
                print(f"   => 比较识别结果: {r[:2] if r else None}  detail={r[3] if r else None}")
            else:
                r = self.recognize_expression(img)
                print(f"   => 算式识别结果: {r[:3] if r else None}  detail={r[4] if r else None}")
        print(f"\n[debug] 标注图已保存到: {self._debug_dir}")

    # ==================== 主循环 ====================

    def run_pk_mode(self, max_count=999):
        print("\n" + "=" * 58)
        print("  PK 口算自动答题（字形分割版 / 无投票）")
        print("=" * 58)
        print(f"  分辨率: {self.phone_w}x{self.phone_h}")
        print("  Otsu 自动阈值 + 连通域分割 + 单字符识别 + 结构校验")
        print("=" * 58)
        print("\n请确保手机已停在 PK 答题界面（能看到算式和数字键盘）")
        input("按回车开始...")

        self.running = True
        count = 0
        done = 0
        fail_count = 0
        kb_setup = False
        last_expr = None
        answer_cooldown_until = 0
        # 二次确认缓存：新算式必须连续识别到两次一致才真正答
        pending_confirm_expr = None
        pending_confirm_count = 0

        try:
            while self.running and count < max_count:
                count += 1
                if not self.ensure_device():
                    self._sleep(0.3)
                    count -= 1
                    continue

                t0 = time.perf_counter()
                img = self.screenshot()
                if img is None:
                    self._sleep(0.1)
                    count -= 1
                    continue

                if not kb_setup:
                    self._find_and_setup_keyboard(img)
                    kb_setup = True
                    self._kb_setup_done = True
                    print(f"  [键盘] 区域={self._kb_region}")
                    print(f"  [键盘] 按键={self._digit_positions}")

                # 冷却期内跳过——答完一题后界面需要稳定时间
                if time.time() < answer_cooldown_until:
                    self._sleep(0.03)
                    count -= 1
                    continue

                r = self.recognize_expression(img)
                if r is None:
                    fail_count += 1
                    if fail_count >= 5:
                        print(f"[{count}] 连续 {fail_count} 次未识别到算式（可能不在答题界面）")
                        try:
                            img.save(os.path.join(SCRIPT_DIR, "debug_scan_fail.png"))
                        except Exception:
                            pass
                        fail_count = 0
                        time.sleep(0.3)
                    else:
                        time.sleep(0.05)
                    count -= 1
                    continue

                a, op, b, oy1, detail = r
                fail_count = 0
                expr = f"{a}{op}{b}"

                # 同一算式：二次确认机制
                if expr == last_expr:
                    # 已经答过这个算式，跳过
                    self._sleep(0.02)
                    count -= 1
                    continue

                if expr == pending_confirm_expr:
                    pending_confirm_count += 1
                else:
                    pending_confirm_expr = expr
                    pending_confirm_count = 1

                # 连续识别到 N 次一致才算真正确认新题目
                need_confirm = 2
                if pending_confirm_count < need_confirm:
                    # 还没确认够次数，等待下一帧再看
                    self._sleep(0.04)
                    count -= 1
                    continue

                # 确认通过，清除确认缓存（下次识别到相同算式也会走上面的"已答过"分支）
                pending_confirm_expr = None
                pending_confirm_count = 0

                answer = self._compute(a, op, b)
                if answer is None:
                    print(f"[{count}] {expr}=? 无法计算，跳过")
                    last_expr = expr
                    answer_cooldown_until = time.time() + max(0.3, 0.6 / self.speed)
                    count -= 1
                    continue

                self._tap_digits(str(answer))
                done += 1
                elapsed = (time.perf_counter() - t0) * 1000
                print(f"[{done}] {expr}={answer}  [{elapsed:.0f}ms]  (预处理={detail['step']})")

                last_expr = expr
                # 答完一题后强制等待界面稳定（给 0.4 ~ 0.7 秒让 APP 切换 + 渲染下一题）
                answer_cooldown_until = time.time() + max(0.4, 0.7 / self.speed)

        except KeyboardInterrupt:
            print(f"\n[!] 已停止，共完成 {done} 题")
        finally:
            self.running = False

    def run_compare_mode(self, max_count=999):
        print("\n" + "=" * 58)
        print("  比较大小自动答题（字形分割版 / 无投票）")
        print("=" * 58)
        print(f"  分辨率: {self.phone_w}x{self.phone_h}")
        print(f"  数字范围 {COMPARE_MIN}-{COMPARE_MAX}，左右由空间位置判定")
        print("=" * 58)
        print("\n请确保手机已停在比较大小答题界面")
        input("按回车开始...")

        self.running = True
        count = 0
        done = 0
        fail_count = 0
        kb_setup = False
        last_pair = None
        answer_cooldown_until = 0
        pending_confirm_pair = None
        pending_confirm_count = 0

        try:
            while self.running and count < max_count:
                count += 1
                if not self.ensure_device():
                    self._sleep(0.3)
                    count -= 1
                    continue

                t0 = time.perf_counter()
                img = self.screenshot()
                if img is None:
                    self._sleep(0.1)
                    count -= 1
                    continue

                if not kb_setup:
                    self._find_and_setup_keyboard(img)
                    kb_setup = True
                    print(f"  [键盘] 区域={self._kb_region}")

                # 冷却期内跳过
                if time.time() < answer_cooldown_until:
                    self._sleep(0.03)
                    count -= 1
                    continue

                r = self.recognize_compare(img)
                if r is None:
                    fail_count += 1
                    if fail_count >= 5:
                        print(f"[{count}] 连续 {fail_count} 次未识别到题目（可能不在答题界面）")
                        try:
                            img.save(os.path.join(SCRIPT_DIR, "debug_scan_fail.png"))
                        except Exception:
                            pass
                        fail_count = 0
                        time.sleep(0.3)
                    else:
                        time.sleep(0.05)
                    count -= 1
                    continue

                left, right, oy1, detail = r
                fail_count = 0
                pair = (left, right)

                # 已经答过这对数字
                if pair == last_pair:
                    self._sleep(0.02)
                    count -= 1
                    continue

                if pair == pending_confirm_pair:
                    pending_confirm_count += 1
                else:
                    pending_confirm_pair = pair
                    pending_confirm_count = 1

                need_confirm = 2
                if pending_confirm_count < need_confirm:
                    self._sleep(0.04)
                    count -= 1
                    continue

                pending_confirm_pair = None
                pending_confirm_count = 0

                symbol = ">" if left > right else ("<" if left < right else "=")
                q_region = {"y": oy1, "h": int(self.phone_h * 0.12)}
                self._draw_compare_symbol(q_region, symbol)

                done += 1
                elapsed = (time.perf_counter() - t0) * 1000
                print(f"[{done}] {left} {symbol} {right}  [{elapsed:.0f}ms]  (预处理={detail['step']})")

                last_pair = pair
                # 答完后等待界面稳定
                answer_cooldown_until = time.time() + max(0.4, 0.7 / self.speed)

        except KeyboardInterrupt:
            print(f"\n[!] 已停止，共完成 {done} 题")
        finally:
            self.running = False

    def close(self):
        self.running = False



# =============================================
# 抓包（mitmdump + adb 代理）
# =============================================
class PacketCapture:
    ADDON_CODE = "import json, os, time\n\nclass FlowLogger:\n    def __init__(self):\n        self.count = 0\n        self.fpath = os.environ.get('MITM_JSONL', 'flows.jsonl')\n        self.f = open(self.fpath, 'a', encoding='utf-8')\n        self.t0 = time.time()\n    def response(self, flow):\n        try:\n            self.count += 1\n            req = flow.request\n            resp = flow.response\n            e = {\n                't': round(time.time() - self.t0, 3),\n                'method': req.method,\n                'host': req.pretty_host,\n                'port': req.port,\n                'path': req.path.split('?')[0][:120],\n                'query_keys': list(req.query.keys())[:12] if hasattr(req, 'query') and req.query else [],\n                'status': resp.status_code if resp else 0,\n                'scheme': req.scheme,\n                'req_len': len(req.raw_content) if req.raw_content else 0,\n                'resp_len': len(resp.raw_content) if resp and resp.raw_content else 0,\n                'content_type': (resp.headers.get('content-type', '') if resp and resp.headers else '').split(';')[0][:60],\n            }\n            self.f.write(json.dumps(e, ensure_ascii=False) + '\\n')\n            self.f.flush()\n        except Exception:\n            pass\n\naddons = [FlowLogger()]\n"

    def __init__(self, adb_path, device_serial=None):
        self.adb_path = adb_path
        self.serial = device_serial
        self.proc = None
        self.port = None
        self.capture_dir = None
        self.jsonl_path = None
        self.mitm_path = None
        self.addon_tmp = None

    def _adb(self, args):
        serial_args = ['-s', self.serial] if self.serial else []
        try:
            subprocess.run(
                [self.adb_path] + serial_args + args,
                capture_output=True, timeout=3,
            )
        except Exception:
            pass

    def start(self, port=8089, capture_dir=None):
        if self.proc is not None:
            return False
        if capture_dir is None:
            capture_dir = os.path.join(SCRIPT_DIR, 'capture')
        os.makedirs(capture_dir, exist_ok=True)
        self.capture_dir = capture_dir

        ts = time.strftime('%H%M%S')
        self.jsonl_path = os.path.join(capture_dir, f'flows_{ts}.jsonl')
        self.mitm_path = os.path.join(capture_dir, f'raw_{ts}.mitm')

        import tempfile
        self.addon_tmp = tempfile.NamedTemporaryFile(
            suffix='.py', delete=False, mode='w', encoding='utf-8'
        )
        self.addon_tmp.write(self.ADDON_CODE)
        self.addon_tmp.close()

        env = os.environ.copy()
        env['MITM_JSONL'] = self.jsonl_path
        try:
            self.proc = subprocess.Popen(
                ['mitmdump', '-p', str(port),
                 '--set', 'block_global=false',
                 '--anticomp', '-w', self.mitm_path,
                 '-s', self.addon_tmp.name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env,
            )
        except FileNotFoundError:
            print('[-] 未找到 mitmdump，请先安装: pip install mitmproxy')
            self.proc = None
            return False
        except Exception as ex:
            print(f'[-] mitmdump 启动失败: {ex}')
            self.proc = None
            return False

        time.sleep(2)
        if self.proc.poll() is not None:
            print('[-] mitmdump 启动后立即退出（端口可能被占用）')
            self.proc = None
            self._cleanup_tmp()
            return False

        self.port = port
        self._adb(['shell', 'settings', 'put', 'global', 'http_proxy', f'127.0.0.1:{port}'])
        print(f'[+] 抓包已启动：port={port}')
        print(f'    JSONL: {self.jsonl_path}')
        print(f'    原始:  {self.mitm_path}')
        print('[!] HTTPS 需在手机安装 mitmproxy 证书才能解密（否则仅看到连接目标）')
        return True

    def _cleanup_tmp(self):
        if self.addon_tmp and os.path.exists(self.addon_tmp.name):
            try:
                os.unlink(self.addon_tmp.name)
            except Exception:
                pass
        self.addon_tmp = None

    def stop(self):
        self._adb(['shell', 'settings', 'put', 'global', 'http_proxy', ':0'])
        if self.proc is not None:
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except Exception:
                    self.proc.kill()
            except Exception:
                pass
            self.proc = None
        self._cleanup_tmp()

    def parse_and_report(self):
        if not self.jsonl_path or not os.path.exists(self.jsonl_path):
            return
        import json as _json
        from collections import Counter

        flows = []
        try:
            with open(self.jsonl_path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            flows.append(_json.loads(line))
                        except Exception:
                            pass
        except Exception:
            return

        if not flows:
            return

        print(f'\n{"=" * 58}')
        print(f'  抓包报告：{len(flows)} 条流量')
        print(f'{"=" * 58}')

        host_counts = Counter(f['host'] for f in flows)
        print('\n-- 域名 TOP --')
        for host, cnt in host_counts.most_common(20):
            bar = '#' * min(40, cnt)
            print(f'  {cnt:4d}x  {host:<32} {bar}')

        total_resp = sum(f.get('resp_len', 0) for f in flows)
        total_req = sum(f.get('req_len', 0) for f in flows)
        print(f'\n  请求总大小: {total_req:,} bytes')
        print(f'  响应总大小: {total_resp:,} bytes')
        print(f'  流量总大小: {total_req + total_resp:,} bytes')

        print('\n-- 详细流量 --')
        hdr = f"  {'t(s)':>7}  {'m':4}  {'host':26}  {'path':36}  {'st':>4}  {'resp':>8}  {'type':20}"
        print(hdr)
        print('  ' + '-' * (len(hdr) - 2))
        for f in flows:
            path = (f.get('path') or '')[:36]
            ct = (f.get('content_type') or '')[:20]
            print(f"  {f.get('t',0):7.2f}  {f.get('method',''):4}  {f.get('host',''):26}  {path:36}  {f.get('status',0):>4}  {f.get('resp_len',0):>8}  {ct:20}")

        print(f'\n原始流量(.mitm): {self.mitm_path}')
        print(f'JSON 摘要(.jsonl): {self.jsonl_path}')

def main():
    debug_mode = "--debug" in sys.argv

    if not ensure_adb():
        return

    auto = XiaoYuanAuto()
    auto.debug = debug_mode
    if not auto.connect_device():
        return

    print("\n" + "=" * 58)
    print("  小猿口算自动答题 - 模式选择")
    print("=" * 58)
    print("  1. PK 口算（加减乘除，点数字键盘）")
    print("  2. 比较大小（画 > < =）")
    print("=" * 58)

    if debug_mode:
        mode = "2"
        for a in sys.argv:
            if a.startswith("--mode="):
                mode = a.split("=", 1)[1].strip()
        print(f"[debug] 模式={mode}，只截图分析一次，不做任何点击")
        try:
            auto._find_and_setup_keyboard(auto.screenshot())
        except Exception:
            pass
        auto.run_debug_once(int(mode) if mode.isdigit() else 2)
        return

    mode = input("请选择 [1/2]: ").strip()
    if mode not in ("1", "2"):
        print("无效选择")
        return

    print("\n-- 抓包设置 --")
    print("  1. 不抓包（默认）")
    print("  2. 开启抓包（mitmproxy 代理，PC 需已安装 mitmproxy）")
    cap_choice = input("选择 [1-2，直接回车=不抓包]: ").strip()
    capturer = None
    if cap_choice == "2":
        try:
            capturer = PacketCapture(ADB_PATH, auto.device_serial)
            if not capturer.start():
                capturer = None
        except Exception as ex:
            print(f"[-] 抓包初始化失败: {ex}")
            capturer = None

    print("\n-- 速度设置 --")

    print("  1. 正常 (默认，稳妥)")
    print("  2. 较快 (约 1.5x)")
    print("  3. 快速 (约 2x)")
    print("  4. 极速 (约 4x)")
    speed_choice = input("选择 [1-4，直接回车=正常]: ").strip()
    speed_map = {"1": 1.0, "2": 1.5, "3": 2.0, "4": 4.0}
    auto.speed = speed_map.get(speed_choice, 1.0)
    print(f"[+] 速度倍率: {auto.speed}x")

    try:
        if mode == "1":
            auto.run_pk_mode()
        else:
            auto.run_compare_mode()
    except Exception as e:
        print(f"[-] 出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        auto.close()
        if capturer is not None:
            capturer.stop()
            capturer.parse_and_report()


if __name__ == "__main__":
    main()