import requests
import json
import time
import random
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Referer": "https://www.kugou.com/mixsong/n1fyjd6.html?fromsearch=%E7%BE%8A%E7%BE%8A%E9%A1%B6%E5%91%B1%E5%91%B1"}
url = "https://wwwapi.kugou.com/play/songinfo?srcappid=2919&clientver=20000&clienttime=1783948152648&mid=758cb2f58a908c5d4e82a711fc882c60&uuid=758cb2f58a908c5d4e82a711fc882c60&dfid=0jLPeU0IFDkI0z1QTX2gf8KD&appid=1014&platid=4&encode_album_audio_id=n1fyjd6&token=5125397b0529dd2e452ddba134b7c796a1828dfac8d2463298573b6c9bf85529&userid=1560592175&signature=6e0dd15a935a6294f06b01b992d1f197'"
try:
    resp = requests.get(url, headers=headers)
    k=random.randint(1,15)
    time.sleep(k)
    print("响应状态码：", resp.status_code)
    content = resp.text.strip()
    print("接口返回前500字符：\n", content[:500])
    if not content:
        print(" 服务器返回空白内容，接口拦截/参数缺失")
    elif content.startswith(("callback(", "jsonp(")):
        start = content.find("(") + 1
        end = content.rfind(")")
        json_str = content[start:end]
        data = json.loads(json_str)
        print("✅ JSONP解析成功", data)
    else:
        data = json.loads(content)
        print("✅ JSON解析成功", data)
except requests.exceptions.ConnectionError:
    print(" 域名无法访问，接口地址错误或网络异常")
except json.JSONDecodeError:
    print(" 返回不是合法JSON，接口被拦截！")
except Exception as e:
    print("程序异常：", e)