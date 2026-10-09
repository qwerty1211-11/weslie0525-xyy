import requests
import re  # 正则的库，作用，匹配符合的字符串内容
from moviepy import VideoFileClip, AudioFileClip  # 合并的库安装 pip install moviepy
import os
import time

"""【讲解流程】
1. 分析视频真实链接来源
2. 定义url
3. 定义请求头
4. 发请求
5. 分析网站源码正则匹配目标网址
6. 提取音视频链接并保存本地
7. 读取音视频合并
"""


def downloadVideo(restext):
    # 【请求头】继续加权重伪装，
    h = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "cookie": "enable_web_push=DISABLE; buvid_fp_plain=undefined; enable_feed_channel=ENABLE; theme-tip-show=SHOWED; theme-avatar-tip-show=SHOWED; PVID=5; theme-switch-show=SHOWED; header_theme_version=CLOSE; fingerprint=7fedc76bf197188d2cabe79eadca0600; buvid_fp=7fedc76bf197188d2cabe79eadca0600; buvid4=CAD6BA07-86F9-1432-9C30-C8B06F529EAC61107-023101618-idT5EiAh+lU7zPJ0HomyHA%3D%3D; _uuid=C8BCFC410-B9CF-3C5D-104EB-14E53EEF9C9B61464infoc; buvid3=852A9990-2632-8E04-5601-1C86BB64D08F33785infoc; b_nut=1763551033; rpdid=|(k))JRRJYkJ0J'u~YY~R)|~k; DedeUserID=433868327; DedeUserID__ckMd5=57bc77dabb9425a7; CURRENT_QUALITY=32; home_feed_column=5; bmg_af_switch=1; bmg_src_def_domain=i1.hdslb.com; bp_t_offset_433868327=1201133191109279744; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Nzg5MTA0MTIsImlhdCI6MTc3ODY1MTE1MiwicGx0IjotMX0.ksyzQ561mXsL_R_psEmdYMLHA-I4lbSuaoL8-tDaPDU; bili_ticket_expires=1778910352; browser_resolution=2133-1021; SESSDATA=507a3835%2C1794221819%2Ca3506%2A51CjCr2NamOqVTJLl7okgvKmGtSdC3RLAdbz3pQgbOEnMevZbTz0J5Yf8thqNSxV1uDVcSVmtFRmZ3OUY5SkZlQjljRzRCcmlxMkNkQXJrSE1kNHZxclFYSWlqUG5icXBmc203RzNiWGpjbHR4VzVCUkZhVk11YnR5Rm1vZFpfN1Y2NldhMWNKYy1BIIEC; bili_jct=c32c0691fe9cf8e4768cd672851e5720; sid=8crlhdgi; CURRENT_FNVAL=4048; b_lsid=545AE1D8_19E2124712C",
        "referer": "https://www.douyin.com/user/self?from_tab_name=main&modal_id=7679444281648444627"
    }

    # 【提取视频标题】
    # 优先从 h1 标签提取
    title_match = re.findall(r'<h1[^>]*>(.*?)</h1>', restext, re.S)

    title = title_match[0].strip() if title_match else ""
    # B站 title 格式: "视频标题_哔哩哔哩_bilibili"，去掉后缀
    title = re.sub(r'[_-][bB]ilibili.*$', '', title)
    title = re.sub(r'[_\-]*哔哩哔哩.*$', '', title)

    # 对标题提纯取消特殊字符以及空格和标点符号
    title = re.sub(r'[\/:*?"<>|]', "", title)
    print(f"标题: {title}")

    # 【提取音视频链接】B站视频数据嵌在 <script> 的 window.__playinfo__ 中
    rule = r'"baseUrl":"(.+?)"'

    result = re.findall(rule, restext)

    # 【提取无声视频url】 result列表中的第一个就是视频的url
    videourl = result[0]

    # 【提取音频url】 result列表中的最后一个就是音频的url
    audiourl = result[-1]

    # 【创建视频目录】
    path = "视频文件"
    if not os.path.exists(path):
        os.makedirs(path)

    # 【下载无声视频】
    resvideo = requests.get(url=videourl, headers=h)
    # print(resvideo)
    # 【保存视频】
    with open(f"{path}/{title}.mp4", "wb") as f:
        f.write(resvideo.content)

    # 【下载保存音频】
    resaudio = requests.get(url=audiourl, headers=h)
    with open(f"{path}/{title}.mp3", "wb") as f:
        f.write(resaudio.content)

    # 【合并】现成的库，使用库合成
    # 1. 加载视频文件和音频文件
    video = VideoFileClip(f"{path}/{title}.mp4")
    audio = AudioFileClip(f"{path}/{title}.mp3")
    # 2. 将音频设置到视频上
    video = video.with_audio(audio)
    # 3. 导出合并后的视频
    video.write_videofile(f"{path}/{title}_merged.mp4")
    # 4. 关闭 clip 对象，释放文件句柄
    video.close()
    audio.close()
    time.sleep(1)
    print("合并成功")
    # 【删除源文件，重命名合并文件】
    os.remove(f"{path}/{title}.mp4")
    os.remove(f"{path}/{title}.mp3")
    os.rename(f"{path}/{title}_merged.mp4", f"{path}/{title}.mp4")











