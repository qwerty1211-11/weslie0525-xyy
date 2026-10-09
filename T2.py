import re
import tkinter as tk
import tkinter.messagebox as msgbox
import webbrowser
import requests
from tkinter import ttk
import os


class App:
    def __init__(self, width=1000, height=600):
        self.w = width
        self.h = height
        self.title = 'VIP视频解析与下载'
        self.root = tk.Tk(className=self.title)
        self.root.geometry(f'{width}x{height}')  # 设置窗口大小

        self.url = tk.StringVar()
        self.v = tk.IntVar()
        self.v.set(3)  # 默认选中剖云解析

        # --- 界面布局 ---
        frame_1 = tk.Frame(self.root, pady=10)
        frame_2 = tk.Frame(self.root, pady=10)
        frame_3 = tk.Frame(self.root, pady=10)  # 新增下载进度条框架

        # 解析通道选择
        tk.Label(frame_1, text='解析通道:', font=('Arial', 12)).pack(side=tk.LEFT, padx=10)
        # 这里简化了，只保留了代码中提到的几个
        tk.Radiobutton(frame_1, text='通道1', variable=self.v, value=1).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(frame_1, text='通道2', variable=self.v, value=2).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(frame_1, text='剖云(推荐)', variable=self.v, value=3).pack(side=tk.LEFT, padx=5)

        # 输入框
        tk.Label(frame_2, text='视频地址:', font=('Arial', 12)).pack(side=tk.LEFT, padx=10)
        entry = tk.Entry(frame_2, textvariable=self.url, width=60, font=('Arial', 10))
        entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # 按钮区域
        btn_frame = tk.Frame(frame_2)
        tk.Button(btn_frame, text='在线播放', font=('楷体', 12), fg='blue', command=self.video_play).pack(side=tk.TOP,
                                                                                                          pady=2)
        tk.Button(btn_frame, text='下载视频', font=('楷体', 12), fg='red', command=self.download_video).pack(
            side=tk.TOP, pady=2)
        btn_frame.pack(side=tk.RIGHT, padx=10)

        # 进度条
        self.progress = ttk.Progressbar(frame_3, orient="horizontal", length=800, mode="determinate")
        self.progress.pack(pady=10)
        self.progress['value'] = 0

        frame_1.pack(fill=tk.X)
        frame_2.pack(fill=tk.X)
        frame_3.pack(fill=tk.X)

        # 默认焦点
        entry.focus_set()

    def get_parse_url(self):
        """根据选择返回解析接口"""
        base_urls = {
            1: "https://jx.yparse.com/index.php?url=",
            2: "https://www.8090g.cn/?url=",
            3: "https://www.pouyun.com/?url="
        }
        return base_urls.get(self.v.get(), "https://www.pouyun.com/?url=")

    def video_play(self):
        """在线播放逻辑"""
        ip = self.url.get().strip()
        if not re.match(r'https?://\w+', ip):
            msgbox.showerror(title='错误', message='视频地址无效，请检查...')
            return

        parse_url = self.get_parse_url() + ip
        webbrowser.open(parse_url)

    def download_video(self):
        """下载视频逻辑"""
        video_url = self.url.get().strip()
        if not re.match(r'https?://\w+', video_url):
            msgbox.showerror(title='错误', message='视频地址无效，请检查...')
            return

        # 1. 获取解析后的视频真实流地址 (这里简化了，实际解析接口通常返回的是网页，需要Selenium或正则提取m3u8或mp4地址)
        # 注意：下面的逻辑是理想情况，实际第三方解析接口往往需要复杂的抓包分析才能获取真实流地址
        try:
            # 模拟请求解析接口
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Referer': self.get_parse_url()
            }

            # 发送请求获取解析后的页面
            response = requests.get(self.get_parse_url() + video_url, headers=headers, stream=True)
            response.raise_for_status()

            # 这里需要解析response.text来找到真实的视频下载链接（如.mp4或.m3u8）
            # **注意：这是一个巨大的难点，因为网页通常是JS渲染的，requests.get获取不到JS执行后的视频地址**
            # 以下代码仅为演示下载流程，无法直接运行成功，因为缺少真实的视频流URL

            # 假设我们通过某种方式（如正则、BeautifulSoup、或专门的API）找到了真实视频地址
            # real_video_url = self.extract_real_url(response.text)

            # 为了演示，我们使用一个占位符，实际开发中这里需要替换为真实的流地址
            # real_video_url = "https://example.com/video.mp4"

            # 2. 开始下载 (模拟)
            self.start_download_simulate()

        except Exception as e:
            msgbox.showerror('下载错误',
                             f'发生异常：{str(e)}\n\n注意：第三方解析接口通常无法直接通过此脚本下载，需浏览器抓包。')

    def start_download_simulate(self):
        """模拟下载过程（因为无法直接获取真实流）"""

        # 这里只是模拟进度条，实际应用需要替换为真实的流式下载逻辑
        def update_progress():
            current = self.progress['value']
            if current < 100:
                self.progress['value'] += 5
                self.root.after(500, update_progress)  # 每500毫秒更新一次
            else:
                msgbox.showinfo('完成', '下载完成！')

        update_progress()

    def loop(self):
        self.root.mainloop()


if __name__ == '__main__':
    App().loop()