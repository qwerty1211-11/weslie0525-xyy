from DrissionPage import ChromiumPage
page = ChromiumPage()
page.get("https://www.jd.com/")
page.set.cookies.clear()
page.wait(1)
page.refresh()
import time
cookie1="cud=c6fd19ccb304a45a81f38a0793109a20; __jdu=17859894120541259424148; PCSYCityID=CN_210000_211200_0; shshshfpa=05c14d7b-a4d1-90d4-c8d4-e8368d0e5f6b-1785989418; shshshfpx=05c14d7b-a4d1-90d4-c8d4-e8368d0e5f6b-1785989418; PCSYHWHR=1; areaId=0; ipLoc-djd=1-72-2799-0; thor=24E49124BA128F56B007818D89D5174F21959F2E5A3A44DEB825957A005653B2FE756B2C92A70407E861617AFE535E782B10B5D81415209C94DB8416148F4B2ADB535245B6CA1B2544B0BE1BAA010A96ED31EC809D92EED99EF9FB662C909AD35FAFB46270E0D743FBF3C8EF5CF2948A267E6003B5FB050E9E35A366EB30CA14550220447FB6BC9E554AF29533891CD90883FA7B0E0271AA28B31729F15DB905; light_key=AASBKE7rOxgWQziEhC_QY6yaKmn_Qwj41uF_3fjI8hBF9fS6cXKxkqJFVwYNBuIF3PL5DoSH; pinId=7u1Dd6Y9lGHGx3RL8p8NR7V9-x-f3wj7; pin=jd_53bcbb094d007; unick=jd_1oi6v9i9l5pgmr; _tp=zTKZdHPA2NWeZ731CiMjm7qmNj7Pc1ejtMNy0Y8hJiM%3D; _pst=jd_53bcbb094d007; __jdv=76161171%7Cbaidu%7C-%7Corganic%7Cnot%20set%7C1786003574272; cvt=3; umc_count=1; mail_times=4%2C2%2C1786030403759; cn=0; 3AB9D23F7A4B3C9B=B6EYDJXJKBCKIBXWQ5MDZHRQQFPUMRYI5C6PYJZJ4LQDJETUYSIKQQMQMY2SR3EUUJFL36KDNZ745WYLFFBVEGJKZM; 3AB9D23F7A4B3CSS=jdd03B6EYDJXJKBCKIBXWQ5MDZHRQQFPUMRYI5C6PYJZJ4LQDJETUYSIKQQMQMY2SR3EUUJFL36KDNZ745WYLFFBVEGJKZMAAAAM727AZELIAAAAADYNUQYKLFVS5QMX; shshshfpb=BApXWXDfJ1PpAN-NrVpZ-YHodgUE2yO6xBsfZkzdo9xJ1ItZfQtOFkBnpjnujZ4IjI-IX37WNsqFbIb9g7_xat9x6Mlrg_T5_kMrb; sdtoken=AAbEsBpEIOVjqTAKCQtvQu17V91wHMT8yj7-5OrJ4exL3z3FCfE8FzE96hO_VY6yOr7JtyTkSUSOw0nZhtfYNXdo60OeKzIbvb4E06DR2ujlLDEsEdkEulwD1zqHVJwaXmhIs3-RH1T4S7OSIqJyOI4O9dprQBEgtqbBS0MSenqf15q422Qk; flash=3_bQHzWQ1JR9tYVPY7DpUx98wuH3kJAXb--9ySeY8gSbKOk_F2Lrsm4M6soDYEZGUlL-oLVaTM2g7H3-yit14Zn03Xl7NyZRUn3v622tOhBMf0Te2HNJMAXMF4sVy9g4vfoHORy4CWJch6tBqnGV**; csn=14; __jda=143920055.17859894120541259424148.1785989412.1786003574.1786030402.4; __jdb=143920055.15.17859894120541259424148|4.1786030402; __jdc=143920055"
cookie2="cud=c6fd19ccb304a45a81f38a0793109a20; __jdu=17859894120541259424148; PCSYCityID=CN_210000_211200_0; shshshfpa=05c14d7b-a4d1-90d4-c8d4-e8368d0e5f6b-1785989418; shshshfpx=05c14d7b-a4d1-90d4-c8d4-e8368d0e5f6b-1785989418; PCSYHWHR=1; areaId=0; ipLoc-djd=1-72-2799-0; thor=24E49124BA128F56B007818D89D5174F21959F2E5A3A44DEB825957A005653B2FE756B2C92A70407E861617AFE535E782B10B5D81415209C94DB8416148F4B2ADB535245B6CA1B2544B0BE1BAA010A96ED31EC809D92EED99EF9FB662C909AD35FAFB46270E0D743FBF3C8EF5CF2948A267E6003B5FB050E9E35A366EB30CA14550220447FB6BC9E554AF29533891CD90883FA7B0E0271AA28B31729F15DB905; light_key=AASBKE7rOxgWQziEhC_QY6yaKmn_Qwj41uF_3fjI8hBF9fS6cXKxkqJFVwYNBuIF3PL5DoSH; pinId=7u1Dd6Y9lGHGx3RL8p8NR7V9-x-f3wj7; pin=jd_53bcbb094d007; unick=jd_1oi6v9i9l5pgmr; _tp=zTKZdHPA2NWeZ731CiMjm7qmNj7Pc1ejtMNy0Y8hJiM%3D; _pst=jd_53bcbb094d007; __jdv=76161171%7Cbaidu%7C-%7Corganic%7Cnot%20set%7C1786003574272; cvt=3; cn=0; 3AB9D23F7A4B3C9B=B6EYDJXJKBCKIBXWQ5MDZHRQQFPUMRYI5C6PYJZJ4LQDJETUYSIKQQMQMY2SR3EUUJFL36KDNZ745WYLFFBVEGJKZM; 3AB9D23F7A4B3CSS=jdd03B6EYDJXJKBCKIBXWQ5MDZHRQQFPUMRYI5C6PYJZJ4LQDJETUYSIKQQMQMY2SR3EUUJFL36KDNZ745WYLFFBVEGJKZMAAAAM727AZELIAAAAADYNUQYKLFVS5QMX; shshshfpb=BApXWXDfJ1PpAN-NrVpZ-YHodgUE2yO6xBsfZkzdo9xJ1ItZfQtOFkBnpjnujZ4IjI-IX37WNsqFbIb9g7_xat9x6Mlrg_T5_kMrb; flash=3_DTfxk-fkzkRnbcwjYLa300iAKHfXsaVgkuQqed_8CVJ46XcO_X7E83_cQjjPU1-PXw81GokwbQGnfoCt-uSCMXxwKuXXi--ovugBtVG4NH6px6-PpbcWC2GPtwpc-YDydLHNokPrQ_DrKhMJre**; sdtoken=AAbEsBpEIOVjqTAKCQtvQu17AWmikVvyRxv2Sxm_H--GZ-1Wd7ZCg8GDe1TjS3FE4MQ8NC9PB38ST1xBhES-QVidBcB0boAF58Q5ZIPlpgnb1CUNkSxaK0gcant60VOt7VVMVi-QxwtzNE49WCgb6WPrdm5uTqSxDRbUtoi6Um4Y_BLTLw; __jda=143920055.17859894120541259424148.1785989412.1786003574.1786030402.4; __jdc=143920055; csn=21; __jdb=143920055.22.17859894120541259424148|4.1786030402"
cookie3="cud=c6fd19ccb304a45a81f38a0793109a20; __jdu=17859894120541259424148; PCSYCityID=CN_210000_211200_0; shshshfpa=05c14d7b-a4d1-90d4-c8d4-e8368d0e5f6b-1785989418; shshshfpx=05c14d7b-a4d1-90d4-c8d4-e8368d0e5f6b-1785989418; PCSYHWHR=1; areaId=0; ipLoc-djd=1-72-2799-0; thor=24E49124BA128F56B007818D89D5174F21959F2E5A3A44DEB825957A005653B2FE756B2C92A70407E861617AFE535E782B10B5D81415209C94DB8416148F4B2ADB535245B6CA1B2544B0BE1BAA010A96ED31EC809D92EED99EF9FB662C909AD35FAFB46270E0D743FBF3C8EF5CF2948A267E6003B5FB050E9E35A366EB30CA14550220447FB6BC9E554AF29533891CD90883FA7B0E0271AA28B31729F15DB905; light_key=AASBKE7rOxgWQziEhC_QY6yaKmn_Qwj41uF_3fjI8hBF9fS6cXKxkqJFVwYNBuIF3PL5DoSH; pinId=7u1Dd6Y9lGHGx3RL8p8NR7V9-x-f3wj7; pin=jd_53bcbb094d007; unick=jd_1oi6v9i9l5pgmr; _tp=zTKZdHPA2NWeZ731CiMjm7qmNj7Pc1ejtMNy0Y8hJiM%3D; _pst=jd_53bcbb094d007; __jdv=76161171%7Cbaidu%7C-%7Corganic%7Cnot%20set%7C1786003574272; cvt=3; cn=0; 3AB9D23F7A4B3C9B=B6EYDJXJKBCKIBXWQ5MDZHRQQFPUMRYI5C6PYJZJ4LQDJETUYSIKQQMQMY2SR3EUUJFL36KDNZ745WYLFFBVEGJKZM; 3AB9D23F7A4B3CSS=jdd03B6EYDJXJKBCKIBXWQ5MDZHRQQFPUMRYI5C6PYJZJ4LQDJETUYSIKQQMQMY2SR3EUUJFL36KDNZ745WYLFFBVEGJKZMAAAAM727AZELIAAAAADYNUQYKLFVS5QMX; shshshfpb=BApXWXDfJ1PpAN-NrVpZ-YHodgUE2yO6xBsfZkzdo9xJ1ItZfQtOFkBnpjnujZ4IjI-IX37WNsqFbIb9g7_xat9x6Mlrg_T5_kMrb; flash=3_DTfxk-fkzkRnbcwjYLa300iAKHfXsaVgkuQqed_8CVJ46XcO_X7E83_cQjjPU1-PXw81GokwbQGnfoCt-uSCMXxwKuXXi--ovugBtVG4NH6px6-PpbcWC2GPtwpc-YDydLHNokPrQ_DrKhMJre**; sdtoken=AAbEsBpEIOVjqTAKCQtvQu17AWmikVvyRxv2Sxm_H--GZ-1Wd7ZCg8GDe1TjS3FE4MQ8NC9PB38ST1xBhES-QVidBcB0boAF58Q5ZIPlpgnb1CUNkSxaK0gcant60VOt7VVMVi-QxwtzNE49WCgb6WPrdm5uTqSxDRbUtoi6Um4Y_BLTLw; __jda=143920055.17859894120541259424148.1785989412.1786003574.1786030402.4; __jdc=143920055; csn=26; __jdb=143920055.27.17859894120541259424148|4.1786030402"
all_cookie=[cookie1,cookie2,cookie3]
def get_cookie(cookie_string):
    cookies = []
    for item in cookie_string.split(";"):
        if "=" not in item:
            continue
        name, value = item.strip().split("=", 1)
        cookies.append({
            "name": name,
            "value": value,
            "domain": ".jd.com",
            "path": "/",
        })
    return cookies
page = ChromiumPage()
count = 1
for c in all_cookie[:3]:
    print(f"当前访问第{count}cookie值")
    count = count + 1
    page.set.cookies.clear()
    time.sleep(5)
    page.get("https://www.jd.com/")
    page.set.cookies(get_cookie(c))
    title = page.title
    print(title)
    if "验证" in page.title:
        print("✗ Cookie无效或需要验证")
    else:
        print("✓ Cookie有效,登录成功")
        page.get("https://home.jd.com/")
        page.wait.doc_loaded()
        time.sleep(5)
        break
product_urls=[
    "https://item.jd.com/100216521039.html?pcdk=XLnzDTEqal2vFlr9lcWWiHFb9QvtSsV_zmkhywbb332QWkLFzQkpYleUM2AMURx8.3z6a.aI3x&spmTag=YTAyMTkuYjAwMjM1Ni5jMDAwMDcxNjEuMSU0MDE3ODYwMzA0NDMxMzIlMjMxNzg1OTg5NDEyMDU0MTI1OTQyNDE0OCUyMzExMzM0NTc0NzQlMkNhMDI0MC5iMDAyNDkzLmMwMDAwNDAyNy4xJTIzc2t1X2NhcmQlNDAxNzg2MDM0NjAzMDQwJTIzMTc4NTk4OTQxMjA1NDEyNTk0MjQxNDglMjMyMzkxMDQ2NDU"]
for p_url in product_urls:
    page.get(p_url)
    time.sleep(5)
    title=page.ele('xpath://span[@class="sku-title-name"]').text
    print(title)
    price=page.ele('xpath://span[@class="product-price--value"]').text
    print(price)
    print(f"你关注的的商品{title}价格是{price}")
time.sleep(5)
idea_price=page.ele('xpath://span[@class="product-price--value"]').text
price = page.ele('xpath://span[@class="product-price--value"]').text
print(f'你关注的商品{title}的价格是{price}')
idea_price="25"
if price < idea_price:
 print("buy it")
 page.quit()
from DrissionPage import ChromiumPage
from serverchan_sdk import sc_send
from DrissionPage import ChromiumPage
from serverchan_sdk import sc_send
import os  # 新增导入

# ==================== 配置区 ====================
ideal_price = 4300
product_urls = [
    "https://item.jd.com/100359969926.html",
    "https://item.jd.com/100105522236.html",
    "https://item.jd.com/100257373973.html"
]
# ================================================
def run_price_check():
    page = ChromiumPage()
    alert_triggered = False  # 标记是否触发降价推送
    for p_url in product_urls:
        try:
            page.get(p_url)
            page.wait(10)
            # 获取产品标题
            title = page.ele('xpath://span[@class="sku-title-name"]').text
            # 获取产品价格
            price_text = page.ele('xpath://span[@class="product-price--value"]').text
            print(f'你关注的{title}的价格是{price_text}')

            # 修复：去除¥符号转数字
            clean_price = float(price_text.replace("¥", ""))
            if clean_price < ideal_price:
                print(f"【降价达标】{title}低于心理价，推送微信！")
                # 推送微信消息
                sc_send(
                    "SCT382432TAFggbULHnql1ToaCuqAaoWab",
                    f"你关注的{title}已降价",
                    f"现价：{clean_price}元\n点击立即购买{p_url}"
                )
                alert_triggered = True
                # 新增：生成停止标记文件
                with open("stop_signal.txt", "w", encoding="utf-8") as f:
                    f.write("stop")
                break  # 跳出商品循环，不用再检测剩下商品
            else:
                print("价格高于理想价格，暂不提醒")
        except Exception as e:
            print(f"检测链接{p_url}出错：{str(e)}")
    page.quit()
    # 返回标记给定时程序，用来判断是否停止定时
    return alert_triggered

# 新增：程序入口，运行脚本自动执行检测函数
if __name__ == "__main__":
    run_price_check()
    