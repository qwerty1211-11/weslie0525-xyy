
import requests

url = "https://www.baidu.com/index.php?tn=68018901_58_oem_dg"
response = requests.get(url)
response.encoding = "utf-8"
print("请求结果", response.text)
# 测试======T========E========S=========T

headers = {
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"}
print(response.content)
with open("xyy.jpg", "wb") as f:
    f.write(response.content)
import requests
import os
import time
from urllib.parse import urljoin, urlparse

# --- 配置区 ---
# 1. 目标网页URL（包含图片的页面）
target_url = "https://www.baidu.com/index.php?tn=68018901_58_oem_dg"
# 2. 请求头（伪装浏览器，防止被反爬）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
}

# 3. 存储图片的文件夹
save_folder = "downloaded_images"
os.makedirs(save_folder, exist_ok=True)  # 如果文件夹不存在则创建


# --- 核心逻辑 ---

def get_image_urls_from_page(url):
    """
    这是一个示例函数。
    实际使用时，你需要根据目标网页的HTML结构，使用BeautifulSoup或正则表达式提取<img>标签的src属性。
    """
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # 这里需要替换为实际的解析逻辑，例如使用 BeautifulSoup:
        # from bs4 import BeautifulSoup
        # soup = BeautifulSoup(response.text, 'html.parser')
        # img_tags = soup.find_all('img', class_='example-class')
        # urls = [urljoin(url, img['src']) for img in img_tags if img.get('src')]

        # 临时返回一个测试列表（请替换为真实解析逻辑）
        # 注意：这里的链接必须是图片的直接链接，而不是百度那种缩略图中转链接
        return [
            "https://b0.bdstatic.com/ugc/uU_KpJMxROMPFDXlYmMW6Abee0e0f2246129947bd8237397da57f4.jpg",
        "file:///C:/Users/lenovo/Downloads/0b5d78cd39d0d54337dd8fd0ed3b7faa.jpg",
        "https://img0.baidu.com/it/u=1192980425,1528968618&fm=253&fmt=auto&app=138&f=JPEG?w=584&h=500"]
    except Exception as e:
        print(f"获取页面失败: {e}")
        return []


def download_image(url, folder, index):
    """
    下载单张图片并保存
    """
    try:
        # 发送请求，stream=True 以便处理大文件
        response = requests.get(url, headers=headers, stream=True, timeout=10)
        response.raise_for_status()

        # 尝试从URL或响应头获取文件扩展名
        parsed_url = urlparse(url)
        ext = os.path.splitext(parsed_url.path)[1]
        if not ext:
            # 如果URL没有后缀，尝试从Content-Type获取
            content_type = response.headers.get('content-type', '')
            if 'jpeg' in content_type:
                ext = '.jpg'
            elif 'png' in content_type:
                ext = '.png'
            else:
                ext = '.jpg'  # 默认

        # 文件保存路径
        filename = f"image_{index:03d}{ext}"
        filepath = os.path.join(folder, filename)

        # 保存图片
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        print(f"[成功] 已下载: {filename}")
        return True

    except Exception as e:
        print(f"[失败] 下载 {url} 时出错: {e}")
        return False


# --- 主程序 ---
if __name__ == "__main__":
    print("开始批量爬取图片...")

    # 1. 获取图片链接列表
    # image_urls = get_image_urls_from_page(target_url)

    # 临时测试数据（请替换为上面那行代码或你的实际链接列表）
    image_urls = [    "https://b0.bdstatic.com/ugc/uU_KpJMxROMPFDXlYmMW6Abee0e0f2246129947bd8237397da57f4.jpg",
        "file:///C:/Users/lenovo/Downloads/0b5d78cd39d0d54337dd8fd0ed3b7faa.jpg",
        "https://img0.baidu.com/it/u=1192980425,1528968618&fm=253&fmt=auto&app=138&f=JPEG?w=584&h=500"]

    print(f"共找到 {len(image_urls)} 张图片待下载。")

    # 2. 遍历下载
    success_count = 0
    for i, img_url in enumerate(image_urls, 1):
        if download_image(img_url, save_folder, i):
            success_count += 1
        # 适当延时，礼貌爬取
        time.sleep(1)

    print(f"下载完成！成功: {success_count}, 失败: {len(image_urls) - success_count}")