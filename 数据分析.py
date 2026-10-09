from encodings import utf_8
import requests
import time
import random
import pandas as pd #导入pandas 取个别名叫做pd
send_url="https://api.kaoyan.cn/pc/school/schoolList"
send_h={
    "user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "referer":"https://www.kaoyan.cn/",
}
send_data={
    "page": 1,
    "limit": 20,
    "province_id": "11",
    "type": "",
    "feature": "",
    "school_name": ""
}
res=requests.post(url=send_url,headers=send_h,data=send_data)
resdata=res.json()
xxlist=resdata["data"]["data"]
all_data=[]
for xx in  xxlist:
    xname=xx["school_name"]
    xid = xx["school_id"]
    for i in range(2023,2027):
        url = "https://api.kaoyan.cn/pc/school/schoolScore"
        data = {
            "degree_type": "",
            "school_id": xid,
            "year":i
        }
        res = requests.post(url=url, headers=send_h, data=data)
        resdata = res.json()
        for x in resdata["data"]:
            data = {
                "学校": xname,
                "专业": x["name"],
                "代码": x["code"],
                "招生院系": x["depart_name"],
                "总分": x["total"],
                "政治": x["english"],
                "外语": x["politics"],
                "专业课一": x["special_one"],
                "专业课二": x["special_two"],
                "录取年份": x["year"]
            }
            print(data)
            all_data.append(data)
    time.sleep(random.randint(1,20))
df=pd.DataFrame(all_data)
df.to_csv("各院校历年数据采集.csv",index=False)
import pandas
from 数据分析服务 import ai_fenxi_and_report

#要分析爬下来的结果，先要读取csv文件
df = pandas.read_csv('各大院校历年分数线采集.csv')
#需要按照学校分组获取内容
xuexiao = df.groupby('学校')
#[(北京大学，北京大学),(清华大学，清华大学)]
for i in xuexiao:
    print(i[0])

#让用户输入想要选择的学校
xxname = input('请输入您想选择的院校:')

#列出该学校的所有专业，get_group就是获取你输入的学校名称的分组

zhuanye_list = xuexiao.get_group(xxname)['专业'].tolist()

for i in zhuanye_list:
    print(i)

zyname = input('请输入专业名称:')

#计算并展示目标院校的历年平均分数线，辅助用户合理评分
xuesheng_data = xuexiao.get_group(xxname)
#筛选专业的列值                       专业 == 管理学
zhuanye_data = xuesheng_data[xuesheng_data['专业']==zyname]
#取该专业的平均分  350+350+345+340/4
pingjunfen = zhuanye_data['总分'].mean()
#pingjunfen:.1f  保留一位小数
print(f'{xxname}的{zyname}历年平均分数线：{pingjunfen:.1f}分')

fenshu = float(input('请您输入您的预估分数:'))

#调用AI分析，控制台输出结果，生成HTML报告，自动打开浏览器
jieguo = ai_fenxi_and_report(xxname,zyname,fenshu)






