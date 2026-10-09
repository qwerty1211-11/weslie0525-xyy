import re
import tkinter as tk
import tkinter.messagebox as msgbox
import webbrowser
import requests
import os
from threading import Thread
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


class VideoDownloaderApp:
    def __init__(self, width=1000, height=600):
        self.root = tk.Tk(className='VIP视频解析与下载器')
        self.url = tk.StringVar()
        self.v = tk.IntVar(value=1)

        # 窗口设置
        self.root.geometry(f"{width}x{height}+200+50")
        self.root.resizable(False, False)

        # --- 界面布局 ---
        # 1. 通道选择区
        frame_1 = tk.Frame(self.root)
        tk.Label(frame_1, text='播放通道:', padx=10, pady=10).pack(side=tk.LEFT)
        tk.Radiobutton(frame_1, text='唯一通道', variable=self.v, value=1).pack(side=tk.LEFT)
        frame_1.pack(pady=10)

        # 2. 输入与操作区
        frame_2 = tk.Frame(self.root)
        tk.Label(frame_2, text='请输入视频播放地址:').grid(row=0, column=0, padx=5, pady=5)
        tk.Entry(frame_2, textvariable=self.url, width=50, highlightcolor='Fuchsia', highlightthickness=1).grid(row=0,
                                                                                                                column=1,
                                                                                                                padx=5,
                                                                                                                pady=5)

        # 按钮：播放 (调用浏览器)
        tk.Button(frame_2, text='在线播放', font=('楷体', 12), fg='Purple', width=10, command=self.video_play).grid(
            row=0, column=2, padx=10, pady=10)

        # 按钮：下载 (调用Selenium+Requests)
        tk.Button(frame_2, text='解析下载', font=('楷体', 12), fg='Green', width=10, command=self.start_download).grid(
            row=0, column=3, padx=10, pady=10)

        frame_2.pack(pady=10)

        # 3. 状态显示区
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(self.root, textvariable=self.status_var, fg="gray", font=("Consolas", 10)).pack(side=tk.BOTTOM,
                                                                                                 fill=tk.X)

    def is_valid_url(self, url):
        """简单验证URL格式"""
        return re.match(r'^https?://\S+', url) is not None

    def video_play(self):
        """在线播放：直接拼接URL在浏览器打开"""
        parse_url = "https://www.pouyun.com/?url="
        input_url = self.url.get().strip()

        if self.is_valid_url(input_url):
            webbrowser.open(parse_url + input_url)
        else:
            msgbox.showerror('错误', '视频地址无效，请检查...')

    def get_video_src_by_selenium(self, page_url: str, wait_time: int = 20):
        """Selenium 启动浏览器，等待video加载，JS获取src真实地址"""
        chrome_options = webdriver.ChromeOptions()

        # --- 关键配置：无头模式 (不弹出浏览器窗口) ---
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        driver = None
        try:
            # 自动管理驱动
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            driver.get(page_url)
            self.status_var.set("正在解析视频真实地址 (1/3)...")

            # 等待视频标签出现
            wait = WebDriverWait(driver, wait_time)
            video_elem = wait.until(EC.presence_of_element_located((By.TAG_NAME, "video")))

            # 执行JS获取真实地址
            js_script = """
            let video = document.querySelector('video');
            function waitSrc(){
                return new Promise(resolve=>{
                    let timer = setInterval(()=>{
                        if(video.currentSrc && video.currentSrc !== ""){
                            clearInterval(timer);
                            resolve(video.currentSrc);
                        }
                    },500)
                })
            }
            return await waitSrc();
            """
            real_url = driver.execute_async_script(js_script)
            self.status_var.set(f"解析成功，准备下载 (2/3)...")
            return real_url

        except Exception as err:
            self.status_var.set("解析失败")
            print(f"解析错误: {err}")
            return None
        finally:
            if driver:
                driver.quit()

    def download_video(self, video_url: str, save_path: str):
        """requests 流式下载视频"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.pouyun.com/"
        }

        try:
            resp = requests.get(video_url, headers=headers, stream=True, timeout=30)
            resp.raise_for_status()
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # 更新进度
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            self.status_var.set(
                                f"下载中... {downloaded / 1024 / 1024:.1f}MB / {total_size / 1024 / 1024:.1f}MB ({progress:.1f}%)")

            self.status_var.set(f"下载完成: {os.path.abspath(save_path)}")
            msgbox.showinfo("成功", f"视频已保存至:\n{save_path}")

        except Exception as e:
            self.status_var.set("下载失败")
            msgbox.showerror("错误", f"下载失败: {str(e)}")

    def start_download(self):
        """启动下载线程 (防止界面卡死)"""
        input_url = self.url.get().strip()
        if not self.is_valid_url(input_url):
            msgbox.showerror('错误', '视频地址无效，请检查...')
            return

        # 确认解析网站 (这里固定使用之前的 pouyun)
        parse_url = "https://www.pouyun.com/?url=" + input_url

        # 获取文件名 (基于时间戳或域名)
        from urllib.parse import urlparse
        parsed_uri = urlparse(input_url)
        domain = parsed_uri.netloc.replace("www.", "")
        filename = f"{domain}_video.mp4"

        # 在新线程中执行耗时操作，避免阻塞UI
        def worker():
            real_link = self.get_video_src_by_selenium(parse_url)
            if real_link:
                self.download_video(real_link, filename)
            else:
                self.status_var.set("就绪")
                msgbox.showerror("错误", "无法获取视频真实地址，请检查链接或更换解析接口。")

        Thread(target=worker, daemon=True).start()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = VideoDownloaderApp()
    app.run()
    #https://www.pouyun.com/