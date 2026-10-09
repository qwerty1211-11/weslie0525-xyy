import cv2
import pyautogui
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor
import ddddocr

# 初始化OCR，只初始化一次，关闭广告
ocr = ddddocr.DdddOcr(show_ad=False)

pyautogui.FAILSAFE = True


def capture_screenshot(region=None):
    # 捕获屏幕截图
    screenshot = pyautogui.screenshot(region=region)
    img = np.array(screenshot)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    return img


def preprocess_ocr_img(img):
    """图像预处理：灰度、二值化"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return thresh


def extract_text_from_image(img):
    """识别go文字，用于等待触发"""
    img_proc = preprocess_ocr_img(img)
    # opencv图片转二进制bytes给ddddocr
    _, buffer = cv2.imencode('.png', img_proc)
    bytes_data = buffer.tobytes()
    text = ocr.classification(bytes_data)
    print("识别出的文本:", text)
    return text.strip()


def wait_for_go(region):
    print("等待识别到 'go' 字样...")
    while True:
        img = capture_screenshot(region)
        text = extract_text_from_image(img)
        if 'go' in text.lower():
            print("'go'已识别,开始执行主程序")
            break
        time.sleep(0.1)


def extract_number_from_image(img):
    """提取图片里面数字"""
    img_proc = preprocess_ocr_img(img)
    _, buffer = cv2.imencode('.png', img_proc)
    bytes_data = buffer.tobytes()
    raw_text = ocr.classification(bytes_data)
    numbers = []
    # 过滤只保留数字
    clean_digits = ''.join([c for c in raw_text if c.isdigit()])
    if clean_digits:
        numbers.append(int(clean_digits))
    print("提取的数字:", numbers)
    return numbers


def draw_comparison_sign(result, start_position):
    # 模拟鼠标滑动绘制比较符号
    pyautogui.moveTo(start_position[0], start_position[1])
    drag_dur = 0.02
    if result == ">":
        pyautogui.dragTo(210, 710, button='left', duration=drag_dur)
        pyautogui.dragTo(200, 720, button='left', duration=drag_dur)
    elif result == "<":
        pyautogui.dragTo(190, 710, button='left', duration=drag_dur)
        pyautogui.dragTo(200, 720, button='left', duration=drag_dur)


def process_image(region):
    img = capture_screenshot(region)
    numbers = extract_number_from_image(img)
    return numbers


def main(region1, region2):
    iterations = 13
    with ThreadPoolExecutor(max_workers=2) as executor:
        for i in range(iterations):
            print(f"\n=====第 {i+1}/{iterations} 轮 =====")
            future1 = executor.submit(process_image, region1)
            future2 = executor.submit(process_image, region2)
            numbers1 = future1.result()
            numbers2 = future2.result()

            if len(numbers1) == 0 or len(numbers2) == 0:
                print("⚠️ 某区域没有识别到数字，跳过本轮")
                time.sleep(0.3)
                continue

            num1 = numbers1[0]
            num2 = numbers2[0]
            print(f"第一张识别到数字: {num1}, 第二张识别到数字: {num2}")

            if num1 > num2:
                draw_comparison_sign(">", (200, 700))
            elif num1 < num2:
                draw_comparison_sign("<", (200, 700))
            else:
                print("两个数字相等，无需绘制符号。")

            time.sleep(0.3)


# 截图区域 (x, y, width, height)
region1 = (100, 300, 100, 100)
region2 = (290, 310, 100, 100)
go_region = (190, 425, 120, 65)


if __name__ == "__main__":
    try:
        wait_for_go(go_region)
        main(region1, region2)
        print("\n✅全部循环执行完毕")
    except KeyboardInterrupt:
        print("\n程序被手动停止")
    except Exception as e:
        print(f"\n发生错误: {type(e).__name__} → {e}")


