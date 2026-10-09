import random
from DrissionPage import ChromiumPage
import csv
import time
all_datas = []
input_works =["爬虫"]
for keyword in input_works:
    page = ChromiumPage()
    page_count = 2
    page.get('https://www.zbj.com/')
    page.ele('xpath://input[@class="j-header-kw"]').input(keyword)
    page.ele('xpath://button[@class="btn-search"]').click()
    k=random.randint(1,9)
    page.wait(k)
    new_page = page.latest_tab
    new_page.ele('xpath://div[@class="tabs"]/a[3]').click()
    for p in range(1, page_count + 1):
        new_page.wait(10)
        items = new_page.eles('xpath://div[@class="card-item-single"]')
        for i in items:
            title = i.ele('xpath:.//span[@class="task-names"]').text
            price = i.ele('xpath:.//div[@class="total-money"]').text
            classify = i.ele('xpath:.//span[@class="depict-refer"]').text
            content = i.ele('xpath:.//div[@class="contents-text"]').text
            try:
                status = i.ele('xpath:.//span[@class="status-box"]').text
            except:
                status = i.ele('xpath:.//span[@class="status-box orange"]').text
            url = i.ele('xpath:./a/@href')
            all_datas.append([keyword, title, status, price, classify, content, url])
        time.sleep(1)
    page.quit()
with open("猪八戒网站数据.csv","w",newline="",encoding="utf-8") as f:
    cf = csv.writer(f)
    cf.writerow(["关键词","标题","状态","价格","需求分类","描述","详情链接"])
    cf.writerows(all_datas)
print(f"数据爬取完成！共获取 {len(all_datas)} 条任务数据，已保存到 csv文件")
print("SUCCESS")



