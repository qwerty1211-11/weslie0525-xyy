# python实现免费看VIP电影
import re
import tkinter as tk
import tkinter.messagebox as msgbox
import webbrowser


class App:
    # 编写图像化的界面，控制输入框窗口样式
    def __init__(self, width=1000, height=600):
        self.w = width
        self.h = height
        self.title = '播放视频'
        self.root = tk.Tk(className=self.title)
        self.url = tk.StringVar()
        self.v = tk.IntVar()
        self.v.set(1)
        frame_1 = tk.Frame(self.root)
        frame_2 = tk.Frame(self.root)
        group = tk.Label(frame_1, text='播放通道:', padx=10, pady=10)
        tb = tk.Radiobutton(frame_1, text='唯一通道', variable=self.v, value=1, width=10, height=10)
        label = tk.Label(frame_2, text='请输入视频播放地址:')
        entry = tk.Entry(frame_2, textvariable=self.url, highlightcolor='Fuchsia', highlightthickness=1, width=50)
        play = tk.Button(frame_2, text='播放', font=('楷体', 20), fg='Purple', width=10, height=10, command=self.video_play)
        frame_1.pack()
        frame_2.pack()
        group.grid(row=0, column=0)
        tb.grid(row=0, column=1)
        label.grid(row=0, column=0)
        entry.grid(row=0, column=1)
        play.grid(row=0, column=2, ipadx=10, ipady=10)

    # 解析VIP视频源，打开浏览器播放
    def video_play(self):
        link_url = "https://jx.m3u8.tv/jx/jx.php?url="
        if re.match(r'https?:/{2}\w.+$', self.url.get()):
            ip = self.url.get()
            play_url = link_url+ip
            webbrowser.open(play_url)
        else:
            msgbox.showerror(title='错误', message='视频地址无效，请检查....')

    # 运行程序
    def loop(self):
        self.root.mainloop()


if __name__ == '__main__':
    App().loop()
