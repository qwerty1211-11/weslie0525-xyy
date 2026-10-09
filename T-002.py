from DrissionPage import ChromiumPage
page = ChromiumPage()
page.get("https://s.taobao.com/search?_input_charset=utf-8&clientPreloadId=preload_1787225996286&commend=all&ie=utf8&initiative_id=tbindexz_20170306&page=1&preLoadOrigin=https%3A%2F%2Fwww.taobao.com&q=%E5%96%9C%E7%BE%8A%E7%BE%8A%E4%B8%8E%E7%81%B0%E5%A4%AA%E7%8B%BC&search_type=item&source=suggest&sourceId=tb.index&spm=a21bo.jianhua%2Fa.search_history.d1&ssid=s5-e&suggest_query=&tab=all&wq=")
page.wait.doc_loaded()
content=page.html
head=page.ele("tag:head").html
print(head)
body=page.ele("tag:body").html
print(body)
# Please install OpenAI SDK first: `pip3 install openai`
import os
from openai import OpenAI
promt=f"""你是一名严谨的严谨的数据提取专家，请从下面的淘宝的搜索界面中，提取真实的消息
1.标题处理：提取商品标题的全部内容，不包含任何额外的文本或标签。
2.价格处理：只提取数字部分，去除货币符号（如 ¥、$、元等），保留纯数字和小数点。
3.购买人数：页面写啥就抓啥
4.只保留能打开商品页面的部分，删掉页面多余的小尾巴，如果链接开头缺失"https:"请补上
5.同一个商品只抓一次，不要重复
6.标题，价格，购买人数，链接必须来自同一个商品卡片，不要把不同的商品混在一起
7.只抓页面上真实看到的内容，不要瞎编
请严格输出json数组，格式随意，但最好是csv格式
第一个符号必须是【
最后一个必须是】
"""
client = OpenAI(
    api_key=os.environ.get('WESLIE-KEY'),
    base_url="https://api.deepseek.com")

response = client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": promt},
    ],
    stream=False,
    reasoning_effort="high",
    extra_body={"thinking": {"type": "enabled"}}
)
print(response.choices[0].message.content)