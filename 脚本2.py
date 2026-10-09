import requests
from lxml import etree
import time

# ========== 配置区 ==========
catalog_url = "shturl.cc/Iz0vFDJTRTB/91_91761/"
base_domain = "shturl.cc/Iz0vFDJTRTB"
save_name = "小说.txt"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": catalog_url
}
sleep_time = 1
# ===========================

def get_catalog(url):
    res = requests.get(url, headers=headers, timeout=10)
    # 网页实际编码为gbk，强制指定，否则乱码解析不到标签
    res.encoding = "gbk"
    html = etree.HTML(res.text)
    # 正确XPath，匹配目录章节链接
    href_list = html.xpath('//div[@class="listmain"]//dd/a/@href')
    chapter_urls = []
    for href in href_list:
        # 拼接完整章节地址
        full_url = base_domain + href
        chapter_urls.append(full_url)
    print(f"共获取到 {len(chapter_urls)} 个章节")
    return chapter_urls

def get_chapter_content(chapter_url):
    try:
        res = requests.get(chapter_url, headers=headers, timeout=10)
        res.encoding = "gbk"
        html = etree.HTML(res.text)
        # 章节标题
        title = html.xpath('//h1/text()')[0].strip()
        # 正文内容
        content_lines = html.xpath('//div[@id="content"]/text()')
        content = ""
        for line in content_lines:
            line = line.strip()
            # 过滤广告文字
            if line and "xsbook" not in line and "阅读" not in line:
                content += line + "\n"
        return title, content
    except Exception as e:
        print(f"章节爬取失败 {chapter_url}：{e}")
        return "章节读取失败", ""

def main():
    chapter_urls = get_catalog(catalog_url)
    if len(chapter_urls) == 0:
        print("未抓到任何章节！检查网站是否换页面结构或被拦截")
        return
    with open(save_name, "w", encoding="utf-8") as f:
        for idx, url in enumerate(chapter_urls, 1):
            print(f"正在爬取第{idx}章：{url}")
            title, text = get_chapter_content(url)
            f.write(f"\n==== {title} ====\n")
            f.write(text + "\n")
            time.sleep(sleep_time)
    print(f"爬取完毕，保存至 {save_name}")

if __name__ == "__main__":
    main()