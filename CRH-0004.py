# 导入内置标准库
import re
import tkinter as tk
# 正确导入弹窗模块messagebox
from tkinter import messagebox as msgbox
import webbrowser

class VideoParsePlayer:
    """视频解析播放GUI工具主类"""
    def __init__(self, width=1000, height=260):
        # 1. 基础窗口配置
        self.window_width = width
        self.window_height = height
        self.window_title = "视频解析播放器 - Python Tkinter"
        self.root = tk.Tk(className=self.window_title)
        # 设置窗口固定尺寸
        self.root.geometry(f"{self.window_width}x{self.window_height}")
        # 窗口禁止缩放
        self.root.resizable(False, False)

        # 2. 绑定控件变量
        self.input_url = tk.StringVar()  # 接收输入框视频地址
        self.channel_select = tk.IntVar() # 单选通道选择
        self.channel_select.set(1) # 默认选中唯一通道

        # 预编译正则表达式（仅执行一次，优化性能）
        self.url_pattern = re.compile(r'^https?://[A-Za-z0-9._~:/?#@!$&\'()*+,;=%-]+$')

        # 3. 划分布局Frame容器（分组管理控件）
        frame_channel = tk.Frame(self.root, pady=12)
        frame_input = tk.Frame(self.root, pady=8)

        # ========== 第一行：通道选择区域 ==========
        label_channel = tk.Label(frame_channel, text="播放通道：", font=("微软雅黑", 12), padx=10)
        radio_only = tk.Radiobutton(
            frame_channel,
            text="唯一解析通道",
            variable=self.channel_select,
            value=1,
            font=("微软雅黑", 11)
        )
        label_channel.grid(row=0, column=0)
        radio_only.grid(row=0, column=1, padx=20)

        # ========== 第二行：地址输入+播放按钮区域 ==========
        label_tip = tk.Label(frame_input, text="请粘贴视频原始地址：", font=("微软雅黑", 12))
        entry_url = tk.Entry(
            frame_input,
            textvariable=self.input_url,
            highlightcolor="Fuchsia", # 选中边框紫色
            highlightthickness=1,
            width=65,
            font=("微软雅黑", 11)
        )
        btn_play = tk.Button(
            frame_input,
            text="一键播放",
            font=("楷体", 18),
            fg="Purple",
            command=self.parse_and_play,
            padx=18,
            pady=4
        )
        label_tip.grid(row=0, column=0)
        entry_url.grid(row=0, column=1, padx=10)
        btn_play.grid(row=0, column=2)

        # 渲染两个容器到主窗口
        frame_channel.pack()
        frame_input.pack()

    def parse_and_play(self):
        """播放按钮点击触发核心逻辑：校验链接+拼接解析地址+打开浏览器"""
        raw_url = self.input_url.get().strip()
        # 判断输入为空
        if not raw_url:
            msgbox.showerror("输入错误", "输入框不能为空，请粘贴视频地址！")
            return
        # 正则校验URL格式
        if not self.url_pattern.match(raw_url):
            msgbox.showerror("地址格式错误", "链接必须以 http:// 或 https:// 开头，请检查链接！")
            return
        # 解析接口基础地址，移除多余引号空格
        parse_base = "https://www.pouyun.com/?url="
        final_play_url = parse_base + raw_url
        # 调用系统浏览器打开解析播放页面
        webbrowser.open(final_play_url)
        msgbox.showinfo("跳转成功", "已自动打开浏览器播放视频！")

    def run_window(self):
        """启动窗口消息循环"""
        self.root.mainloop()

# 程序入口
if __name__ == '__main__':
    app = VideoParsePlayer()
    app.run_window()
