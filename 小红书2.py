from DrissionPage import ChromiumPage
import os, time, csv
filename = '大蓝书数据'
if not os.path.exists(filename):
    os.makedirs(filename)
kw = input('请输入您要搜索的小红书内容: ')
page = ChromiumPage()
url = f"https://www.xiaohongshu.com/search_result?keyword={kw}&source=web_explore_feed"
page.get(url)
print("正在等待页面加载并捕获数据包...")
page.listen.start("https://so.xiaohongshu.com/api/sns/web/v2/search/notes", method='POST')
allData = []

# 7. 循环滚动抓取
# 注意：小红书有反爬机制，滚动次数过多可能会失效，建议先测试少量次数
for i in range(20):
    print(f'正在进行第 {i + 1} 次滚动...')

    # 滚动到底部
    page.scroll.to_bottom()

    # 等待数据包返回 (设置超时时间，防止死等)
    # wait() 会阻塞直到捕获到符合条件的包
    try:
        res = page.listen.wait(timeout=10)  # 等待10秒，如果没数据就报错跳过
    except Exception as e:
        print("等待数据包超时，可能已到底部或网络波动。")
        break

    # 8. 解析数据 (核心修复点)
    # res.response.body 已经是字典了，不需要 json.loads
    try:
        result = res.response.body

        # 检查数据结构是否完整
        if 'data' in result and 'items' in result['data']:
            items = result['data']['items']

            for item in items:
                try:
                    # 提取字段
                    note_id = item['id']
                    token = item['xsec_token']
                    note_card = item['note_card']

                    title = note_card['display_title']
                    user_info = note_card['user']
                    name = user_info['nickname']
                    avatar = user_info['avatar']

                    interact_info = note_card['interact_info']
                    liked_count = interact_info['liked_count']
                    collected_count = interact_info['collected_count']
                    comment_count = interact_info['comment_count']
                    shared_count = interact_info['shared_count']

                    # 添加到列表
                    allData.append([note_id, token, title, name, avatar, liked_count, collected_count, comment_count,
                                    shared_count])

                except KeyError as e:
                    # 有些字段可能不存在，跳过即可
                    print(f"字段缺失跳过: {e}")
                    continue
        else:
            print("API 返回数据结构异常，可能未登录或被风控。")
            # 打印部分结果以便调试
            # print(result)
            break

    except Exception as e:
        print(f"解析数据包出错: {e}")
        continue

# 9. 保存数据
csv_file = f'{filename}/大蓝书数据.csv'
with open(csv_file, 'w', newline="", encoding='utf-8-sig') as f:  # 使用 utf-8-sig 防止 Excel 打开乱码
    cf = csv.writer(f)
    cf.writerow(['id', 'token', '标题', '昵称', '头像', '点赞', '收藏', '评论', '分享'])
    cf.writerows(allData)

print(f"抓取完成，共获取 {len(allData)} 条数据，已保存至 {csv_file}")