import time
import os
from DrissionPage import ChromiumPage

from tools.chaojiying import Chaojiying_Client

#创建浏览器
page = ChromiumPage()
#打开网页
page.get('https://www.gushiwen.cn/user/login.aspx')
time.sleep(1)

#因为找图片并且识别是需要一点时间的，所以先开始找图片
img = page.ele('#imgCode')
#如果下载图片，还需要去requests请求图片地址保存，麻烦
img.get_screenshot('yzm11.png')
chaojiying = Chaojiying_Client('tian91','8n4t','96001')
with open('yzm11.png','rb') as f:
    result = chaojiying.PostPic(f.read(),1004)

yzm = result['pic_str']
print(yzm)

#定位输入账号的地方
zhanghao = page.ele('#email')
#定位输入密码的地方
mima = page.ele('#pwd')
#定位输入验证码的地方
code = page.ele('#code')

#输入内容之前，先清空一下之前的所有内容
zhanghao.clear()
zhanghao.input("19980511434")
mima.input('tian123456')
code.input(yzm)

#点击登录按钮
login = page.ele('#denglu')
login.click()