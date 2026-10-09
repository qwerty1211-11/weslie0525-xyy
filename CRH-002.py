from DrissionPage import ChromiumPage, ChromiumOptions
import time
import random
class YouKuBot:
    def __init__(self):
        # 设置浏览器选项
        co = ChromiumOptions()
        # 可以添加无头模式等参数，但调试时建议显示浏览器
        # co.set_headless(True)
        self.page = ChromiumPage(co)
        self.page.set.timeouts(10, 10, 10)  # 设置超时时间
    def login(self):
        print("正在打开优酷登录页...")
        self.page.get('https://www.youku.com')
        # 1. 点击登录按钮
        # 优酷首页右上角的登录入口，文字可能是"登录"或图标
        try:
            # 尝试点击顶部的登录文字链接
            login_btn = self.page.ele('text=登录', timeout=5)
            login_btn.click()
        except:
            # 如果找不到，可能是已经处于登录弹窗状态，或者结构变了
            print("未找到顶部登录按钮，尝试直接寻找登录框...")

        # 2. 切换到账号密码登录
        # 等待登录框出现，并点击“密码登录”标签
        try:
            self.page.ele('text=密码登录', timeout=10).click()
            print("已切换到密码登录模式")
        except:
            print("可能已经是密码登录模式")
        # 3. 输入账号密码
        # 注意：优酷的input框可能在iframe中，或者name属性会变动
        # 这里使用比较稳健的定位方式
        try:
            # 输入用户名
            user_input = self.page.ele('xpath://input[@name="fm-login-id"]')  # 常见的name属性
            if not user_input: user_input = self.page.ele('xpath:input[@name="fm-login-id"]')  # 备用定位
            user_input.input('13188408741')  # <--- 替换为你的账号

            # 输入密码
            pass_input = self.page.ele('@name=fm-login-password')
            if not pass_input: pass_input = self.page.ele('tag:input@@placeholder=WESLIE0525-xyy')
            pass_input.input('WESLIE0525-xyy')  # <--- 替换为你的密码
            print()
            print("账号密码输入完毕")
        except Exception as e:
            max_count = 10
            for count in range(1, max_count + 1):
                print(f'\n===== 第 {count} 次尝试 =====')
                try:
                    bool_result = drag_verify(page)
                    if not bool_result:
                        text_verify(page)
                    page.ele('.Avatar AppHeader-profileAvatar css-d9tvwx', timeout=3).click()
                    break
                except:
                    page.get('https://www.youku.com/')
                    page.wait(3)  # 等待页面加载
                    page.ele('.SignFlow-tab').click()  # 点击“密码登录”标签
                    page.ele('xpath://input[@name="username"]').input('13188408741')  # 输入手机号或邮箱
                    page.ele('xpath://input[@name="password"]').input('WESLIE0525')  # 输入密码
                    page.ele('xpath://button[@type="submit"]').click()  # 点击登录按钮
                    continue
                    if success:
                        print(success)
                    else:
                        print(fail)
            print(f"输入账号密码失败: {e}")
            return False

        # 4. 点击登录并处理滑块
        submit_btn = self.page.ele('xpath://button[@class="fm-button fm-submit password-login "]')
        submit_btn.click()
        print("已点击登录，正在检测滑块验证...")

        # 5. 滑块验证逻辑 (半自动化)
        # 优酷的滑块验证非常复杂，全自动破解极不稳定。
        # 最佳实践是：程序暂停，等待用户手动通过验证。

        max_wait = 60  # 最多等待60秒
        wait_interval = 2
        elapsed = 0
        while elapsed < max_wait:
            # 检查是否登录成功（通过判断是否存在用户头像或登录后的特定元素）
            # 如果登录成功，页面上通常会出现用户头像
            if self.page.ele('.Avatar', timeout=1) or self.page.ele('text=退出', timeout=1):
                print("检测到你已通过验证并登录成功！")
                return True

            # 检查是否还在滑块验证页面
            # 滑块验证通常包含一个拖动条
            if self.page.ele('xpath://div[contains(@class, "nc_iconfont")]') or self.page.ele('text=向右滑动填充拼图'):
                if elapsed == 0:
                    print("⚠️ 检测到滑块验证！请在浏览器中手动完成滑块验证。")
                    print("程序将在后台等待，直到检测到你登录成功...")

            time.sleep(wait_interval)
            elapsed += wait_interval

        print("等待超时，未检测到登录成功。")
        return False

    def search_content(self, keyword):
        print(f"正在搜索内容: {keyword}")

        # 1. 确保在首页或能进行搜索的页面
        if "youku.com" not in self.page.url:
            self.page.get('https://www.youku.com')
            time.sleep(2)

        # 2. 定位搜索框
        # 搜索框通常在顶部，id可能是'search-keyword'或者placeholder包含'搜索'
        try:
            search_input = self.page.ele('#search-keyword')
            if not search_input:
                search_input = self.page.ele('search_search_input ')

            search_input.input(keyword)
            search_input.input('[Enter]')  # 模拟回车搜索
            print(f"已提交搜索请求: {keyword}")

            # 3. 等待搜索结果加载
            time.sleep(3)  # 等待页面跳转和加载

            # 4. 简单验证是否搜索成功 (打印前几个结果的标题)
            # 搜索结果通常在列表中，类名可能包含 'video' 或 'item'
            results = self.page.eles('xpath://div[@class=""new-content_2kCcp "]')  # 假设标题在h3标签中，具体需根据实际页面调整

            print(f"\n--- 搜索结果预览 (前3个) ---")
            count = 0
            for res in results:
                if count >= 3: break
                title = res.text
                if title:  # 过滤空文本
                    print(f"{count + 1}. {title}")
                    count += 1

        except Exception as e:
            print(f"搜索过程中出错: {e}")

    def run(self):
        if self.login():
            # 登录成功后执行搜索
            self.search_content("狂飙")  # <--- 这里可以修改你要搜索的关键词
        else:
            print("登录失败，程序结束。")

        # 保持浏览器打开，方便查看结果
        input("\n程序执行完毕，按回车键关闭浏览器...")


if __name__ == '__main__':
    bot = YouKuBot()
    bot.run()