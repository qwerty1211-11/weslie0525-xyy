import pyautogui
import time
# 鼠标移动到微信输入框，0.5秒移动到位
pyautogui.moveTo(x=581, y=1407, duration=0.5)
time.sleep(0.3)  # 等待鼠标稳定
pyautogui.click() # 激活输入框
time.sleep(0.2)
msg = "welie is very very cute"
for i in range(1):
    pyautogui.typewrite(msg)
    time.sleep(0.1)
    pyautogui.press("enter")
    time.sleep(0.3) # 每条消息发送后停顿



