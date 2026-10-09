import os
from tools.chaojiying import Chaojiying_Client
from DrissionPage import ChromiumPage
from DrissionPage.common import Actions
import random

page = ChromiumPage()
page.get('https://www.zhihu.com')
page.wait(3)

# 登录操作
page.ele('.SignFlow-tab').click()
page.ele('xpath://input[@name="username"]').input('3920682002@qq.com')
page.ele('xpath://input[@name="password"]').input('Aa123456789')
page.ele('xpath://button[@type="submit"]').click()
page.wait(3)

# 获取滑块元素
bg_img = page.ele('.yidun_bg-img')
if bg_img:
    bg_img.save(name='bg.png', rename=False)
else:
    print("未找到背景图，可能无需验证或加载失败")
    exit()

huakuai = page.ele('.yidun_jigsaw')
if not huakuai:
    print("未找到滑块元素")
    exit()

# ===== 超级鹰识别 =====
chaojiying = Chaojiying_Client('ti991', '84t', '96001')

# 先检查余额
try:
    balance = chaojiying.GetBalance()
    print(f"💰 账户余额: {balance}")
except:
    print("⚠️ 无法获取余额，继续尝试...")

# 识别缺口
with open('bg.png', 'rb') as f:
    result = chaojiying.PostPic(f.read(), 9001)  # 改用9001
    print(f"📡 超级鹰返回: {result}")

    # 安全提取坐标
    pic_str = result.get('pic_str', '')
    if pic_str and ',' in pic_str:
        blank_x = int(pic_str.split(',')[0])
        print(f"✅ 识别成功，缺口x坐标: {blank_x}")
    else:
        # 识别失败，使用人工经验值
        print(f"❌ 识别失败，使用备用坐标")
        blank_x = 200  # 这个值可以根据实际情况调整
        print(f"⚠️ 备用坐标: {blank_x}")


# ===== 拖动滑块 =====
def drag_slider(drag_ele, blank_x):
    # 知乎滑块起始偏移约28px
    axis_x = blank_x - 28

    # 随机微调，模拟人类操作
    axis_x += random.randint(-3, 3)
    print(f'🖱️ 实际滑动距离: {axis_x}px')

    page.wait(1)
    ac = Actions(page)
    drag_ele.hover()
    ac.hold(drag_ele)

    # 模拟人类滑动：先快后慢
    ac.move(axis_x // 2, 0).wait(0.1)
    ac.move(axis_x // 3, 0).wait(0.1)
    ac.move(axis_x - axis_x // 2 - axis_x // 3, 0)

    ac.release(drag_ele)


# ===== 执行 =====
try:
    drag_slider(huakuai, blank_x)
    page.wait(3)

    # 判断登录结果
    if page.url.startswith('https://www.zhihu.com/'):
        print("✅ 登录流程完成")
        # 尝试点击头像验证
        try:
            avatar = page.ele('xpath://img[contains(@class, "Avatar")]', timeout=3)
            if avatar:
                print("🎉 登录成功！")
        except:
            print("⚠️ 可能登录失败，需要手动检查")
    else:
        print(f"❌ 登录失败，当前URL: {page.url}")

except Exception as e:
    print(f'❌ 出错: {e}')
    page.screenshot('error.png')