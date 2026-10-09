import requests
from lxml import etree
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

# 目标小说页面
kaiyangurl = 'https://fanqienovel.com/page/7401399984769207358?enter_from=search'

# 配置无头Chrome（不弹出浏览器窗口）
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")

# 启动浏览器驱动
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
driver.get(kaiyangurl)
time.sleep(3)  # 等待JS加载正文

# 1. 获取标题
title_text = "无名小说"
try:
    h1_elem = driver.find_element(By.TAG_NAME, "h1")
    title_text = h1_elem.text.strip()
    print("小说标题：", title_text)
except:
    print("未读取到标题")

# 清洗文件名非法字符
bad_chars = r'\/:*?"<>|'
safe_name = title_text
for char in bad_chars:
    safe_name = safe_name.replace(char, '-')

# 2. 获取完整正文（JS渲染后的真实文字）
try:
    # 正文容器，根据页面实际章节盒子定位
    content_box = driver.find_element(By.ID, "app")
    full_content = content_box.text
except Exception as e:
    full_content = "未能提取正文"
    print("正文提取失败：", e)

# 写入txt文件
with open(f'{safe_name}.txt', 'w', encoding='utf-8') as f:
    f.write(f"小说链接：{kaiyangurl}\n")
    f.write(f"小说标题：{title_text}\n\n")
    f.write(full_content)

print(f"保存成功，文件名：{safe_name}.txt")
driver.quit()