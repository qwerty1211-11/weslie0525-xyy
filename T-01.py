import requests
import m3u8
import os
import datetime
from moviepy import VideoFileClip, concatenate_videoclips
import re
# 1. 优酷请求头（注意：优酷反爬较严，建议从浏览器复制完整的 Cookie 和 Referer）
h = {  "user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "cookie":"enable_web_push=DISABLE; buvid_fp_plain=undefined; enable_feed_channel=ENABLE; theme-tip-show=SHOWED; theme-avatar-tip-show=SHOWED; PVID=5; theme-switch-show=SHOWED; header_theme_version=CLOSE; fingerprint=7fedc76bf197188d2cabe79eadca0600; buvid_fp=7fedc76bf197188d2cabe79eadca0600; buvid4=CAD6BA07-86F9-1432-9C30-C8B06F529EAC61107-023101618-idT5EiAh+lU7zPJ0HomyHA%3D%3D; _uuid=C8BCFC410-B9CF-3C5D-104EB-14E53EEF9C9B61464infoc; buvid3=852A9990-2632-8E04-5601-1C86BB64D08F33785infoc; b_nut=1763551033; rpdid=|(k))JRRJYkJ0J'u~YY~R)|~k; DedeUserID=433868327; DedeUserID__ckMd5=57bc77dabb9425a7; CURRENT_QUALITY=32; home_feed_column=5; bmg_af_switch=1; bmg_src_def_domain=i1.hdslb.com; bp_t_offset_433868327=1201133191109279744; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3Nzg5MTA0MTIsImlhdCI6MTc3ODY1MTE1MiwicGx0IjotMX0.ksyzQ561mXsL_R_psEmdYMLHA-I4lbSuaoL8-tDaPDU; bili_ticket_expires=1778910352; browser_resolution=2133-1021; SESSDATA=507a3835%2C1794221819%2Ca3506%2A51CjCr2NamOqVTJLl7okgvKmGtSdC3RLAdbz3pQgbOEnMevZbTz0J5Yf8thqNSxV1uDVcSVmtFRmZ3OUY5SkZlQjljRzRCcmlxMkNkQXJrSE1kNHZxclFYSWlqUG5icXBmc203RzNiWGpjbHR4VzVCUkZhVk11YnR5Rm1vZFpfN1Y2NldhMWNKYy1BIIEC; bili_jct=c32c0691fe9cf8e4768cd672851e5720; sid=8crlhdgi; CURRENT_FNVAL=4048; b_lsid=545AE1D8_19E2124712C",
    "referer":" https://www.youku.com/ku/webhome"}
# 2. 准备优酷视频链接列表
urllist = [
    "https://v.youku.com/v_show/id_XNjUwODIzMDk1Ng==.html",
]
# 3. 自动创建文件夹
dirpath = "优酷下载视频"
if not os.path.exists(dirpath):
    os.makedirs(dirpath)
# 4. 循环下载
count = 1
for url in urllist:
    print(f"开始下载第 {count} 个优酷视频...")
    count += 1
    try:
        # 获取视频页面源码
        res = requests.get(url=url, headers=h)
        html = res.text
        # 【核心改动】：通过正则提取优酷的 m3u8 视频流地址
        # 优酷的视频流通常包含在特定的 JSON 或 JS 变量中，这里用通用正则匹配
        m3u8_match = re.search(r'"m3u8_url":"(.*?)"', html)
        if not m3u8_match:
            print(f"第 {count - 1} 个视频解析失败，可能链接无效或需要VIP权限")
            continue
        m3u8_url = m3u8_match.group(1)
        # 解析 m3u8 获取所有的 ts 视频分段
        m3u8_obj = m3u8.load(m3u8_url)
        ts_segments = []
        # 下载所有的 ts 分段
        for i, segment in enumerate(m3u8_obj.segments):
            ts_url = segment.uri
            # 处理相对路径和绝对路径
            if not ts_url.startswith("http"):
                ts_url = m3u8_url.rsplit('/', 1)[0] + '/' + ts_url
            ts_res = requests.get(ts_url, headers=h)
            ts_filename = f"temp_seg_{i}.ts"
            with open(ts_filename, "wb") as f:
                f.write(ts_res.content)
            ts_segments.append(ts_filename)
            print(f"  已下载分段: {i + 1}/{len(m3u8_obj.segments)}")
        # 【合并逻辑】：使用 moviepy 合并分段
        clips = [VideoFileClip(ts) for ts in ts_segments]
        final_clip = concatenate_videoclips(clips)
        # 生成唯一时间戳作为文件名
        now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filepath = os.path.join(dirpath, f"{now}.mp4")
        final_clip.write_videofile(filepath, codec="libx264", audio_codec="aac")
        # 清理临时 ts 文件
        for ts in ts_segments:
            os.remove(ts)
        for clip in clips:
            clip.close()
        final_clip.close()
        print(f"第 {count - 1} 个视频下载合并完成！\n")
    except Exception as e:
        print(f"第 {count - 1} 个视频下载出错: {e}")
        from  DrissionPage import ChromiumPage
        page = ChromiumPage()
        page.get("https://v.youku.com/v_show/id_XNjUwODIzMDk1Ng==.html?spm=a2hkl.14919748_WEBHOME_HOME.loginrecord.d_text_0&scm=pc.history.toprecord.video_XNjUwODIzMDk1Ng%3D%3D&s=bdfca4ba5529478d9471")
