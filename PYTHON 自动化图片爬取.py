import time
from DrissionPage import ChromiumPage
from DrissionRecord.handlers.xlsx_handler import img2ws
pages = ChromiumPage()
page = ChromiumPage()
page.get("https://www.baidu.com")
textarea=page.ele ("#chat-textarea")
textarea.input ("喜羊羊可爱壁纸")
button=page.ele ("#chat-submit-button")
button.click ()
time.sleep (3)
page.ele ('xpath://div [@id="s_tab_inner"]/a [2]').click ()
for i in range (4):
 time.sleep (4)
page.scroll.to_bottom ()
imgs=page.eles ('xpath://div [@class="cos-image-content"]//img')
print (imgs)
for img in imgs:
 img.save ("weslie qute wallpaper.jpg")
