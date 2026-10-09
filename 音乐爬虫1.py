import requests
# 导入xpath工具
from lxml import etree
import json
# 以周杰伦为例，第一次发请求，后续可以改成输入框，手动输入歌手来爬取
kaiyangurl = "https://www.gequbao.net/"
# 定义请求头，模拟浏览器访问
kaiyangheaders = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
}
# 第一次请求网络，歌曲列表  发送请求，得到响应
response = requests.get(url=kaiyangurl,headers=kaiyangheaders)

# print(response.text)
#这个网站里有我们需要的内容，那么就把文本转为树
data = etree.HTML(response.text)
#用xpath去寻找每首歌的链接地址
info = data.xpath('//a[@class="hover-zoom d-block text-decoration-none"]')
print(len(info)) # 这就找到了112首歌的爹
#接着用循环，找里面的每个a标签
#一次下112首太多了，我们用切片，只下载3首 info[0:3]
#i就是每首歌的div
for i in info[0:3]: #想下载112首，这里不写就行了
    #提取第一首歌的名字 找a标签的title属性
    title = i.xpath('./text()')[0].strip()
    print(f'正在下载歌曲{title}....')
    aurl = i.xpath('./@href')[0]
    #我们要的是这样的格式 https://www.gequbao.com  +  /music/39466
    gequ_url ="https://www.gequbao.com" + aurl
    print(gequ_url)





















