import requests
from lxml import etree
import time

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"

}
cookie1="cud=c6fd19ccb304a45a81f38a0793109a20; __jdu=17859894120541259424148; PCSYCityID=CN_210000_211200_0; shshshfpa=05c14d7b-a4d1-90d4-c8d4-e8368d0e5f6b-1785989418; shshshfpx=05c14d7b-a4d1-90d4-c8d4-e8368d0e5f6b-1785989418; PCSYHWHR=1; areaId=0; ipLoc-djd=1-72-2799-0; thor=24E49124BA128F56B007818D89D5174F21959F2E5A3A44DEB825957A005653B2FE756B2C92A70407E861617AFE535E782B10B5D81415209C94DB8416148F4B2ADB535245B6CA1B2544B0BE1BAA010A96ED31EC809D92EED99EF9FB662C909AD35FAFB46270E0D743FBF3C8EF5CF2948A267E6003B5FB050E9E35A366EB30CA14550220447FB6BC9E554AF29533891CD90883FA7B0E0271AA28B31729F15DB905; light_key=AASBKE7rOxgWQziEhC_QY6yaKmn_Qwj41uF_3fjI8hBF9fS6cXKxkqJFVwYNBuIF3PL5DoSH; pinId=7u1Dd6Y9lGHGx3RL8p8NR7V9-x-f3wj7; pin=jd_53bcbb094d007; unick=jd_1oi6v9i9l5pgmr; _tp=zTKZdHPA2NWeZ731CiMjm7qmNj7Pc1ejtMNy0Y8hJiM%3D; _pst=jd_53bcbb094d007; __jdv=76161171%7Cbaidu%7C-%7Corganic%7Cnot%20set%7C1786003574272; cvt=3; umc_count=1; mail_times=4%2C2%2C1786030403759; cn=0; 3AB9D23F7A4B3C9B=B6EYDJXJKBCKIBXWQ5MDZHRQQFPUMRYI5C6PYJZJ4LQDJETUYSIKQQMQMY2SR3EUUJFL36KDNZ745WYLFFBVEGJKZM; 3AB9D23F7A4B3CSS=jdd03B6EYDJXJKBCKIBXWQ5MDZHRQQFPUMRYI5C6PYJZJ4LQDJETUYSIKQQMQMY2SR3EUUJFL36KDNZ745WYLFFBVEGJKZMAAAAM727AZELIAAAAADYNUQYKLFVS5QMX; shshshfpb=BApXWXDfJ1PpAN-NrVpZ-YHodgUE2yO6xBsfZkzdo9xJ1ItZfQtOFkBnpjnujZ4IjI-IX37WNsqFbIb9g7_xat9x6Mlrg_T5_kMrb; sdtoken=AAbEsBpEIOVjqTAKCQtvQu17V91wHMT8yj7-5OrJ4exL3z3FCfE8FzE96hO_VY6yOr7JtyTkSUSOw0nZhtfYNXdo60OeKzIbvb4E06DR2ujlLDEsEdkEulwD1zqHVJwaXmhIs3-RH1T4S7OSIqJyOI4O9dprQBEgtqbBS0MSenqf15q422Qk; flash=3_bQHzWQ1JR9tYVPY7DpUx98wuH3kJAXb--9ySeY8gSbKOk_F2Lrsm4M6soDYEZGUlL-oLVaTM2g7H3-yit14Zn03Xl7NyZRUn3v622tOhBMf0Te2HNJMAXMF4sVy9g4vfoHORy4CWJch6tBqnGV**; csn=14; __jda=143920055.17859894120541259424148.1785989412.1786003574.1786030402.4; __jdb=143920055.15.17859894120541259424148|4.1786030402; __jdc=143920055"
refer="https://www.zhihu.com/search?"
def get_cookie(cookie_string):
 chapters = [
    {
        "url": "/market/paid_column/1854572389167460352/section/1850313921166176256",
        "title": "高考前，我妈炖了我的兔子"
    }
]
 for idx, chapter in enumerate(chapters, 1):
    full_url = "https://www.zhihu.com" + chapter["url"]
    title = chapter["title"]
    print(f"正在下载：{title}")
    try:
        response = requests.get(full_url, headers=headers)
        response.raise_for_status()  # 检查 HTTP 错误
        response.encoding = "utf-8"
        html = etree.HTML(response.text)
        content_list = html.xpath('//div[contains(@class, "RichContent-inner")]//text')
        content = "\n".join([c.strip() for c in content_list if c.strip()])
        if not content:
            print(f"⚠️ 警告：未提取到内容，可能是页面结构变化或需要登录。")
            content = "未能提取到内容，请检查页面结构或登录状态。"
        safe_title = title.replace("/", "-").replace("\\", "-")
        with open(f"{safe_title}.txt", "w", encoding="utf-8") as f:
            f.write(title + "\n\n")
            f.write(content)
        print(f"✅ 第 {idx} 章下载完成")
    except requests.RequestException as e:
        print(f"❌ 下载失败：{e}")
    except Exception as e:
        print(f"❌ 发生未知错误：{e}")
    time.sleep(1)