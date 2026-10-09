import cv2
import pytesseract
import pyautogui
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor

# Tesseract OCR路径配置
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def capture_screenshot(region=None):
    # 捕获屏幕截图
    screenshot = pyautogui.screenshot(region=region)  # 捕获指定区域
    img = np.array(screenshot)  # 转换为numpy数组
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)  # 转换为BGR格式
    return img

def extract_text_from_image(img):
    # 图像中提取文本
    custom_config = r'--oem 3 --psm 6'  # Tesseract配置
    text = pytesseract.image_to_string(img, config=custom_config)
    print("识别出的文本:", text)  # 调试输出
    return text.strip()

def wait_for_go(region):
    # 等待识别到go字样后继续执行
    print("等待识别到 'go' 字样...")
    while True:
        img = capture_screenshot(region)
        text = extract_text_from_image(img)
        if 'go' in text.lower():  # 如果识别到"go",开始执行主程序
            print("'go'已识别,开始执行主程序")
            break
        time.sleep(0.1)  # 每秒检查一次

def extract_number_from_image(img):
    # 从图像中提取数字
    custom_config = r'--oem 3 --psm 6 outputbase digits'  # Tesseract配置
    details = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=custom_config)

    # 提取识别出的文本信息
    numbers = []
    for i, text in enumerate(details['text']):
        if text.isdigit():  # 只提取数字
            numbers.append(int(text))
    print("提取的数字:", numbers)  # 调试输出
    return numbers

def draw_comparison_sign(result, start_position):
    # 模拟鼠标滑动绘制比较符号
    pyautogui.moveTo(start_position[0], start_position[1])  # 移动到起始位置

    # 绘制符号
    if result == ">":
        # 绘制大于号
        pyautogui.dragTo(210, 710, button='left', duration=0.00001)  # 上半部分
        pyautogui.dragTo(200, 720, button='left', duration=0.00001)  # 下半部分
    elif result == "<":
        # 绘制小于号
        pyautogui.dragTo(190, 710, button='left', duration=0.00001)
        pyautogui.dragTo(200, 720, button='left', duration=0.00001)  # 下半部分

def process_image(region):
    # 捕获图像并提取数字
    img = capture_screenshot(region)
    numbers = extract_number_from_image(img)
    return numbers

def main(region1, region2):
    # 主循环：捕捉、识别、比较并绘制符号
    iterations = 13  # 设定循环次数
    with ThreadPoolExecutor(max_workers=2) as executor:  # 创建线程池，设置2个并发工作线程
        for i in range(iterations):
            # 使用线程并行处理两个图像捕捉与数字提取
            future1 = executor.submit(process_image, region1)
            future2 = executor.submit(process_image, region2)

            # 获取提取结果
            numbers1 = future1.result()
            numbers2 = future2.result()

            if len(numbers1) > 0 and len(numbers2) > 0:
                num1 = numbers1[0]  # 假设第一张图像提取第一个数字
                num2 = numbers2[0]  # 假设第二张图像提取第一个数字

                print(f"第一张识别到数字: {num1}, 第二张识别到数字: {num2}")

                # 比较数字并绘制符号
                if num1 > num2:
                    draw_comparison_sign(">", (200, 700))  # 在指定位置绘制大于号
                elif num1 < num2:
                    draw_comparison_sign("<", (200, 700))  # 在指定位置绘制小于号
                else:
                    print("两个数字相等，无需绘制符号。")

            time.sleep(0.3)  # 暂停0.3秒再进行下一次截图

# 示例：定义捕捉屏幕的区域
region1 = (100, 300, 100, 100)  # 第一张图像捕捉区域 (x, y, width, height)
region2 = (290, 310, 100, 100)  # 第二张图像捕捉区域 (x, y, width, height)

# 定义 'go' 字样的区域
go_region = (190, 425, 120, 65)  # 假设 'go' 字样出现在这个区域 (x, y, width, height)

# 等待识别到 'go' 字样后启动主程序
wait_for_go(go_region)

# 启动主程序
try:
    main(region1, region2)
except KeyboardInterrupt:
    print("程序已停止")
except Exception as e:
    print("发生错误:", e)
