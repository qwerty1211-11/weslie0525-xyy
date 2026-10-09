#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小猿口算 PK赛 自动答题助手
功能：ADB截图 → OCR识别数字 → 比较大小 → ADB手写 > < 符号
作者：AutoSolver
依赖：adb, pytesseract, opencv-python, pillow, numpy
"""

import subprocess
import time
import re
import os
import sys
import random
import cv2
import numpy as np
import pytesseract
from PIL import Image
random.randint(0,30)


# ============================================================
#  配置区域（根据你的手机和题目位置修改）
# ============================================================

# ADB 路径（Windows 填完整路径，如 r'C:\platform-tools\adb.exe'；Mac/Linux 填 'adb'）
ADB_PATH = 'adb'

# 手机屏幕分辨率（你的VIVO是 720×1600）
SCREEN_WIDTH = 720
SCREEN_HEIGHT = 1600

# 题目区域坐标 (x, y, width, height) —— 框住 "数字 ? 数字" 那一行
QUESTION_REGION = {
    'x': 100,
    'y': 420,
    'width': 520,
    'height': 180
}

# 手写答题区中心坐标（符号画在这个点周围）
ANSWER_CENTER = {
    'x': 360,
    'y': 1150
}

# 符号大小（从中心到端点的距离，单位像素）
SYMBOL_HALF_SIZE = 80

# 每段滑动的持续时间（毫秒），建议 120~200
SWIPE_DURATION = 150

# 两段滑动之间的间隔（秒）
SWIPE_GAP = 0.05

# 每题之间等待时间（秒），等下一题刷新
QUESTION_INTERVAL = 0.8

# 随机延迟范围（秒），防检测：在基础等待上加减随机值
RANDOM_DELAY_RANGE = 0.15

# OCR 配置（Windows 需要指定 tesseract.exe 路径）
TESSERACT_CMD = None  # 例如 r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 调试模式：保存每一步截图
DEBUG = False

# ============================================================
#  ADB 工具模块
# ============================================================

def adb_run(cmd, timeout=10):
    """执行一条 ADB 命令，返回输出"""
    full_cmd = [ADB_PATH] + cmd.split()
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"  [ADB] 命令超时: {cmd}")
        return ""
    except FileNotFoundError:
        print(f"  [ADB] 找不到 adb，请检查 ADB_PATH 配置: {ADB_PATH}")
        sys.exit(1)


def adb_swipe(x1, y1, x2, y2, duration=SWIPE_DURATION):
    """模拟滑动"""
    adb_run(f'shell input swipe {x1} {y1} {x2} {y2} {duration}')


def adb_tap(x, y):
    """模拟点击"""
    adb_run(f'shell input tap {x} {y}')


def capture_screen(save_path='screen.png'):
    """ADB 截图并拉取到电脑"""
    adb_run('shell screencap -p /sdcard/auto_solver_screen.png')
    adb_run(f'pull /sdcard/auto_solver_screen.png {save_path}')
    if os.path.exists(save_path):
        return Image.open(save_path)
    return None


# ============================================================
#  图像预处理 & OCR
# ============================================================

def setup_tesseract():
    """配置 Tesseract"""
    if TESSERACT_CMD and os.path.exists(TESSERACT_CMD):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def preprocess_for_ocr(pil_image):
    """图像预处理，提高数字识别率"""
    img_cv = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    # 自适应二值化，应对不同背景
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2
    )
    # 膨胀让数字连起来
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(binary, kernel, iterations=1)
    return Image.fromarray(cv2.bitwise_not(dilated))


def extract_numbers(pil_image):
    """
    从题目区域截图中提取两个数字
    返回 (num1, num2)，失败返回 (None, None)
    """
    # 裁剪题目区域
    region = pil_image.crop((
        QUESTION_REGION['x'],
        QUESTION_REGION['y'],
        QUESTION_REGION['x'] + QUESTION_REGION['width'],
        QUESTION_REGION['y'] + QUESTION_REGION['height']
    ))

    if DEBUG:
        region.save('debug_question.png')

    # 预处理
    processed = preprocess_for_ocr(region)

    # OCR 识别（psm 6 = 假设为统一文本块，支持多行）
    config = '--psm 6 -c tessedit_char_whitelist=0123456789'
    text = pytesseract.image_to_string(processed, config=config)
    print(f"  [OCR] 原始识别: {text.strip()}")

    # 提取所有数字
    numbers = re.findall(r'\d+', text)

    if len(numbers) >= 2:
        return int(numbers[0]), int(numbers[1])

    # 备用方案：psm 7 单行
    config2 = '--psm 7 -c tessedit_char_whitelist=0123456789'
    text2 = pytesseract.image_to_string(processed, config=config2)
    numbers2 = re.findall(r'\d+', text2)
    if len(numbers2) >= 2:
        return int(numbers2[0]), int(numbers2[1])

    print(f"  [OCR] 只识别到数字: {numbers if numbers else numbers2}")
    return None, None


# ============================================================
#  手写符号模块（画 > < =）
# ============================================================

def draw_greater_than():
    """手写 > 号：左上 → 中心 → 右下"""
    cx, cy = ANSWER_CENTER['x'], ANSWER_CENTER['y']
    s = SYMBOL_HALF_SIZE
    # 微小随机偏移，防检测
    jitter = lambda: random.randint(-3, 3)

    adb_swipe(cx - s + jitter(), cy - s + jitter(), cx + jitter(), cy + jitter())
    time.sleep(SWIPE_GAP)
    adb_swipe(cx + jitter(), cy + jitter(), cx + s + jitter(), cy + s + jitter())
    print("  [绘制] > 号")


def draw_less_than():
    """手写 < 号：右上 → 中心 → 左下"""
    cx, cy = ANSWER_CENTER['x'], ANSWER_CENTER['y']
    s = SYMBOL_HALF_SIZE
    jitter = lambda: random.randint(-3, 3)

    adb_swipe(cx + s + jitter(), cy - s + jitter(), cx + jitter(), cy + jitter())
    time.sleep(SWIPE_GAP)
    adb_swipe(cx + jitter(), cy + jitter(), cx - s + jitter(), cy + s + jitter())
    print("  [绘制] < 号")


def draw_equal():
    """手写 = 号：两条横线"""
    cx, cy = ANSWER_CENTER['x'], ANSWER_CENTER['y']
    s = SYMBOL_HALF_SIZE
    jitter = lambda: random.randint(-3, 3)

    # 上横线
    adb_swipe(cx - s + jitter(), cy - 20 + jitter(), cx + s + jitter(), cy - 20 + jitter())
    time.sleep(SWIPE_GAP)
    # 下横线
    adb_swipe(cx - s + jitter(), cy + 20 + jitter(), cx + s + jitter(), cy + 20 + jitter())
    print("  [绘制] = 号")


def draw_answer(num1, num2):
    """根据比较结果画对应符号"""
    if num1 > num2:
        draw_greater_than()
        return ">"
    elif num1 < num2:
        draw_less_than()
        return "<"
    else:
        draw_equal()
        return "="


# ============================================================
#  弹窗处理（奖励/结算弹窗自动关闭）
# ============================================================

# 常见弹窗按钮坐标（720×1600）
POPUP_BUTTONS = {
    '开心收下': (360, 1250),
    '继续': (360, 1450),
    '炫耀一下': (200, 1450),
    '关闭X': (660, 100),
}


def try_close_popup():
    """尝试关闭可能出现的弹窗（简单策略：依次点常见按钮）"""
    # 优先点"继续"或"开心收下"
    for name, (x, y) in POPUP_BUTTONS.items():
        adb_tap(x, y)
        time.sleep(0.3)


# ============================================================
#  主循环
# ============================================================

def random_sleep(base):
    """带随机抖动的等待"""
    delay = base + random.uniform(-RANDOM_DELAY_RANGE, RANDOM_DELAY_RANGE)
    delay = max(0.1, delay)
    time.sleep(delay)


def run_auto_solver(max_questions=0):
    """
    主循环
    max_questions: 最多答多少题，0=无限
    """
    print("=" * 55)
    print("   小猿口算 PK赛 自动答题助手")
    print("=" * 55)
    print(f"  屏幕分辨率: {SCREEN_WIDTH}×{SCREEN_HEIGHT}")
    print(f"  题目区域:   x={QUESTION_REGION['x']} y={QUESTION_REGION['y']} "
          f"{QUESTION_REGION['width']}×{QUESTION_REGION['height']}")
    print(f"  手写中心:   ({ANSWER_CENTER['x']}, {ANSWER_CENTER['y']})")
    print(f"  符号大小:   {SYMBOL_HALF_SIZE * 2}px")
    print(f"  调试模式:   {'开' if DEBUG else '关'}")
    print("=" * 55)

    # 检查 ADB 连接
    devices = adb_run('devices')
    if 'device' not in devices.lower() or len(devices.strip().split('\n')) < 2:
        print("\n[错误] 未检测到手机设备！")
        print("请检查：")
        print("  1. 手机已通过USB连接电脑")
        print("  2. 手机已开启USB调试")
        print("  3. 手机弹窗已点击'允许USB调试'")
        print(f"  4. ADB路径正确: {ADB_PATH}")
        return

    print(f"\n[ADB] 设备已连接:\n{devices}")
    setup_tesseract()

    input("\n按 Enter 开始答题（Ctrl+C 停止）...")

    count = 0
    correct = 0

    try:
        while True:
            count += 1
            print(f"\n--- 第 {count} 题 ---")

            # 1. 截图
            screen = capture_screen()
            if screen is None:
                print("  [错误] 截图失败，跳过")
                random_sleep(0.5)
                continue

            if DEBUG:
                screen.save(f'debug_screen_{count}.png')

            # 2. 识别数字
            num1, num2 = extract_numbers(screen)
            if num1 is None or num2 is None:
                print("  [跳过] 数字识别失败，可能是弹窗或加载中")
                try_close_popup()
                random_sleep(0.5)
                count -= 1
                continue

            print(f"  [题目] {num1} ? {num2}")

            # 3. 比较并画符号
            symbol = draw_answer(num1, num2)
            correct += 1
            print(f"  [答案] {num1} {symbol} {num2}")

            # 4. 达到上限则退出
            if max_questions > 0 and count >= max_questions:
                print(f"\n已完成 {max_questions} 题，退出")
                break

            # 5. 等下一题
            random_sleep(QUESTION_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n\n[中断] 用户停止，共处理 {count} 题，识别成功 {correct} 题")
    finally:
        print("程序结束")


# ============================================================
#  测试 & 工具函数
# ============================================================

def test_capture():
    """测试截图功能"""
    print("[测试] 截取屏幕...")
    screen = capture_screen('test_screen.png')
    if screen:
        print(f"  截图成功: {screen.size}")
        # 裁剪题目区域保存
        region = screen.crop((
            QUESTION_REGION['x'], QUESTION_REGION['y'],
            QUESTION_REGION['x'] + QUESTION_REGION['width'],
            QUESTION_REGION['y'] + QUESTION_REGION['height']
        ))
        region.save('test_question.png')
        print("  题目区域已保存为 test_question.png，请检查是否框住题目")
    else:
        print("  截图失败")


def test_draw():
    """测试手写符号（在手机上画一个 > 号）"""
    print("[测试] 在手机上画 > 号...")
    draw_greater_than()
    time.sleep(1)
    print("[测试] 画 < 号...")
    draw_less_than()
    print("请查看手机上符号是否清晰、在答题框内")


def test_ocr():
    """测试 OCR 识别"""
    print("[测试] 截图并识别...")
    setup_tesseract()
    screen = capture_screen()
    if screen:
        num1, num2 = extract_numbers(screen)
        if num1 is not None:
            print(f"  识别成功: {num1}, {num2}")
        else:
            print("  识别失败，请检查 QUESTION_REGION 坐标")


def show_coordinates():
    """显示当前所有配置坐标"""
    print("\n" + "=" * 40)
    print("  当前坐标配置")
    print("=" * 40)
    print(f"  题目区域:")
    print(f"    左上角: ({QUESTION_REGION['x']}, {QUESTION_REGION['y']})")
    print(f"    右下角: ({QUESTION_REGION['x'] + QUESTION_REGION['width']}, "
          f"{QUESTION_REGION['y'] + QUESTION_REGION['height']})")
    print(f"    尺寸: {QUESTION_REGION['width']}×{QUESTION_REGION['height']}")
    print(f"  手写中心: ({ANSWER_CENTER['x']}, {ANSWER_CENTER['y']})")
    print(f"  符号范围: ({ANSWER_CENTER['x'] - SYMBOL_HALF_SIZE}, "
          f"{ANSWER_CENTER['y'] - SYMBOL_HALF_SIZE}) ~ "
          f"({ANSWER_CENTER['x'] + SYMBOL_HALF_SIZE}, "
          f"{ANSWER_CENTER['y'] + SYMBOL_HALF_SIZE})")
    print("=" * 40)


# ============================================================
#  程序入口
# ============================================================

if __name__ == '__main__':
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == '--test-capture':
            test_capture()
        elif arg == '--test-draw':
            test_draw()
        elif arg == '--test-ocr':
            test_ocr()
        elif arg == '--coords':
            show_coordinates()
        elif arg == '--debug':
            DEBUG = True
            run_auto_solver()
        elif arg == '--help':
            print("用法:")
            print("  python xiaoyuan_auto_solver.py           开始自动答题")
            print("  python xiaoyuan_auto_solver.py --test-capture  测试截图")
            print("  python xiaoyuan_auto_solver.py --test-draw     测试画符号")
            print("  python xiaoyuan_auto_solver.py --test-ocr      测试OCR识别")
            print("  python xiaoyuan_auto_solver.py --coords        显示坐标配置")
            print("  python xiaoyuan_auto_solver.py --debug         调试模式运行")
        else:
            print(f"未知参数: {arg}，使用 --help 查看帮助")
    else:
        run_auto_solver()
