from Demos.win32cred_demo import username

heros=[{ "喜羊羊": ("，我一定能想出办法！", "普通"),
    "灰太狼": ("我一定会回来的！", "经典稀有"),
    "美羊羊": ("哇，好漂亮呀～", "普通"),
    "懒羊羊": ("我要吃青草蛋糕！", "普通"),
    "沸羊羊": ("我是最强的！", "普通"),
    "慢羊羊": ("年轻人，做事要慢慢来啊。", "普通"),
    "红太狼": ("灰太狼！抓不到羊就别回来！", "经典稀有"),
    "小灰灰": ("爸爸，我们一起和小羊做朋友吧", "稀有"),
    "蕉太狼": ("香蕉才是世界上最好吃的东西！", "稀有"),
    "暖羊羊": ("大家有困难我都会帮忙的！", "普通"),
    "冰冰羊": ("哥哥，我们一起玩！", "稀有"),
        "小灰灰": ("爸爸，我们一起和小羊做朋友吧", "稀有"),}]
import random
import time
import os
# 喜灰角色卡池：键=角色名，值=(台词, 稀有度)#绿色区域台词可以自行更改
card_pool = {
    "喜羊羊": ("，我一定能想出办法！", "普通"),
    "灰太狼": ("我一定会回来的！", "经典稀有"),
    "美羊羊": ("哇，好漂亮呀～", "普通"),
    "懒羊羊": ("我要吃青草蛋糕！", "普通"),
    "沸羊羊": ("我是最强的！", "普通"),
    "慢羊羊": ("年轻人，做事要慢慢来啊。", "普通"),
    "红太狼": ("灰太狼！抓不到羊就别回来！", "经典稀有"),
    "小灰灰": ("爸爸，我们一起和小羊做朋友吧", "稀有"),
    "蕉太狼": ("香蕉才是世界上最好吃的东西！", "稀有"),
    "暖羊羊": ("大家有困难我都会帮忙的！", "普通"),
    "冰冰羊": ("哥哥，我们一起玩！", "稀有"),
    "小灰灰": ("爸爸不许欺负小羊！", "稀有"),}
print(heros["喜羊羊"])
del heros["喜羊羊"]
print(heros)
def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")
# 抽卡滚动动画
def draw_animation():
    roll_names = list(card_pool.keys())
    print("=====抽卡中=====")
    for _ in range(12):
        temp = random.choice(roll_names)
        print(f"\r【{temp}】", end="")
        time.sleep(0.08)
    print("\r", end="")
    print("================\n")
def single_draw():
    clear_screen()
    print("=========喜灰抽卡系统启动 =========")
    time.sleep(0.5)
    draw_animation()
    # 随机抽取角色
    role_name = random.choice(list(card_pool.keys()))
    line, rare = card_pool[role_name]
    # 稀有度配色文字（控制台标识）
    rare_color = ""
    if rare == "典藏":
        rare_color = "★典藏★"
    elif rare == "经典稀有":
        rare_color = "◆经典稀有◆"
    elif rare == "稀有":
        rare_color = "◇稀有◇"
    else:
        rare_color = "普通"
    # 展示抽卡结果+闪现台词
    print(f"抽到角色：【{role_name}】 | {rare_color}")
    print("-" * 40)
    # 台词闪现效果：停顿一下再弹出
    time.sleep(0.6)
    print(f"角色台词：「{line}」")
    print("-" * 40)
# 主程序循环
def main():
    while True:
        print("\n1. 单抽一次")
        print("2. 退出抽卡系统")
        select = input("\n请输入你的选择：")
        if select == "1":
            single_draw()
        elif select == "2":
            clear_screen()
            print("抽卡程序关闭，下次再来抽小羊吧！")
            break
        else:
            clear_screen()
            print("输入错误，请重新选择！")
            time.sleep(1)
            clear_screen()

if __name__ == "__main__":
    main()
with open("抽卡。txt","a",encoding="utf-8")as f:
    f.write(str(card_pool))
    print()
