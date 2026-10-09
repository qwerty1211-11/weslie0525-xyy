import requests
from lxml import etree
import time
import os
import re
import random

# 1. 融合前10章小说链接的字典
kurl = {
    1: {"title": "第432章 一根萝卜", "url": "/ddxs/113860/38850617.html"},
    2: {"title": "第431章 杀天灭无", "url": "/ddxs/113860/38850118.html"},
    3: {"title": "第430章 鸿钧老祖？", "url": "/ddxs/113860/38849266.html"},
    4: {"title": "第429章 吞道", "url": "/ddxs/113860/38848746.html"},
    5: {"title": "第428章 战圣人", "url": "/ddxs/113860/38846899.html"},
    6: {"title": "第427章 吞天之始", "url": "/ddxs/113860/38844081.html"},
    7: {"title": "第1章 禽兽啊", "url": "/ddxs/113860/25013335.html"},
    8: {"title": "第2章 病入膏肓", "url": "/ddxs/113860/25013336.html"},
    9: {"title": "第3章 相依为命", "url": "/ddxs/113860/25013338.html"},
    10: {"title": "第4章 神话都是骗人的！", "url": "/ddxs/113860/25013340.html"}
}


# 2. 核心下载逻辑
def clean_filename(filename):
    """清洗文件名中的非法字符，防止Windows保存报错"""
    return re.sub(r'[\\/:*?"<>|]', '', filename)


def download_novel():
    base_url = "https://www.ddxsw.net"

    # 【防反爬1】使用 Session 保持会话，自动管理 Cookie
    session = requests.Session()

    # 【防反爬2】准备多个真实的浏览器 User-Agent 进行随机伪装
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0'
    ]

    # 创建小说保存文件夹
    folder_name = "修仙小说"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

    # 遍历前10章进行下载
    for num, info in kurl.items():
        title = clean_filename(info["title"])
        url = base_url + info["url"]

        # 每次请求随机生成请求头，模拟真实用户
        headers = {
            "User-Agent": random.choice(user_agents),
            "Referer": base_url  # 模拟从首页点击进入的正常阅读行为
        }

        try:
            response = session.get(url, headers=headers, timeout=10)
            response.encoding = 'utf-8'
            html = etree.HTML(response.text)

            # 提取正文内容
            content_list = html.xpath('//div[@id="content"]//text()')
            content = '\n'.join(content_list).strip()

            # 拦截空内容，避免生成空文件
            if not content:
                print(f"警告: {title} 未提取到内容，可能触发了反爬拦截或网站结构变化")
                continue

                # 保存为txt文件
            file_path = os.path.join(folder_name, f"{num:03d}_{title}.txt")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"成功下载: {title}")

            # 【防反爬3】随机延迟 1~3 秒，模拟真人阅读翻页速度，防止被限流封禁
            delay_time = random.uniform(1.0, 3.0)
            time.sleep(delay_time)

        except Exception as e:
            print(f"下载失败 {title}: {e}")


if __name__ == "__main__":
    download_novel()