import requests
url="https://www.baidu.com/index.php?tn=68018901_58_oem_dg"
response=requests.get(url)
print(response.text)
headers={"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"}
respones=requests.get(url)
print(respones.status_code)
with open("test.html","w",encoding="utf-8") as f:
    f.write("hello world")