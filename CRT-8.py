from DrissionPage import ChromiumPage
page = ChromiumPage()
page.get("https://item.taobao.com/item.htm?abbucket=9&id=963897523790&mi_id=0000cDI3v5GusWamC1nL_54D-XKzEwmg_Qpoxymztk6gkhA&ns=1&priceTId=2150486917870607141273687e1a8d&skuId=5906400897838&spm=a21n57.1.hoverItem.11&utparam=%7B%22aplus_abtest%22%3A%22e6b2866f047fab0eb7a2ffb332e47d6f%22%7D&xxc=taobaoSearch")
page.wait.doc_loaded()
content=page.html
# Please install OpenAI SDK first: `pip3 install openai`
import os
from openai import OpenAI
prompt=f"帮我从网页源码中提取标题和价格：{content}"
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
print(response.choices[0].message.content)
with open("r", encoding="utf-8") as f:
    f.wirte()

