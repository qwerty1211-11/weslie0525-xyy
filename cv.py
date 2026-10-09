import subprocess
import os

def youku_download(url, save_path="./youku"):
    os.makedirs(save_path, exist_ok=True)
    cmd = [
        "you-get",
        "-o", save_path,
        url
    ]
    try:
        subprocess.run(cmd, check=True)
        print("下载完成")
    except Exception as e:
        print("解析失败，该视频为加密版权内容")

if __name__ == '__main__':
    link = "https://v.youku.com/v_show/id_XNjUzNzM0MjQxMg==.html?s=daaba22c08db44dbb58c&scm=20140719.apircmd.298647.video_XNjUzNzM0MjQxMg==&spm=a2hkt.13141534.298647.d_39_11"
    youku_download(link)