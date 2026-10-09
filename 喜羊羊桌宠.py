import tkinter as tk
from PIL import Image, ImageTk
import time
import random

class XiMiaoMiaoPet:
    def __init__(self, root):
        self.root = root
        self.root.title("喜喵喵桌面宠物")
        # 窗口无边框、置顶、透明
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "#f0f0f0")
        self.root.overrideredirect(True)

        # 画布承载形象
        self.canvas = tk.Canvas(root, bg="#f0f0f0", width=300, height=320)
        self.canvas.pack()

        # 拖动变量
        self.drag_x = 0
        self.drag_y = 0
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<ButtonRelease-1>", self.stop_drag)
        self.canvas.bind("<B1-Motion>", self.do_drag)
        # 右键退出
        self.canvas.bind("<Button-3>", self.exit_pet)

        # 绘制猫化喜羊羊（矢量绘制还原图中形象）
        self.draw_ximiaomiao()
        # 待机动画循环
        self.anim_loop()

    def draw_ximiaomiao(self):
        c = self.canvas
        # 1. 背景浅蓝渐变底色
        c.create_oval(10, 10, 290, 310, fill="#b8e0f8", outline="#90c8ee", width=3)
        # 羊毛白色卷发轮廓
        c.create_ellipse(20, 10, 280, 240, fill="white", outline="#60a8e8", width=4)
        # 猫耳朵
        # 左耳
        c.create_polygon(30, 40, 90, 20, 80, 110, fill="#60b8f8", outline="#3088d8", width=3)
        c.create_polygon(40, 50, 80, 30, 75, 100, fill="#90d0ff")
        # 右耳
        c.create_polygon(270, 40, 210, 20, 220, 110, fill="#60b8f8", outline="#3088d8", width=3)
        c.create_polygon(260, 50, 220, 30, 225, 100, fill="#90d0ff")
        # 脸部肤色
        c.create_ellipse(60, 90, 240, 260, fill="#ffe8d0", outline="#f8a8b8", width=3)
        # 眉毛
        c.create_arc(80, 100, 140, 130, start=20, extent=140, fill="", outline="#402818", width=3)
        c.create_arc(160, 100, 220, 130, start=200, extent=140, fill="", outline="#402818", width=3)
        # 大眼睛
        # 左眼
        c.create_oval(70, 130, 155, 230, fill="white", outline="#2060c8", width=4)
        c.create_oval(80, 140, 145, 220, fill="#2058c0")
        c.create_oval(100, 150, 130, 180, fill="white")
        # 右眼
        c.create_oval(145, 130, 230, 230, fill="white", outline="#2060c8", width=4)
        c.create_oval(155, 140, 220, 220, fill="#2058c0")
        c.create_oval(175, 150, 205, 180, fill="white")
        # 鼻子
        c.create_oval(138, 190, 162, 212, fill="#302010")
        # 微笑嘴
        c.create_arc(120, 210, 180, 240, start=0, extent=180, fill="", outline="#e06090", width=2)
        # 腮红
        c.create_oval(65, 200, 105, 230, fill="#ffc8d8", outline="")
        c.create_oval(195, 200, 235, 230, fill="#ffc8d8", outline="")
        # 猫胡须
        # 左胡须
        c.create_line(40, 195, 90, 185, fill="#806070", width=2)
        c.create_line(35, 210, 95, 210, fill="#806070", width=2)
        c.create_line(40, 225, 90, 235, fill="#806070", width=2)
        # 右胡须
        c.create_line(260, 195, 210, 185, fill="#806070", width=2)
        c.create_line(265, 210, 205, 210, fill="#806070", width=2)
        c.create_line(260, 225, 210, 235, fill="#806070", width=2)
        # 身体羊毛
        c.create_ellipse(90, 230, 210, 300, fill="white", outline="#60a8e8", width=3)
        # 项圈
        c.create_rectangle(95, 240, 205, 265, fill="#4098e8", outline="#2068b8", width=2)
        # 铃铛
        c.create_oval(120, 245, 180, 300, fill="#ffc860", outline="#b06020", width=3)
        c.create_arc(135, 260, 165, 290, start=45, extent=270, fill="#b06020")
        # 猫尾巴（左侧）
        c.create_arc(20, 240, 100, 300, start=90, extent=220, fill="#60b8f8", outline="#3088d8", width=3)
        c.create_oval(30, 260, 60, 290, fill="white", outline="#3088d8", width=2)
        # 小鞋子
        c.create_oval(110, 290, 145, 315, fill="#60b8f8", outline="#2068b8", width=2)
        c.create_oval(155, 290, 190, 315, fill="#60b8f8", outline="#2068b8", width=2)
        c.create_oval(115, 295, 140, 310, fill="white")
        c.create_oval(160, 295, 185, 310, fill="white")

    # 拖动窗口逻辑
    def start_drag(self, event):
        self.drag_x = event.x
        self.drag_y = event.y

    def stop_drag(self, event):
        self.drag_x = 0
        self.drag_y = 0

    def do_drag(self, event):
        dx = event.x - self.drag_x
        dy = event.y - self.drag_y
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")

    # 右键退出
    def exit_pet(self, event):
        self.root.destroy()

    # 简易待机动画（轻微上下浮动）
    def anim_loop(self):
        offset = random.randint(-3, 3)
        x = self.root.winfo_x()
        y = self.root.winfo_y() + offset
        self.root.geometry(f"+{x}+{y}")
        self.root.after(800, self.anim_loop)

if __name__ == "__main__":
    window = tk.Tk()
    pet = XiMiaoMiaoPet(window)
    # 初始窗口位置
    window.geometry("300x320+1000+500")
    window.mainloop()