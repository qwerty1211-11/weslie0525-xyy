import requests

kaiyangurl = ""

kaiyangheaders = {
    "user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
}
response = requests.get(url=kaiyangurl,headers=kaiyangheaders)
with open('天地龙鳞.mp3','wb') as f:
    f.write(response.content)