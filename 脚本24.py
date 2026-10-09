import pyautogui
import time
import pyperclip

# 1. 定位微信输入框
pyautogui.moveTo(x=2166, y=1424, duration=0.5)
time.sleep(0.3)
pyautogui.click()  # 点击激活输入框
time.sleep(0.2)

# 2. 自定义要发送的多条中文消息列表
message_list = ["羊守13今日开播"]

# 3. 循环发送每一条消息
for text in message_list:
    pyperclip.copy(text)       # 将中文复制到剪贴板
    pyautogui.hotkey("ctrl", "v")  # 粘贴消息
    time.sleep(0.1)
    pyautogui.press("enter")    # 回车发送
    time.sleep(0.8)  # 每条消息间隔时间，可自行调整数值

print("全部消息发送完成！")