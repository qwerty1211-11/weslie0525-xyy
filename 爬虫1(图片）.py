import requests
url="https://img0.baidu.com/it/u=2134081624,2495870578&fm=253&app=138&f=JPEG?w=800&h=802"
response=requests.get(url)
response.encoding="utf-8"
print("请求结果",response.text)
#测试======T========E========S=========T
headers={"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"}
print(response.content)
with open("xyy.jpg","wb")as f:
    f.write(response.content)

