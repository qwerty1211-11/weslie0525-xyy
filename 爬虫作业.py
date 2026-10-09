import json
json_str = '{"name": "张三", "age": 18}'
data = json.loads(json_str)
print(data["name"])
import requests
url="https://webfs.kugou.com/202607141706/cf58f4ad071ff0fb808341972033d5aa/v3/1eeb86c9065dd23480a53fc3340b8629/yp/p_0_960119/ap1014_us1953311369_mii0w1iw8z2ai2iphcu80ooo2ki81120_pi406_mx268299519_s574962613.mp3"
response = requests.get(url)
with open("song.mp3", "wb") as f:
    f.write(response.content)
    