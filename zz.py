'''
人生模拟器（综合项目）
刚出生:
1. 输入性别
2. 输入名字
3. 随机生成智力、资产、健康、快乐等数据
4. 生成的智力或者家境，数据和预期较低，可以选择重开
新手村:
随机事件

学习阶段：
遇到一些事件，可以选择有不同的结果

是否创业:
决策事件：是否创业还是当牛马---不同的选择后续，还有不同的二次选择

结局判断
1.总分值>30:S级别，人生赢家
2.总分值>=22:A级评价!小康生活
3.智力<3:D级，智力低下，治好了也流口水
4.健康<=2:E级，健康崩坏，英年早逝
5.其他:平凡NPC，平淡一生
'''
import random

#定义属性变量
zhili = 0  #智力属性
zichan = 0 #资产属性
jiankang = 0 #健康属性
xinqing = 0  #心情属性

xingbie = ''  #性别属性
xingming = ''  #姓名属性
# 让用户请输入姓名和性别
xingbie = input('请输入您的性别:')
xingming = input('请输入您的姓名:')

def fuhua():
    global zhili,zichan,jiankang,xinqing
    #给用户生成随机属性 1-10
    zhili = random.randint(6,10)
    zichan = random.randint(1,10)
    jiankang = random.randint(1,10)
    xinqing = random.randint(1,10)

    print(f'\n==============尊敬的用户{xingming}=================\n您的初始属性面板为|智力:{zhili}|资产:{zichan}|健康:{jiankang}|心情:{xinqing}')
# =====================孵化角色环节============================
#老师，能不能重新随机啊？初始状态不满意
while True:  #如果用户一直不满意就一直循环 ；如果只给用户三次机会，for i in range(3)
    fuhua()
    choice = input('您是否满意当前的角色？满意输入666，不满意输入1:')
    if choice == '666':  #用户满意
        print('\n确认角色，开始冒险吧！！')
        break
    else:
        print('\n开始重新生成角色中...')
        import time
        time.sleep(1)

# =====================新手村环节============================
# 随机遇到一些事项
print("\n===== 人生模拟器：7岁前 触发随机事件 =====")
suiji = random.randint(1,3)
if suiji == 1:
    zhili += 10  #  zhili = zhili + 10
    print(f'文曲星托梦，大脑被强力开发，智力+10-->当前智力{zhili}')
elif suiji == 2:
    jiankang += 6
    print(f'被路边老乞丐发掘，根骨奇特，练武奇才，健康+6-->当前健康{jiankang}')
elif suiji == 3:
    zhili -= 2
    print(f'沉迷游戏，无心学习，智力-2-->当前智力{zhili}')

#====================进入成长期(7-18岁)========================
print('\n=====人生模拟器：7~18岁（成长期）==========')
#定义一组事件，让他们随机的发生  列表？  字典？
# 事件的组成：发生了啥事（出门捡钱，你是否选择捡起来？）    属性的变化：+1 +3 -2  zichan+20 zhili-10
#资产 智力 健康 心情
chengzhang = [
    {'天降横财，出门见到了1万块，请选择是否捡起':[10,-2,0,10,0,-2,0,-4]},
    {'心动crush，您是否选择冲动消费':[-6,-8,-1,4,2,5,-1,-2]},
    {'路见不平，您是否选择拔刀相助':[2,-1,0,8,-1,1,0,-2]},
    {'同桌对你表白，您是否选择答应':[0,2,-2,6,0,-2,2,-2]},
    {'刘亦菲邀请你共进晚餐，您是否选择答应':[10,10,10,10,10,10,10,10]}
]
#循环执行事件，每年发生一次
for i in range(7,19):
    print(f'\n🎂 今年你{i}岁')
    shijian = random.choice(chengzhang)
    #解决问题1：数值就没有加上去  问题2：你也没让我选啊？

    #这行代码 分别取出上面的key和value，然后保存在两个变量里
    shijiankey, shijianvalue = next(iter(shijian.items()))
    print(f'您触发了事件{shijiankey}:')
    choice = input('请输入你的选择(选择输入1,拒绝输入2):')
    if choice == '1':
        zichan = zichan + shijianvalue[0]
        zhili = zhili + shijianvalue[1]
        jiankang = jiankang + shijianvalue[2]
        xinqing = xinqing + shijianvalue[3]
        print(f'您属性发生变化资产:{zichan} 智力:{zhili} 健康:{jiankang} 心情{xinqing}')
    elif choice == '2':
        zichan = zichan + shijianvalue[4]
        zhili = zhili + shijianvalue[5]
        jiankang = jiankang + shijianvalue[6]
        xinqing = xinqing + shijianvalue[7]
        print(f'您属性发生变化资产:{zichan} 智力:{zhili} 健康:{jiankang} 心情{xinqing}')

# ========== 6. 成年阶段（18岁后，创业/打工，复习条件判断） ==========
print("\n===== 人生模拟器：18岁成年 =====")
cy = input('是否选择创业？（1表示创业，2不创业）:')
if cy == '1':
    cy1 = input('选择小本买卖，还是all in 借贷（1表示小本买卖，2借贷）')
    if cy1 == '1':
        print("🚀 创业成功！资产+10，心情+5")
        zichan += 10
        xinqing += 5
    else:
        print("💥 创业失败！资产-10，心情-10")
        zichan -= 10
        xinqing -= 10
else:
    print("👔 选择打工，安稳但辛苦：资产+3，智力+3，健康-2，心情-2")
    zichan += 3
    zhili += 3
    jiankang -= 2
    xinqing -= 2

# 展示成年后属性
print(f"\n【成年后最终属性】")
print(f"智力：{zhili} | 资产：{zichan} | 健康：{jiankang} | 心情：{xinqing}")

# ========== 7. 人生结算（复习总分计算+多条件判断） ==========
print("\n===== 人生模拟器：赛季结算 =====")
input("按下回车键查看你的人生评价 ↓（按回车继续）")

zongfen = zhili+zichan+jiankang+xinqing
if zongfen >= 40:
    print(f"🏆 S级评价（{zongfen}分）：人生赢家！")
elif zongfen>=20:
    print(f"🥈 A级评价（{zongfen}分）：普普通通的人生")
elif zhili<3:
    print(f"🥉 D级评价（智力{zhili}分）：智力堪忧")
elif jiankang <= 5:
    print(f"💀 E级评价（健康{jiankang}分）：英年早逝")
else:
    print(f"⭐ B级评价（{zongfen}分）：平平淡淡的NPC人生")

