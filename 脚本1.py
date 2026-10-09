import pyautogui
import time
import pyperclip  # 负责剪贴板，传递中文

# 鼠标移动到微信输入框，0.5秒移动到位
pyautogui.moveTo(x=581, y=1407, duration=0.5)
time.sleep(0.3)  # 等待鼠标稳定
pyautogui.click() # 激活输入框
time.sleep(0.2)

# 这里写你要发送的中文消息
msg = ""

for i in range(1):
    # 把中文复制到剪贴板
    pyperclip.copy(msg)
    # 粘贴快捷键 Ctrl+V
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.1)
    pyautogui.press("enter")
    time.sleep(0.3) # 每条消息发送后停
    msgs = [""]
    for text in msgs:
        pyperclip.copy(text)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        pyautogui.press("enter")
        time.sleep(0.5)