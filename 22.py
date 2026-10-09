import tkinter as tk

from click import command

from deep_explore import l

tk.Tk()
window = tk.Tk()
window.title("老师来了摸鱼神器")
window.geometry("300x300")
tk.Label(window,text="距离下次巡逻：27：40",font=("微软雅黑",14),command=start_fish).pack(pady=20)
def start_fish():
 l.config(text="倒计时启动")
 def end_fish():
  l.config(text="倒计时结束")
btn_start=tk.Buttonon(window,text="开始摸鱼")
btn_start.pack()
btn_end=tk.Button(window,text="我不摸了")
btn_end.pack()
window.mainloop()


