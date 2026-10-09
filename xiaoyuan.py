# -*- coding: utf-8 -*-
"""
小袁口算自动PK脚本 单文件版，PyCharm直接运行
使用前：先运行坐标工具获取屏幕坐标，修改下方CONFIG配置
紧急停止：鼠标甩到屏幕左上角，或者Ctrl+C
"""
import re
import time
import random
import os
import sys
from io import BytesIO
from datetime import datetime

import pyautogui
from PIL import Image, ImageGrab, ImageEnhance

# ======================【在这里修改你的配置！】======================
class CONFIG:
    # -------- 题目截图区域，运行坐标工具获取真实坐标替换这里 --------
    QUESTION_AREA = {
        'x': 400,      # 题目左上角X
        'y': 200,      # 题目左上角Y
        'w': 400,      # 宽度
        'h': 150       # 高度
    }
    SCREEN_CAPTURE_REGION = {
        'x': 400,
        'y': 200,
        'width': 400,
        'height': 150
    }

    # 选项区域
    OPTION_AREAS = [
        {'x': 300, 'y': 400, 'w': 200, 'h': 80},
        {'x': 700, 'y': 400, 'w': 200, 'h': 80},
        {'x': 300, 'y': 520, 'w': 200, 'h': 80},
        {'x': 700, 'y': 520, 'w': 200, 'h': 80}
    ]
    ANSWER_INPUT_AREA = {'x': 500, 'y': 450, 'w': 200, 'h': 60}

    # 自动化参数
    MOUSE_MOVE_DELAY = 0.2
    CLICK_DELAY = 0.1
    OCR_RETRY_COUNT = 3
    ACTION_INTERVAL = 0.5
    ANSWER_DELAY_RANGE = [0.4, 0.8]
    ANSWER_MODE = "auto"  # auto / choice / input

    # OCR图像预处理
    ENABLE_IMAGE_PREPROCESSING = True
    BINARY_THRESHOLD = 150

    # 调试
    DEBUG_SAVE_SCREENSHOTS = False
    DEBUG_SCREENSHOT_DIR = "./screenshots"
    VERBOSE_LOGGING = True
# =================================================================

# ---------------- OCR引擎模块 ----------------
class OCREngine:
    def __init__(self):
        import ddddocr
        try:
            self.ocr = ddddocr.DdddOcr(show_ad=False)
            if CONFIG.VERBOSE_LOGGING:
                print("[信息] OCR引擎初始化成功")
        except Exception as e:
            if CONFIG.VERBOSE_LOGGING:
                print(f"[错误] OCR引擎初始化失败：{e}")
            raise e

    def recognize_text(self, image):
        try:
            if image.mode != 'RGB':
                image = image.convert('RGB')
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_bytes = img_byte_arr.getvalue()
            text = self.ocr.classification(img_bytes)
            if CONFIG.VERBOSE_LOGGING:
                print(f"[OCR]识别结果：'{text}'")
            return text.strip()
        except Exception as e:
            if CONFIG.VERBOSE_LOGGING:
                print(f"[错误]OCR识别失败：{e}")
            return None

    def recognize_with_retry(self, image, max_retries=None):
        if max_retries is None:
            max_retries = CONFIG.OCR_RETRY_COUNT
        for attempt in range(max_retries):
            result = self.recognize_text(image)
            if result and len(result) > 0 and self._is_valid_expression(result):
                return result
            if CONFIG.VERBOSE_LOGGING:
                print(f"[警告]第{attempt+1}次识别无效，重试…")
        if CONFIG.VERBOSE_LOGGING:
            print(f"[错误]OCR识别失败，重试{max_retries}次完毕")
        return None

    def _is_valid_expression(self, text):
        has_digit = bool(re.search(r'\d', text))
        has_operator = bool(re.search(r'[+\-×÷*/=]', text))
        return has_digit and has_operator


# ---------------- 屏幕截图模块 ----------------
def save_debug_image(image, prefix):
    try:
        if not os.path.exists(CONFIG.DEBUG_SCREENSHOT_DIR):
            os.makedirs(CONFIG.DEBUG_SCREENSHOT_DIR)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{prefix}_{timestamp}.png"
        filepath = os.path.join(CONFIG.DEBUG_SCREENSHOT_DIR, filename)
        image.save(filepath)
        if CONFIG.VERBOSE_LOGGING:
            print(f"[调试]保存截图:{filepath}")
    except Exception as e:
        if CONFIG.VERBOSE_LOGGING:
            print(f"[错误]保存截图失败:{e}")


def capture_question_area():
    try:
        area = CONFIG.QUESTION_AREA
        x, y, w, h = area['x'], area['y'], area['w'], area['h']
        screenshot = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        if CONFIG.DEBUG_SAVE_SCREENSHOTS:
            save_debug_image(screenshot, "question")
        return screenshot
    except Exception as e:
        if CONFIG.VERBOSE_LOGGING:
            print(f"[错误]截取题目失败：{e}")
        return None


class ScreenCapture:
    def capture_region(self):
        return capture_question_area()


# ---------------- 计算器模块 ----------------
class Calculator:
    def __init__(self):
        self.operator_map = {
            '×': '*',
            '÷': '/',
            '＋': '+',
            '－': '-',
            '等于': '=',
            '＝': '='
        }

    def parse_expression(self, text):
        if not text:
            return None
        norm = text
        for old, new in self.operator_map.items():
            norm = norm.replace(old, new)
        pat1 = r'(\d+)\s*([+\-*/])\s*(\d+)\s*=?'
        m1 = re.search(pat1, norm)
        if m1:
            expr = f"{m1.group(1)}{m1.group(2)}{m1.group(3)}"
            if CONFIG.VERBOSE_LOGGING:
                print(f"[解析]原始:'{text}' →算式:'{expr}'")
            return expr
        pat2 = r'(\d+)\s*([+\-*/xX÷])\s*(\d+)'
        m2 = re.search(pat2, norm)
        if m2:
            n1, op, n2 = m2.groups()
            if op in ['x', 'X']:
                op = '*'
            expr = f"{n1}{op}{n2}"
            if CONFIG.VERBOSE_LOGGING:
                print(f"[解析]宽松匹配:{expr}")
            return expr
        if CONFIG.VERBOSE_LOGGING:
            print(f"[警告]无法解析算式:{text}")
        return None

    def calculate(self, expression):
        if not expression:
            return None
        try:
            if not re.match(r'^[\d+\-*/().\s]+$', expression):
                if CONFIG.VERBOSE_LOGGING:
                    print(f"[错误]非法字符:{expression}")
                return None
            res = eval(expression)
            if isinstance(res, float) and res.is_integer():
                res = int(res)
            if CONFIG.VERBOSE_LOGGING:
                print(f"[计算] {expression} = {res}")
            return res
        except ZeroDivisionError:
            if CONFIG.VERBOSE_LOGGING:
                print(f"[错误]除零错误:{expression}")
            return None
        except Exception as e:
            if CONFIG.VERBOSE_LOGGING:
                print(f"[错误]计算异常:{e}")
            return None

    def solve(self, ocr_text):
        exp = self.parse_expression(ocr_text)
        if not exp:
            return None
        return self.calculate(exp)


# ---------------- 自动化操作模块 ----------------
class AutoAction:
    def __init__(self):
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1
        if CONFIG.VERBOSE_LOGGING:
            print("[信息]自动化模块初始化成功")
            print("[提示]鼠标移到屏幕角落可紧急停止")

    def click_at_position(self, x, y, clicks=1, button='left', duration=None):
        try:
            if duration is None:
                duration = random.uniform(0.1, 0.3)
            pyautogui.click(x=x, y=y, clicks=clicks, interval=0.1, button=button, duration=duration)
            if CONFIG.VERBOSE_LOGGING:
                print(f"[操作]点击 ({x},{y})")
        except Exception as e:
            if CONFIG.VERBOSE_LOGGING:
                print(f"[错误]点击失败:{e}")

    def input_text(self, text, interval=None):
        try:
            if interval is None:
                interval = random.uniform(0.05, 0.15)
            pyautogui.write(text, interval=interval)
            if CONFIG.VERBOSE_LOGGING:
                print(f"[操作]输入:'{text}'")
        except Exception as e:
            if CONFIG.VERBOSE_LOGGING:
                print(f"[错误]输入失败:{e}")

    def press_key(self, key):
        try:
            pyautogui.press(key)
            if CONFIG.VERBOSE_LOGGING:
                print(f"[操作]按键:{key}")
        except Exception as e:
            if CONFIG.VERBOSE_LOGGING:
                print(f"[错误]按键失败:{e}")

    def answer_multiple_choice(self, answer, option_positions=None):
        if option_positions is None:
            bx = CONFIG.SCREEN_CAPTURE_REGION['x']
            by = CONFIG.SCREEN_CAPTURE_REGION['y'] + CONFIG.SCREEN_CAPTURE_REGION['height'] + 50
            option_positions = {
                'A': (bx + 50, by),
                'B': (bx + 200, by),
                'C': (bx + 350, by),
                'D': (bx + 500, by)
            }
        ak = str(answer).upper()
        num_map = {'1': 'A', '2': 'B', '3': 'C', '4': 'D'}
        if ak in num_map:
            ak = num_map[ak]
        if ak in option_positions:
            pos = option_positions[ak]
            self.click_at_position(pos[0], pos[1])
            if CONFIG.VERBOSE_LOGGING:
                print(f"[操作]选择选项 {ak} {pos}")
        else:
            if CONFIG.VERBOSE_LOGGING:
                print(f"[警告]未知选项{ak},随机选")
            rk = random.choice(list(option_positions.keys()))
            pos = option_positions[rk]
            self.click_at_position(pos[0], pos[1])

    def answer_input_mode(self, answer):
        bx = CONFIG.SCREEN_CAPTURE_REGION['x'] + CONFIG.SCREEN_CAPTURE_REGION['width'] // 2
        by = CONFIG.SCREEN_CAPTURE_REGION['y'] + CONFIG.SCREEN_CAPTURE_REGION['height'] + 60
        self.click_at_position(bx, by)
        time.sleep(random.uniform(0.2, 0.4))
        self.input_text(str(answer))
        time.sleep(random.uniform(0.2, 0.4))
        self.press_key('enter')

    def smart_answer(self, answer, mode='auto'):
        if mode == 'choice':
            self.answer_multiple_choice(answer)
        elif mode == 'input':
            self.answer_input_mode(answer)
        else:
            self.answer_multiple_choice(answer)


# ---------------- 主机器人逻辑 ----------------
class AutoPKBot:
    def __init__(self):
        print("="*50)
        print("小袁口算自动PK脚本【单文件版】")
        print("="*50)
        self.screen_capture = ScreenCapture()
        self.ocr_engine = OCREngine()
        self.calculator = Calculator()
        self.auto_action = AutoAction()
        self.stats = {"total_questions":0,"success_count":0,"fail_count":0,"start_time":None}
        print("\n[信息]全部模块初始化完成")
        print(f"[配置]截取区域 {CONFIG.SCREEN_CAPTURE_REGION}")
        print("[提示]打开小袁口算PK页面放到前台；Ctrl+C停止\n")

    def process_one_question(self):
        try:
            if CONFIG.VERBOSE_LOGGING:
                print("\n[步骤1]截取题目")
            img = self.screen_capture.capture_region()
            if img is None:
                print("[错误]截图失败")
                return False

            if CONFIG.VERBOSE_LOGGING:
                print("[步骤2]OCR识别")
            ocr_text = self.ocr_engine.recognize_text(img)
            if not ocr_text or len(ocr_text.strip())<3:
                print(f"[警告]识别过短/空：{ocr_text}")
                return False
            print(f"[识别]题目文本：{ocr_text.strip()}")

            if CONFIG.VERBOSE_LOGGING:
                print("[步骤3]计算答案")
            ans = self.calculator.solve(ocr_text)
            if ans is None:
                print("[警告]无法算出答案")
                return False
            print(f"[计算]答案 = {ans}")

            if CONFIG.VERBOSE_LOGGING:
                print("[步骤4]执行答题")
            self.auto_action.smart_answer(ans, mode=CONFIG.ANSWER_MODE)

            wait = random.uniform(*CONFIG.ANSWER_DELAY_RANGE)
            print(f"[等待]{wait:.2f}秒后下一题")
            time.sleep(wait)
            return True
        except Exception as e:
            print(f"[异常]处理题目出错:{e}")
            return False

    def run(self, max_questions=None):
        self.stats["start_time"] = time.time()
        self.stats.update({"total_questions":0,"success_count":0,"fail_count":0})
        print("\n"+"="*50)
        print("🚀开始自动PK循环")
        print("="*50+"\n")
        try:
            while True:
                if max_questions and self.stats["total_questions"] >= max_questions:
                    print(f"\n达到最大题数 {max_questions}，退出循环")
                    break
                ok = self.process_one_question()
                self.stats["total_questions"] +=1
                if ok:
                    self.stats["success_count"] +=1
                else:
                    self.stats["fail_count"] +=1

                elapsed = time.time()-self.stats["start_time"]
                print(f"\n[进度]总题:{self.stats['total_questions']} |成功:{self.stats['success_count']} |失败:{self.stats['fail_count']} |耗时{elapsed:.1f}s")

                if self.stats["total_questions"] % 10 == 0:
                    rest = random.uniform(2,5)
                    print(f"\n[休息]已10题，休息{rest:.1f}秒")
                    time.sleep(rest)
        except KeyboardInterrupt:
            print("\n\n用户Ctrl+C手动终止脚本")
        except Exception as e:
            print(f"\n[致命错误]运行异常:{e}")
        finally:
            self.print_summary()

    def print_summary(self):
        print("\n"+"="*50)
        print("📊运行统计报告")
        print("="*50)
        t = self.stats["total_questions"]
        s = self.stats["success_count"]
        f = self.stats["fail_count"]
        elap = time.time()-self.stats["start_time"] if self.stats["start_time"] else 0
        print(f"总答题数:{t}")
        print(f"成功:{s}  失败:{f}")
        if t>0:
            print(f"成功率:{(s/t*100):.1f}%")
            print(f"平均每题:{elap/t:.2f}秒")
        print(f"总耗时:{elap:.1f}秒")
        print("="*50)


# ---------------- 坐标获取小工具（运行这个获取屏幕坐标） ----------------
def tool_get_mouse_pos():
    print("="*60)
    print("🎯鼠标坐标获取工具")
    print("="*60)
    print("打开小袁口算PK界面，鼠标移动到题目左上角看X,Y；再移到右下角看X,Y")
    print("按 Ctrl+C 退出工具\n")
    try:
        while True:
            x,y = pyautogui.position()
            sw,sh = pyautogui.size()
            print(f"\r当前坐标 X={x:4d} Y={y:4d} 屏幕分辨率 {sw}×{sh}",end="",flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n工具结束。把坐标填入上方CONFIG类的QUESTION_AREA")


def check_env():
    if sys.platform in ("win32","darwin"):
        return True
    display = os.environ.get("DISPLAY")
    if not display:
        print("[警告]没有图形界面！不能运行，需要桌面环境")
        return False
    return True


def main():
    print("\n请选择模式：")
    print("1 = 坐标获取工具（先运行这个！拿到屏幕坐标）")
    print("2 = 启动自动PK答题机器人")
    sel = input("\n输入数字1或2：").strip()
    if sel == "1":
        tool_get_mouse_pos()
        return
    if sel == "2":
        if not check_env():
            print("环境检查失败，退出")
            return
        bot = AutoPKBot()
        bot.run(max_questions=None)
    else:
        print("输入错误，退出")


if __name__ == "__main__":
    main()
