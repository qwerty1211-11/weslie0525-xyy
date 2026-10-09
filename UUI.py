import requests
from lxml import etree


kaiyangurl = 'https://fanqienovel.com/page/7401399984769207358?enter_from=search'

kaiyangheaders = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
}
response = requests.get(url=kaiyangurl, headers=kaiyangheaders)
response.encoding = response.apparent_encoding  # 自动识别网页编码，防止乱码
print(response.text)
data = etree.HTML(response.text)

# 自动提取章节标题，不再手动写死
title = data.xpath('//h1/text()')
print(title[0])

# 清洗文件名非法字符 \ / : * ? " < > |
bad_chars = r'\/:*?"<>|'
safe_name = title[0]
for char in bad_chars:
    safe_name = safe_name.replace(char, '-')

# 获取正文内容
body = data.xpath('//div[@id="app"]//text()')
print(body)

# 只打开一次文件，循环写入，性能更好
with open(f'{safe_name}.txt', 'a', encoding='utf-8') as f:
    for hang in body:
        # 拼接内容写入
        f.write('https://fanqienovel.com//reader/7401399989756248638 ' + hang + '\n')
        #id = "booktxt