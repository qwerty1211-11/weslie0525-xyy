import random
from concurrent.futures import ThreadPoolExecutor # 创建线程数的
# 课堂以豆瓣电影举例子，查看时间对比
import requests
from lxml import etree
import time
count = 0
def caiji(url):
    global count
    h = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    }
    resp = requests.get(url=url,headers=h)
    tree = etree.HTML(resp.text)
    #获取每页的内容
    infos = tree.xpath('//div[@class="info"]')
    for i in infos:
        #标题
        # 标题
        title = i.xpath('./div[@class="hd"]/a/span[1]/text()')
        # 导演
        daoyan = i.xpath('./div[@class="bd"]/p/text()')
        # 评分
        pinfen = i.xpath('.//span[@class="rating_num"]/text()')
        # 名句
        mingju = i.xpath('.//p[@class="quote"]/text()')

        #评分
        star = i.xpath('.//span[@class="rating_num"]/text()')
        count+=1
        print(f'第{count}次',title,daoyan,pinfen,mingju)

    time.sleep(random.randint(1,2))

#开始计时
start = time.time() #记录当前的时间
#加上多线程--调用更多的电脑资源，去帮我做这一件事情，
with ThreadPoolExecutor(20) as p:
    for i in range(0,226,25):
        url = f'https://movie.douban.com/top250?start={i}&filter='
        # caiji(url)
        p.submit(caiji,url)
end = time.time() #记录当前的时间

print(f"总共花费了{end-start}")





