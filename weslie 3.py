#新手村环节
IQ=0
money=0
health=0
sex=""
name=""
def fuhua():
    global IQ,money,health
sex=input("enter your sex")
name=input("enter your name")
import random
IQ=random.randint(1,10)
money=random.randint(1,10)
health=random.randint(1,10)
sex=random.randint(1,10)
print(f"your IQ is {IQ},your sex is {sex},your money is {money},your health is {health},yourname is {name}")
while True:
    fuhua()
    choice=input("你是否满意当前的角色")
    if choice =="666":
        print("\n确认角色，开启冒险")
        break
    else:
        print("\n角色重新生成中")
        import time
        time.sleep(1)
suiji=random.randint(1,3)
if suiji==1:
    print(f"文曲星托梦，大脑大力开发，智力加10，当前智力{IQ}")
elif suiji==2:
    health+=6
    print(f"被老喜猫猫发掘，，健康加6，当前健康{health}")
elif suiji==3:
    health-=6
    print(f"过度学习，你处死了，健康*0，当前健康{health}")
#成长期（7-18)
print("\n=====人生模拟器：7-18（成长期）=========")
#出门捡钱，是否选择捡起，属性的变化+1，+2，+3

for i in range(7,19):
 print(f"\n,今年你{i}岁")
shujian=random.choice(f"\n,今年你{i}岁")
print(f"\n,今年你{i}岁")
shijiankey,shijianvalue=next(iter(shujian.items()))
print (f"你触发了事件{shijianvalue}")
if choice =="1":
        money=money+shijianvalue[0]
        IQ=IQ+shijianvalue[30]
        health=health+shijianvalue[90]
elif choice =="2":
    money = money - shijianvalue[0]
    IQ = IQ -shijianvalue[30]
    health = health - shijianvalue[90]
cy=input("是否选择创业")
if cy =="1":
    CY=("选择创页，打工")
money+=9
IQ-=10
money = money + shijianvalue[0]
IQ = IQ + shijianvalue[30]
health = health + shijianvalue[90]
import random
import time
#charter setting
CHARACTERS = {
    "喜羊羊": {"智慧": 90, "体力": 80, "运气": 85, "性格": "勇敢机智"},
    "懒羊羊": {"智慧": 60, "体力": 50, "运气": 95, "性格": "贪吃嗜睡"},
    "沸羊羊": {"智慧": 70, "体力": 95, "运气": 60, "性格": "冲动鲁莽"},
    "美羊羊": {"智慧": 80, "体力": 70, "运气": 80, "性格": "爱美爱打扮"},
    "暖羊羊": {"智慧": 85, "体力": 75, "运气": 75, "性格": "温柔善良"},
    "灰太狼": {"智慧": 95, "体力": 85, "运气": 40, "性格": "倒霉但执着"},
    "红太狼": {"智慧": 80, "体力": 90, "运气": 70, "性格": "暴躁但护家"}
}

# dicter
EVENTS = [
    {"text": "你在草原上散步，不小心踩到了灰太狼的捕兽夹！", "stats": {"体力": -20, "运气": -10}, "type": "bad"},
    {"text": "你意外发现了慢羊羊村长藏起来的超级青草蛋糕，吃得很开心！", "stats": {"体力": 15, "智慧": 5},
     "type": "good"},
    {"text": "灰太狼又发明了新机器来抓你，但你用智慧轻松化解了危机！", "stats": {"智慧": 20, "运气": 10}, "type": "good"},
    {"text": "你被灰太狼抓回了狼堡，在平底锅的威胁下艰难逃脱。", "stats": {"体力": -30, "运气": -15}, "type": "bad"},
    {"text": "村长给你颁发了一枚‘草原守护勋章’，大家都很崇拜你！", "stats": {"智慧": 15, "运气": 20}, "type": "good"},
    {"text": "你在河边钓鱼时，钓上来一个装满金币的宝箱！", "stats": {"运气": 25}, "type": "good"},
    {"text": "你不小心吃了懒羊羊留下的毒蘑菇，在床上躺了三天。", "stats": {"体力": -25, "运气": -10}, "type": "bad"},
    {"text": "你帮助美羊羊找到了丢失的蝴蝶结，她对你非常感激！", "stats": {"运气": 15, "智慧": 5}, "type": "good"},
    {"text": "灰太狼的火箭筒炸膛了，你在一旁看笑话时不小心被熏黑了脸。", "stats": {"体力": -10, "运气": -5},
     "type": "bad"},
    {"text": "你成功研发出一种新型防狼喷雾，青青草原的安全指数上升！", "stats": {"智慧": 25, "运气": 15}, "type": "good"}
]


def print_slow(text, delay=0.03):
    """打字机效果输出"""
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print()


def start_simulation():
    print_slow(" 欢迎来到【人生模拟器】 ")
    print_slow("=========================================")

    # 随机抽取角色
    char_name = random.choice(list(CHARACTERS.keys()))
    char_stats = CHARACTERS[char_name].copy()

    print_slow(f"\n🎲 命运之轮转动，你转生成为了：【{char_name}】")
    print_slow(f"📜 性格标签：{char_stats.pop('性格')}")
    print_slow(f"📊 初始属性：智慧 {char_stats['智慧']} | 体力 {char_stats['体力']} | 运气 {char_stats['运气']}")
    print_slow("\n⏳ 你的青青草原人生，现在开始...")
    time.sleep(1)

    age = 0
    max_age = random.randint(6, 10)  # 随机经历 6-10 个事件

    while age < max_age and char_stats['体力'] > 0:
        age += 1
        print_slow(f"\n--- 第 {age} 年 ---")

        # 随机抽取事件
        event = random.choice(EVENTS)
        print_slow(f"📢 {event['text']}")

        # 结算属性
        for stat, change in event['stats'].items():
            char_stats[stat] = max(0, min(100, char_stats[stat] + change))
            effect = "📈" if change > 0 else "📉"
            print_slow(f"   {effect} {stat} {'+' if change > 0 else ''}{change} (当前: {char_stats[stat]})")

        if char_stats['体力'] <= 0:
            print_slow("\n💀 你的体力耗尽，被送进了慢羊羊村长的医务室，人生被迫提前结束...")
            break

        time.sleep(1)

    # 结局判定
    print_slow("\n=========================================")
    print_slow("🏁 人生模拟结束！最终属性：")
    for k, v in char_stats.items():
        print_slow(f"   {k}: {v}")

    if char_stats['智慧'] >= 90:
        print_slow("🌟 结局：【青青草原大发明家】你成为了比村长还要聪明的存在！")
    elif char_stats['运气'] >= 90:
        print_slow("🌟 结局：【天选之羊/狼】你出门总能捡到青草饼，灰太狼都羡慕你！")
    elif char_stats['体力'] <= 0:
        print_slow("💔 结局：【英年早逝】青青草原失去了一位勇敢的战士。")
    else:
        print_slow("🌿 结局：【平凡的一生】你在青青草原度过了平淡但安稳的一生。")
    print_slow("=========================================")
if __name__ == "__main__":
    start_simulation()