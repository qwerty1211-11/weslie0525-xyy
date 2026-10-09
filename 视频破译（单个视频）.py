
import requests
import re
from moviepy import VideoFileClip  #我们不需要这个库的所有内容，只需要其中的合并视频功能
#准备url
kaiyangurl='https://www.bilibili.com/video/BV1pXJA6AEaC/?spm_id_from=333.337.search-card.all.click&vd_source=513740106383589134a741139796a91d'

#先给大家完善一下headers---目的是模拟浏览器
#user-agent--相当于给你的爬虫穿了衣服，你就不是裸奔的爬虫程序
#referer--保安还要问你，从哪儿进来的
#cookie--相当于你的电影票，标明你的身份（跟你的浏览器有关系，跟你登录没登录会员有关系）
kaiyangheaders = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "cookie":'''buvid3=35BE4CB3-7A15-6056-C7C5-83666915ED8706060infoc; b_nut=1765867406; _uuid=B72DAB55-C813-210CA-FE78-DAD2342641010D03402infoc; buvid4=FBD8F333-A45B-F159-BEBE-C17340F1623037890-025050913-didLSFOXKs1MHKASYY3JFw%3D%3D; buvid_fp=e943a9638de629d3142c5fa0e606c423; theme-tip-show=SHOWED; rpdid=|(k))JRRJYkJ0J'u~Yl))|k~R; theme-avatar-tip-show=SHOWED; CURRENT_QUALITY=0; hit-dyn-v2=1; PVID=1; LIVE_BUVID=AUTO4517697717305113; theme-switch-show=SHOWED; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODQxOTAzODEsImlhdCI6MTc4MzkzMTEyMSwicGx0IjotMX0.RlUEjil_olYMz5Y1S3ql3489yxf-4cJwLBbGEX0YYhc; bili_ticket_expires=1784190321; bp_t_offset_532992441=1224464187900559360; bp_t_offset_374295422=1224469663983861760; bmg_af_switch=1; bmg_src_def_domain=i0.hdslb.com; bmg_af_sc={"none":{"on":1,"def":"i0.hdslb.com"},"sgp":{"on":1,"def":"i0-sgp.hdslb.com"}}; home_feed_column=5; browser_resolution=1920-911; bp_t_offset_3707011363506455=1224853599700385792; SESSDATA=17891ee4%2C1799573883%2C7b536%2A71CjDmDSrcUJLdHHTa94LI7xgQX6NVxU0tRUk83eZfW8n6bVngvI6YK5WFJzFXH0ogAicSVnVueWMwbFFrajFQeWhhb3VVcnpUVTY2R3FOYkNYUEJVbjllVmdxS0tPTWpwbUdEYXY5WEN4QkJHVG0zSmFMZk5NWFlYX2Q4X1ZzRzRoUEttc21VSVNRIIEC; bili_jct=a8dd4e6c736c8ffc210a97548e7a20f4; DedeUserID=532992441; DedeUserID__ckMd5=8dd3ee78c0568fa2; sid=5u1v5hof; CURRENT_FNVAL=4048; b_lsid=3F2ACEC8_19F607AFE49''',
    "referer":"https://search.bilibili.com/all?keyword=%E9%80%8D%E9%81%A5%E4%BB%99&from_source=webhistory_search&spm_id_from=333.1007&search_source=3&order=click"
}

#发送请求
response = requests.get(url=kaiyangurl,headers=kaiyangheaders)
#按理说，这个里面应该包含了我们所有需要的内容，我们只需要提取内容就可以了。
# print(response.text)

#接着我们要去找刚才的音频文件和视频文件
#提取的内容比较复杂 xpath通过一个一个的标签名找到的 div span[@id=id名]
#可以使用json，但是如果json嵌套的非常深，也有点麻烦
#直接提取内容---正则表达式：从字符串当中，提取某种具体格式的内容
gz = r'"baseUrl":"(.+?)"'  #我已经把规则定清楚了，就baseUrl:"  "
urls = re.findall(gz,response.text)
# print(urls)
#从这一堆里面提取一下视频地址和音频地址
#视频地址
videourl = urls[0]
#音频地址
audiourl = urls[-1]

#有了地址 下载就可以了
videofile = requests.get(url=videourl,headers=kaiyangheaders)
with open('video.mp4','wb') as f:
    print('正在下载视频文件......')
    f.write(videofile.content)

#有了地址 下载就可以了
audiofile = requests.get(url=audiourl,headers=kaiyangheaders)
with open('audio.mp3','wb') as f:
    print('正在下载音频文件......')
    f.write(audiofile.content)

#合并视频，只需要两行代码就搞定，但是需要学一个新的库 moviepy ---pip install moviepy
#先把内容读取进来
video = VideoFileClip('video.mp4')
#写出一个全新的文件，并且把mp3合并进去
video.write_videofile('逍遥仙.mp4',audio='audio.mp3')

#这节课是一个下载的课程，不要再说剪映了。因为B站有音视频分离，所以才说了一个合并音视频

#稍微的完善一下，把该删除的文件删一删,考虑内存和性能的问题。
import os  #这是一个操作系统的库，可以创建文件夹，可以删除文件
os.remove('video.mp4')
os.remove('audio.mp3')
os.makedirs('B站视频')
