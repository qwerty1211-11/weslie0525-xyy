# 1. 猪八戒 网页跑腿员  获取商品搜索页的body
import json
import os
import time

from DrissionPage import ChromiumPage
import schedule
def bajie():
    # 1.1 创建一个浏览器对象
    page = ChromiumPage()
    # 1.2 访问商品搜索页
    page.get("https://s.taobao.com/search?_input_charset=utf-8&clientPreloadId=preload_1787548743444&commend=all&ie=utf8&initiative_id=tbindexz_20170306&page=1&preLoadOrigin=https%3A%2F%2Fwww.taobao.com&q=%E5%96%9C%E7%BE%8A%E7%BE%8A%E5%91%A8%E8%BE%B9&search_type=item&source=suggest&sourceId=tb.index&spm=a21bo.jianhua%2Fa.search_downSideRecommend.d4&ssid=s5-e&suggest=0_4&suggest_query=%E5%96%9C%E7%BE%8A%E7%BE%8A&tab=all&wq=%E5%96%9C%E7%BE%8A%E7%BE%8A")
    # 1.3 等待页面加载完成
    page.wait.doc_loaded()
    # 1.4 获取页面的body内容
    body=page.ele("tag:body").html
    # print(body)
    return body
# 2. 猴哥  将body内容经过传话大爷(本地桥接服务)给猴哥 提取最低价格的商品数据
# 2.1 召唤小弟  requests
import requests
def houge(body):
    # 2.2  大爷地址
    BASE_URL="http://127.0.0.1:3010"
    # 2.3  暗号
    ANHAO="WESLIE-KEY"
    # 2.4  问题
    # question="你猜猜我是谁?"
    prompt=f"""
    你是一名严谨的网页数据提取与比价专家。
    请从以下淘宝搜索结果页面内容中，提取真正相关的商品，并从中筛选出价格最低的那一件商品。
    提取规则：
    提取规则：
    1. 只提取价格最低的那一件商品，不要返回多个。
    2. 商品标题：提取商品标题的完整内容，不要包含任何额外的文本、标签或广告词。
    3. 价格处理：只提取数字部分，去除所有货币符号（如"¥"、"￥"、"元"等），只保留纯数字和小数点。如果价格是一个范围（如"2999-3499"），取最低的那个数字。
    4. 商品链接：只保留能打开商品详情页的部分（保留id=xxx），删掉链接后面多余的小尾巴（如spm、scm、abbucket等参数）。如果链接开头少了"https:"，请补上。
    5. 必须确保标题、价格和链接来自同一个商品，不要把不同商品的信息混在一起。
    输出格式：
    请严格输出一个标准的JSON对象，格式如下：
    {{"title":"商品完整标题","price":4899,"url":"https://item.taobao.com/item.htm?id=123456"}}
    要求：
    - 第一个字符必须是{{
    - 最后一个字符必须是}}
    - 不要输出 ```json 等Markdown标记
    - 不要输出任何解释性文字、分析过程或换行符以外的多余内容
    容错处理：
    如果页面中没有找到任何相关商品，或无法确定价格，请输出：
    {{"title":null,"price":null,"url":null}}
    淘宝搜索结果页body内容如下：
    {body}
    """
    # 2.5 大爷的任务清单 ai表哥的名字 问题
    payload={
        "model":"deepseek",
        "messages":[
            {"role":"user","content":prompt}
        ]
    }
    # 2.6 信物  暗号 任务数据类型
    headers={
        "Authorization":f"Bearer {ANHAO}",
        "Content-Type":"application/json"
    }
    # 2.7 小弟出发
    res=requests.post(
        url=f"{BASE_URL}/v1/chat/completions",
        headers=headers,
        json=payload
    )
    # 2.8 拆开信封 答案  z字典
    response=res.json()
    # print(response)
    answer=response["choices"][0]["message"]["content"]
    # print(answer) # <class 'str'>
    # print(type(answer))
    # 2.9 将json字符串数据转为字典
    answer_dict=json.loads(answer)
    print(answer_dict)
    return answer_dict
# 3. 沙和尚   把最低商品价格数据存到json文件 (重点)
def shaheshang(answer_dict):
    # 3.1 定义变量保存json文件路径
    file="phone.json"
    # 3.2 判断文件是否存在
    isExists=os.path.exists(file)
    # 3.3 不存在 将数据直接写入文件
    if not isExists:
        with open(file,"w",encoding="utf-8") as f:
            # json.dump 将字典/列表 写入到json文件中 json.dumps()
            json.dump([answer_dict],f,ensure_ascii=False,indent=2)
    # 3.4 存在
    else:
        # 3.4.1 读取文件原数据
        with open(file,"r",encoding="utf-8") as f:
            # json.load() 读取文件内容  列表 [{},{}]  json.loads()
            data=json.load(f)
        # 3.4.2 在原数据基础上追加新数据  列表.append(字典)  向列表末尾追加数据
        data.append(answer_dict)
        # 3.4.3 完整数据重新写入json文件
        with open(file,"w",encoding="utf-8") as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
# 4.唐僧   定时：规定任务的间隔时间 schedule
def tangseng():
    body=bajie()
    answer=houge(body)
    shaheshang(answer)
schedule.every(5).seconds.do(tangseng)
while True:
    schedule.run_pending()
    time.sleep(1)
# 5.白龙马 绘图员 绘制折线图代码
# crawl4ai   代码至少能少写一半

# 西天取经