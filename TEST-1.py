from DrissionPage import ChromiumPage
import os
import re  # 导入正则表达式模块
import csv  # 导入csv模块
from openai import OpenAI
# --- 1. 网页抓取部分 ---
page = ChromiumPage()
page.get("https://item.taobao.com/item.htm?abbucket=9&id=963897523790&mi_id=0000cDI3v5GusWamC1nL_54D-XKzEwmg_Qpoxymztk6gkhA&ns=1&priceTId=2150486917870607141273687e1a8d&skuId=5906400897838&spm=a21n57.1.hoverItem.11&utparam=%7B%22aplus_abtest%22%3A%22e6b2866f047fab0eb7a2ffb332e47d6f%22%7D&xxc=taobaoSearch")
page.wait.doc_loaded()
content = page.html

# --- 2. AI 模型调用部分 ---
prompt = f"帮我从网页源码中提取标题和价格：{content}"
client = OpenAI(
    api_key=os.getenv("WESLIE-KEY"),
    base_url="https://api.deepseek.com")

response = client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": prompt},
    ],
    stream=False,
    reasoning_effort="high",
    extra_body={"thinking": {"type": "enabled"}}
)

# 获取模型返回的文本内容
ai_response_text = response.choices[0].message.content
print("AI 模型原始响应：")
print(ai_response_text)

# --- 3. 数据解析与保存部分 ---
# 使用正则表达式从 AI 的响应中提取标题和价格
# 假设 AI 的回复格式类似于 "标题：xxx\n价格：xxx"
title_match = re.search(r"标题[:：]\s*(.+)", ai_response_text)
price_match = re.search(r"价格[:：]\s*(.+)", ai_response_text)

# 提取数据，如果没找到则为 None
title = title_match.group(1).strip() if title_match else None
price = price_match.group(1).strip() if price_match else None

# 将数据保存为 CSV 文件
csv_filename = 'taobao_product_info.csv'
try:
    # 使用 'w' 模式写入，newline='' 用于避免在某些系统中产生空行
    # encoding='utf-8-sig' 可以确保 Excel 打开时中文不乱码
    with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        # 写入表头
        writer.writerow(['标题', '价格'])
        # 写入数据行
        writer.writerow([title, price])
    print(f"\n✅ 数据已成功保存到 {csv_filename}")
except Exception as e:
    print(f"\n❌ 保存文件时出错: {e}")