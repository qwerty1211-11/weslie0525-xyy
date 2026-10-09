#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动答题助手 - 数学比较题自动识别与填写
功能：自动识别屏幕上的数学比较题（如 5 > 3），计算答案并自动填写 > 或 <
作者：Inscode AI
"""

import cv2
import numpy as np
import pyautogui
import pytesseract
from PIL import Image
import time
import re
import os
import random
# ==================== 配置区域 ====================
# ⚠️ 重要：请根据您的屏幕分辨率和题目位置修改以下坐标！

# 题目区域坐标 (左上角x, 左上角y, 宽度, 高度)
# 示例：假设题目显示在屏幕 (100, 200) 位置，宽度400像素，高度50像素
QUESTION_REGION = {
    'x': 1667,
    'y': 735,
    'width': 880,
    'height': 320
}

# 答案填写区域坐标 (答案框的中心点坐标)
ANSWER_POSITION = {
    'x': 1685,
    'y': 1478
}

# OCR 配置
# Windows 用户需要指定 Tesseract 安装路径
# 例如: pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Linux/Mac 用户如果已安装到系统路径，可以注释掉下面这行
TESSERACT_PATH = None  # 设置为 None 表示使用系统默认路径

# 操作延时（秒）
DELAY_BETWEEN_ACTIONS = 0.5
DELAY_BEFORE_CAPTURE = 1.0

# 连续答题数量（设置为0表示无限循环，按 Ctrl+C 退出）
MAX_QUESTIONS = 0
random.randint(0,9)
time.sleep(DELAY_BEFORE_CAPTURE)
time.sleep(random.randint(0,9))
# ==================== 核心功能模块 ====================

def setup_tesseract():
    """配置 Tesseract OCR 路径"""
    if TESSERACT_PATH and os.path.exists(TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
        print(f"✓ Tesseract 路径已设置: {TESSERACT_PATH}")
    else:
        print("✓ 使用系统默认 Tesseract 路径")


def capture_region(x, y, width, height):
    """
    截取屏幕指定区域的图片

    参数:
        x: 左上角 x 坐标
        y: 左上角 y 坐标
        width: 区域宽度
        height: 区域高度

    返回:
        PIL.Image 对象
    """
    try:
        # 使用 pyautogui 截取全屏，然后裁剪
        screenshot = pyautogui.screenshot()
        region = screenshot.crop((x, y, x + width, y + height))
        return region
    except Exception as e:
        print(f"✗ 截图失败: {e}")
        return None


def preprocess_image(image):
    """
    图像预处理，提高 OCR 识别准确率

    参数:
        image: PIL.Image 对象

    返回:
        处理后的 OpenCV 图像
    """
    # 转换为 OpenCV 格式
    img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    # 转换为灰度图
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

    # 二值化处理
    _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

    # 反转颜色（白底黑字更适合 OCR）
    inverted = cv2.bitwise_not(binary)

    # 膨胀操作，使数字更清晰
    kernel = np.ones((2, 2), np.uint8)
    dilated = cv2.dilate(inverted, kernel, iterations=1)

    return dilated


def extract_numbers(image):
    """
    从图像中提取数字

    参数:
        image: PIL.Image 对象

    返回:
        (num1, num2) 元组，如果识别失败返回 (None, None)
    """
    try:
        # 图像预处理
        processed = preprocess_image(image)

        # 转换回 PIL 格式进行 OCR
        pil_image = Image.fromarray(processed)

        # 使用 Tesseract 进行 OCR 识别
        # --psm 7 表示将图像视为单行文本
        config = '--psm 7 -c tessedit_char_whitelist=0123456789.<>'
        text = pytesseract.image_to_string(pil_image, config=config)

        print(f"  OCR 识别结果: {text.strip()}")

        # 提取数字
        numbers = re.findall(r'\d+', text)

        if len(numbers) >= 2:
            num1 = int(numbers[0])
            num2 = int(numbers[1])
            return num1, num2
        else:
            print(f"✗ 未能识别到两个数字，识别到: {numbers}")
            return None, None

    except Exception as e:
        print(f"✗ OCR 识别失败: {e}")
        return None, None


def extract_numbers_advanced(image):
    """
    高级数字提取方法：分割图像后分别识别

    参数:
        image: PIL.Image 对象

    返回:
        (num1, num2) 元组
    """
    try:
        # 转换为 OpenCV 格式
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

        # 二值化
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # 查找轮廓
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 按x坐标排序轮廓
        bounding_boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w > 5 and h > 10:  # 过滤太小的区域
                bounding_boxes.append((x, y, w, h))

        bounding_boxes.sort(key=lambda b: b[0])

        # 提取数字区域
        numbers = []
        for box in bounding_boxes[:5]:  # 最多取前5个区域
            x, y, w, h = box
            region = binary[y:y + h, x:x + w]

            # OCR 识别单个区域
            pil_region = Image.fromarray(cv2.bitwise_not(region))
            config = '--psm 10 -c tessedit_char_whitelist=0123456789'
            text = pytesseract.image_to_string(pil_region, config=config)
            text = text.strip()

            if text.isdigit():
                numbers.append(int(text))

        if len(numbers) >= 2:
            return numbers[0], numbers[1]
        else:
            return None, None

    except Exception as e:
        print(f"✗ 高级识别失败: {e}")
        return None, None


def compare_numbers(num1, num2):
    """
    比较两个数字大小

    参数:
        num1: 第一个数字
        num2: 第二个数字

    返回:
        ">" 或 "<" 字符串
    """
    if num1 > num2:
        return ">"
    elif num1 < num2:
        return "<"
    else:
        return "="


def move_and_type(x, y, text):
    """
    移动鼠标到指定位置并输入文本

    参数:
        x: 目标 x 坐标
        y: 目标 y 坐标
        text: 要输入的文本
    """
    try:
        # 移动鼠标
        pyautogui.moveTo(x, y, duration=0.3)
        time.sleep(0.2)

        # 点击目标位置
        pyautogui.click()
        time.sleep(0.2)

        # 输入答案
        pyautogui.write(text, interval=0.1)

        print(f"✓ 已在 ({x}, {y}) 输入: {text}")

    except Exception as e:
        print(f"✗ 输入失败: {e}")


def get_mouse_position():
    """
    获取当前鼠标位置（用于配置坐标）
    """
    print("\n=== 鼠标位置获取工具 ===")
    print("将鼠标移动到目标位置，然后查看控制台输出...")
    print("按 Ctrl+C 退出\n")

    try:
        while True:
            x, y = pyautogui.position()
            print(f"\r当前鼠标位置: ({x}, {y})    ", end='', flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n已退出位置获取工具")


def run_auto_solver():
    """
    主运行函数：自动答题主循环
    """
    print("\n" + "=" * 50)
    print("    自动答题助手 - 数学比较题")
    print("=" * 50)

    # 配置 Tesseract
    setup_tesseract()

    # 显示当前配置
    print(f"\n当前配置:")
    print(f"  题目区域: ({QUESTION_REGION['x']}, {QUESTION_REGION['y']}) "
          f"大小: {QUESTION_REGION['width']}x{QUESTION_REGION['height']}")
    print(f"  答案位置: ({ANSWER_POSITION['x']}, {ANSWER_POSITION['y']})")
    print(f"  操作延时: {DELAY_BETWEEN_ACTIONS} 秒")

    print("\n⚠️ 请确保:")
    print("  1. 题目区域坐标已正确配置")
    print("  2. 屏幕上的题目清晰可见，无遮挡")
    print("  3. Tesseract-OCR 已正确安装")

    input("\n按 Enter 键开始运行，按 Ctrl+C 退出...")

    question_count = 0

    try:
        while True:
            question_count += 1
            print(f"\n{'=' * 40}")
            print(f"第 {question_count} 题")
            print(f"{'=' * 40}")

            # 等待一下，确保屏幕稳定
            time.sleep(DELAY_BEFORE_CAPTURE)

            # 截取题目区域
            print("→ 正在截取题目区域...")
            question_image = capture_region(
                QUESTION_REGION['x'],
                QUESTION_REGION['y'],
                QUESTION_REGION['width'],
                QUESTION_REGION['height']
            )

            if question_image is None:
                print("✗ 截图失败，跳过本题")
                continue

            # 保存截图（调试用）
            debug_path = f"debug_question_{question_count}.png"
            question_image.save(debug_path)
            print(f"  截图已保存: {debug_path}")

            # 识别数字
            print("→ 正在识别数字...")
            num1, num2 = extract_numbers(question_image)

            # 如果第一种方法失败，尝试高级方法
            if num1 is None or num2 is None:
                print("  尝试高级识别方法...")
                num1, num2 = extract_numbers_advanced(question_image)

            if num1 is None or num2 is None:
                print("✗ 数字识别失败，跳过本题")
                print("  提示: 请检查截图 debug_question_*.png 确认题目是否清晰")
                continue

            print(f"✓ 识别结果: {num1} ? {num2}")

            # 比较大小
            answer = compare_numbers(num1, num2)
            print(f"✓ 答案: {num1} {answer} {num2}")

            # 填写答案
            print("→ 正在填写答案...")
            move_and_type(ANSWER_POSITION['x'], ANSWER_POSITION['y'], answer)

            # 检查是否达到最大题数
            if MAX_QUESTIONS > 0 and question_count >= MAX_QUESTIONS:
                print(f"\n已完成 {MAX_QUESTIONS} 题，程序结束")
                break

            # 等待下一题
            time.sleep(DELAY_BETWEEN_ACTIONS)

    except KeyboardInterrupt:
        print(f"\n\n用户中断，已处理 {question_count - 1} 题")

    print("\n程序结束")


def test_ocr():
    """
    测试 OCR 功能是否正常
    """
    print("\n=== OCR 功能测试 ===\n")

    # 配置 Tesseract
    setup_tesseract()

    # 截取测试区域
    print("→ 正在截取屏幕区域进行测试...")
    test_image = capture_region(
        QUESTION_REGION['x'],
        QUESTION_REGION['y'],
        QUESTION_REGION['width'],
        QUESTION_REGION['height']
    )

    if test_image:
        test_image.save("test_ocr.png")
        print("✓ 测试截图已保存: test_ocr.png")

        # 尝试识别
        num1, num2 = extract_numbers(test_image)

        if num1 and num2:
            print(f"✓ OCR 测试成功! 识别到: {num1}, {num2}")
        else:
            print("✗ OCR 未能识别数字，请检查:")
            print("  1. Tesseract-OCR 是否正确安装")
            print("  2. 题目区域坐标是否正确")
            print("  3. 屏幕上是否有清晰的数字")
    else:
        print("✗ 截图失败")


# ==================== 程序入口 ====================

if __name__ == "__main__":
    import sys

    print("\n" + "=" * 50)
    print("    自动答题助手 v1.0")
    print("=" * 50)
    print("\n使用方法:")
    print("  1. 直接运行: python auto_solver.py")
    print("  2. 获取鼠标坐标: python auto_solver.py --pos")
    print("  3. 测试 OCR: python auto_solver.py --test")
    print("\n注意事项:")
    print("  - 运行前请先修改 QUESTION_REGION 和 ANSWER_POSITION 坐标")
    print("  - 确保已安装 Tesseract-OCR")
    print("  - 运行时不要遮挡屏幕上的题目区域")

    # 解析命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--pos":
            get_mouse_position()
        elif sys.argv[1] == "--test":
            test_ocr()
        else:
            print(f"\n未知参数: {sys.argv[1]}")
    else:
        # 运行主程序
        run_auto_solver()