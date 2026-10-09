from DrissionPage import ChromiumPage
import pandas

page = ChromiumPage()
#打开网页
page.get('https://bj.ke.com/ershoufang/')
#打开网址先睡一会
page.wait(2)
#定义一个存储列表
all_data = []
#找用户需要的所有数据
lis = page.eles('xpath://ul[@class="sellListContent"]/li[@class="clear"]')
for li in lis:
    info = {
        "标题": li.ele('xpath:.//div[@class="title"]/a').text,
        "地址": li.ele('xpath:.//div[@class="positionInfo"]/a').text,
        "描述": li.ele('xpath:.//div[@class="houseInfo"]').text,
        "总价": li.ele('xpath:.//div[@class="totalPrice totalPrice2"]/span').text,
        "单价": li.ele('xpath:.//div[@class="unitPrice"]/span').text,
        "关注度":li.ele('xpath:.//div[@class="followInfo"]').text,
        "详情网址": li.ele('xpath:./a').attr('href'),
        #找属性，用.attr来获取
        "图片网址": li.ele('xpath:.//img[@class="lj-lazy"]').attr('src')
    }
    all_data.append(info)

#还要保存下来，给用户去看一眼，是不是这样的格式  xlsx   .csv
df = pandas.DataFrame(all_data)
df.to_excel('给用户看一眼的基本数据格式.xlsx',index=False)
import time

#爬贝壳找房---大厂还是小厂？用什么方式 rq  dr

from DrissionPage import ChromiumPage
import pandas

page = ChromiumPage()
#打开网页
page.get('https://bj.ke.com/ershoufang/')
#打开网址先睡一会
page.wait(2)

#页面滚动 学会调整参数即可
for i in range(30):
    #这里可以设置横向和纵向滚动，1是纵向滚动
    height = page.rect.scroll_position[1]
    #向下每次滚动500个像素
    page.scroll.down(500)
    #给点时间让页面加载图片
    time.sleep(0.3)
    #如果滚动前后的位置相同。说明页面达到的底部
    if height == page.rect.scroll_position[1]:
        break




#定义一个存储列表
all_data = []
#找用户需要的所有数据
lis = page.eles('xpath://ul[@class="sellListContent"]/li[@class="clear"]')
for li in lis:
    info = {
        "标题": li.ele('xpath:.//div[@class="title"]/a').text,
        "地址": li.ele('xpath:.//div[@class="positionInfo"]/a').text,
        "描述": li.ele('xpath:.//div[@class="houseInfo"]').text,
        "总价": li.ele('xpath:.//div[@class="totalPrice totalPrice2"]/span').text,
        "单价": li.ele('xpath:.//div[@class="unitPrice"]/span').text,
        "关注度":li.ele('xpath:.//div[@class="followInfo"]').text,
        "详情网址": li.ele('xpath:./a').attr('href'),
        #找属性，用.attr来获取
        "图片网址": li.ele('xpath:.//img[@class="lj-lazy"]').attr('src')
    }
    all_data.append(info)

#还要保存下来，给用户去看一眼，是不是这样的格式  xlsx   .csv
df = pandas.DataFrame(all_data)
df.to_excel('给用户看一眼的基本数据格式.xlsx',index=False)
import time

#爬贝壳找房---大厂还是小厂？用什么方式 rq  dr

from DrissionPage import ChromiumPage
import pandas

from tools.add_image import add_images_to_excel
from tools.captcha_solver import crack_captcha

page = ChromiumPage()
#打开网页
page.get('https://bj.ke.com/ershoufang/pg5/')

#把这个网页放入我们的人机验证板块：文字顺序，按照图片点击顺序，单一滑块不能用
#一定要用自己的用户名和密码
crack_captcha(page)

#打开网址先睡一会
page.wait(2)

#页面滚动 学会调整参数即可
for i in range(30):
    #这里可以设置横向和纵向滚动，1是纵向滚动
    height = page.rect.scroll_position[1]
    #向下每次滚动500个像素
    page.scroll.down(500)
    #给点时间让页面加载图片
    time.sleep(0.3)
    #如果滚动前后的位置相同。说明页面达到的底部
    if height == page.rect.scroll_position[1]:
        break


#定义一个存储列表
all_data = []
#找用户需要的所有数据
lis = page.eles('xpath://ul[@class="sellListContent"]/li[@class="clear"]')
for li in lis:
    info = {
        "标题": li.ele('xpath:.//div[@class="title"]/a').text,
        "地址": li.ele('xpath:.//div[@class="positionInfo"]/a').text,
        "描述": li.ele('xpath:.//div[@class="houseInfo"]').text,
        "总价": li.ele('xpath:.//div[@class="totalPrice totalPrice2"]/span').text,
        "单价": li.ele('xpath:.//div[@class="unitPrice"]/span').text,
        "关注度":li.ele('xpath:.//div[@class="followInfo"]').text,
        "详情网址": li.ele('xpath:./a').attr('href'),
        #找属性，用.attr来获取
        "图片网址": li.ele('xpath:.//img[@class="lj-lazy"]').attr('src')
    }
    all_data.append(info)

#还要保存下来，给用户去看一眼，是不是这样的格式  xlsx   .csv
df = pandas.DataFrame(all_data)
df.to_excel('给用户看一眼的基本数据格式.xlsx',index=False)
#传入excel表格，并取出图片链接这一列内容
add_images_to_excel('给用户看一眼的基本数据格式.xlsx',pandas.DataFrame(all_data)['图片网址'],'H')
import time

#爬贝壳找房---大厂还是小厂？用什么方式 rq  dr

from DrissionPage import ChromiumPage
import pandas

from tools.add_image import add_images_to_excel
from tools.captcha_solver import crack_captcha

page = ChromiumPage()
#打开网页
for i in range(1,8):
    page.get(f'https://bj.ke.com/ershoufang/pg{i}/')

    #把这个网页放入我们的人机验证板块：文字顺序，按照图片点击顺序，单一滑块不能用
    #一定要用自己的用户名和密码
    crack_captcha(page)

    #打开网址先睡一会
    page.wait(2)

    #页面滚动 学会调整参数即可
    for i in range(30):
        #这里可以设置横向和纵向滚动，1是纵向滚动
        height = page.rect.scroll_position[1]
        #向下每次滚动500个像素
        page.scroll.down(500)
        #给点时间让页面加载图片
        time.sleep(0.3)
        #如果滚动前后的位置相同。说明页面达到的底部
        if height == page.rect.scroll_position[1]:
            break


    #定义一个存储列表
    all_data = []
    #找用户需要的所有数据
    lis = page.eles('xpath://ul[@class="sellListContent"]/li[@class="clear"]')
    for li in lis:
        info = {
            "标题": li.ele('xpath:.//div[@class="title"]/a').text,
            "地址": li.ele('xpath:.//div[@class="positionInfo"]/a').text,
            "描述": li.ele('xpath:.//div[@class="houseInfo"]').text,
            "总价": li.ele('xpath:.//div[@class="totalPrice totalPrice2"]/span').text,
            "单价": li.ele('xpath:.//div[@class="unitPrice"]/span').text,
            "关注度":li.ele('xpath:.//div[@class="followInfo"]').text,
            "详情网址": li.ele('xpath:./a').attr('href'),
            #找属性，用.attr来获取
            "图片网址": li.ele('xpath:.//img[@class="lj-lazy"]').attr('src')
        }
        all_data.append(info)
#不要忘了爬完数据，关闭浏览器---因为不关闭浏览器，程序会一直运行浪费内容
page.quit()

#还要保存下来，给用户去看一眼，是不是这样的格式  xlsx   .csv
df = pandas.DataFrame(all_data)
df.to_excel('终版交付.xlsx',index=False)
#传入excel表格，并取出图片链接这一列内容
add_images_to_excel('终版交付.xlsx',pandas.DataFrame(all_data)['图片网址'],'H')
