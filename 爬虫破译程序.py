import requests
url="https://vali-g1.cp31.ott.cibntv.net/youku/6910-3232416409254262648922626489221256/03000801006A1E3804127915DD42DEC0A7FB37-FBCD-4EA9-B00E-AFBC168071F6.mp4?sid=178403088900010006650_00_Bc6d1488fb2a68107735d916a7e9178b2&sign=8a581e53bb82385c860cf2c8b384c2ba&ctype=50"
header={"user+agent":"Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Mobile Safari/537.36"}
respone=requests.get(url,headers=header)
print(respone.text)
with open("test.mp4","wb") as f:
    f.write(respone.content)
import re
import tkinter as tk
import tkinter.messagebox as msgbox
import webbrowser
import os
import subprocess
import requests
import threading
class App:
    def __init__(self, width=1000, height=600):
        self.w = width
        self.h = height
        self.title = '视频解析播放+下载工具'
        self.root = tk.Tk(className=self.title)
        self.root.geometry(f"{self.w}x{self.h}")
        self.url = tk.StringVar()
        # 三个解析通道
        self.v = tk.IntVar()
        self.v.set(1)
        self.channel_list = [
            ("通道1(带广告)", "https://jx.yparse.com/index.php?url="),
            ("通道2(无广告)", "shturl.cc/zMbEgfcmTaTOrHw2"),
            ("通道3(云解析)", "https://www.pouyun.com/?url=")
        ]

        # 通道选择区域
        frame_1 = tk.Frame(self.root, pady=10)
        frame_1.pack(fill="x")
        group = tk.Label(frame_1, text='播放通道选择:', font=("黑体", 12), padx=10)
        group.pack(side="left")
        for idx, (name, _) in enumerate(self.channel_list, start=1):
            rb = tk.Radiobutton(frame_1, text=name, variable=self.v, value=idx, font=("宋体", 10))
            rb.pack(side="left", padx=15)

        # 输入框+功能按钮区域
        frame_2 = tk.Frame(self.root, pady=30)
        frame_2.pack()
        label = tk.Label(frame_2, text='请输入视频网页地址:', font=("黑体", 12))
        label.grid(row=0, column=0, padx=5)
        entry = tk.Entry(frame_2, textvariable=self.url, highlightcolor='Fuchsia', highlightthickness=1, width=60, font=("宋体", 11))
        entry.grid(row=0, column=1, padx=10)

        play_btn = tk.Button(frame_2, text='在线播放', font=('楷体', 12), fg='Purple', width=10, command=self.video_play)
        play_btn.grid(row=0, column=2, padx=8)

        download_btn = tk.Button(frame_2, text='下载视频', font=('楷体', 12), fg='green', width=10, command=self.start_download_thread)
        download_btn.grid(row=0, column=3, padx=8)

        # 进度显示文本框
        tk.Label(self.root, text="下载日志：", font=("黑体",11)).pack()
        self.log_text = tk.Text(self.root, width=120, height=20)
        self.log_text.pack(padx=10)

    # 获取当前选中通道链接前缀
    def get_api_url(self):
        idx = self.v.get() - 1
        return self.channel_list[idx][1]

    # 在线播放功能
    def video_play(self):
        raw_link = self.url.get().strip()
        if not re.match(r'https?:/{2}\w.+$', raw_link):
            msgbox.showerror('错误', '视频地址无效，请检查链接！')
            return
        api = self.get_api_url()
        play_url = api + raw_link
        webbrowser.open(play_url)
        self.write_log(f"打开播放页面：{play_url}")

    # 日志输出到文本框
    def write_log(self, text):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    # 流式下载函数，捕获权限、网络异常
    def stream_download(self, mp4_url, save_name="video.mp4"):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        }
        try:
            self.write_log(f"开始解析下载链接：{mp4_url}")
            res = requests.get(mp4_url, headers=headers, stream=True, timeout=30)
            res.raise_for_status()
            total_size = int(res.headers.get("content-length", 0))
            downloaded = 0

            with open(save_name, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            self.write_log(f"下载进度：{progress:.2f}%")
            self.write_log(f"✅ 下载完成！保存文件名：{save_name}")
            msgbox.showinfo("完成", f"视频已下载至程序目录：{save_name}")
        except PermissionError:
            err_msg = "❌ 权限错误：无法写入文件，请关闭占用文件/更换保存文件夹/以管理员运行程序！"
            self.write_log(err_msg)
            msgbox.showerror("权限报错", err_msg)
        except requests.exceptions.RequestException as e:
            err_msg = f"❌ 网络链接错误：{str(e)}"
            self.write_log(err_msg)
            msgbox.showerror("链接错误", "无法访问视频链接，链接失效或网络异常")
        except Exception as e:
            err_msg = f"❌ 未知错误：{str(e)}"
            self.write_log(err_msg)

    # 使用yt-dlp解析网页真实视频直链
    def get_real_video_url(self, web_url):
        try:
            # 调用yt-dlp获取第一条视频直链
            cmd = ["yt-dlp", "-g", web_url]
            result = subprocess.check_output(cmd, encoding="utf-8", timeout=60)
            real_link = result.strip().split("\n")[0]
            return real_link
        except subprocess.CalledProcessError:
            self.write_log("yt-dlp解析失败，当前网站不支持直接下载")
            return None
        except FileNotFoundError:
            self.write_log("未检测到yt-dlp工具，请先执行安装：pip install yt-dlp")
            msgbox.showerror("缺少依赖", "请打开命令行执行 pip install yt-dlp 后重启程序")
            return None

    # 多线程下载（防止界面卡死）
    def start_download_thread(self):
        def download_task():
            raw_link = self.url.get().strip()
            if not re.match(r'https?:/{2}\w.+$', raw_link):
                msgbox.showerror('错误', '视频地址无效，请检查链接！')
                return
            self.write_log("正在解析真实视频地址...")
            real_mp4 = self.get_real_video_url(raw_link)
            if not real_mp4:
                return
            self.stream_download(real_mp4)
        # 新建线程执行下载，不阻塞GUI
        t = threading.Thread(target=download_task, daemon=True)
        t.start()

    def loop(self):
        self.root.mainloop()

if __name__ == '__main__':
    App().loop()

