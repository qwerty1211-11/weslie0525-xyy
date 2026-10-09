money = 100
money=money-95
print(money)
for i in range(1,21):
 money = money*0.05
if money<0.01:
       print("success")
       i=0
while i <10:
    print(i)
    i=1+i
while True:
    print("i like weslie")
    break

boil=0
gai=0
buy=0
while boil<51:
    boil=boil+1
    buy=buy+1
    gai=gai+1
if gai ==3:
    gai=1
    ping = boil+1
    print(buy)
import random
count=1
while True:
 num=random.randint(0,1)
 if num==0:
    print(f"第{count}次提现成功")
    break
if num==1:
    print(f"第{count}次提现失败")
