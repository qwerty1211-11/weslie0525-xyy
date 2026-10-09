from DrissionPage import ChromiumPage
import time
import random


class AutoAnswer:
    def __init__(self):
        # 启动浏览器
        self.page = ChromiumPage()
        # 做题页面地址，改成你的真实做题网址
        self.exam_url = "https://school.yangcongxueyuan.com/study/pratice?topicId=51257e30-32c1-11ea-86d3-755fce067371&themeId=26602940-32bf-11ea-952f-9dc657df204e&sectionId=d962fe60-32be-11ea-952f-9dc657df204e&subSectionId=eaeb36c0-32be-11ea-86d3-755fce067371&publisherId=24&semesterId=20&stageId=3&subjectId=1&name=%E6%8C%87%E6%95%B0%E8%BF%90%E7%AE%97%E5%AE%9A%E4%B9%89%E7%9A%84%E6%89%A9%E5%85%85&doneLevel=0"
        # 通义千问网页地址
        self.qwen_url = "https://tongyi.aliyun.com/qianwen/"

    def get_question(self):
        """【步骤1】在做题页识别提取题目，修改ele选择器适配你的网页"""
        # =========这里需要你修改选择器！改成你页面题目的css/xpath=========
        question_ele = self.page.ele(".question-title", timeout=8)
        if not question_ele:
            print("❌没有识别到题目元素，请修改题目选择器！")
            return None
        question_text = question_ele.text.strip()
        print(f"\n📝识别到题目：{question_text}")
        return question_text

    def ask_qwen(self, question):
        """【步骤2】打开千问，把题目粘贴提问，获取AI返回答案"""
        # 新建标签页打开千问
        tab_qwen = self.page.new_tab(self.qwen_url)
        time.sleep(random.uniform(2, 3.5))

        # 定位千问输入框，粘贴题目
        input_box = tab_qwen.ele("textarea", timeout=10)
        input_box.input(question)
        time.sleep(random.uniform(0.8,1.5))
        # 点击发送按钮
        send_btn = tab_qwen.ele('button[type="submit"]')
        send_btn.click()
        print("🚀已经向千问发送题目，等待AI生成答案...")

        # 等待AI输出完成，等待时间根据网络调整
        time.sleep(random.uniform(8,14))

        # 获取最新一条AI回复内容，修改选择器如果获取不到
        answer_ele = tab_qwen.ele(".markdown-body", timeout=12)
        if not answer_ele:
            print("❌千问未获取到答案")
            tab_qwen.close()
            return None
        answer_text = answer_ele.text.strip()
        print(f"🤖千问得到答案：\n{answer_text[:200]}......")

        # 复制答案到剪贴板，方便回填
        tab_qwen.set_clipboard(answer_text)
        # 关闭千问标签页，切回做题页面
        tab_qwen.close()
        return answer_text

    def fill_and_submit(self, answer):
        """【步骤3】回到做题页面，把答案粘贴输入框，提交"""
        if answer is None:
            print("⚠️答案为空，跳过提交")
            return
        # =========修改这里，适配你的答题输入框选择器========
        answer_input = self.page.ele(".answer-input", timeout=6)
        # 粘贴剪贴板内容
        answer_input.paste()
        time.sleep(random.uniform(1,2))
        # 点击提交按钮，修改选择器
        submit_btn = self.page.ele(".submit-btn")
        submit_btn.click()
        print("✅已完成回填并提交本题！")
        time.sleep(2)

    def run(self):
        """主流程"""
        print("打开做题页面")
        self.page.get(self.exam_url)
        time.sleep(random.uniform(2,3))

        # 1 获取题目
        q_text = self.get_question()
        if not q_text:
            input("回车退出")
            self.page.quit()
            return
        # 2 请求千问获取答案
        ans = self.ask_qwen(q_text)
        # 3 回填提交
        self.fill_and_submit(ans)

        input("\n全部流程执行完毕，按回车关闭浏览器")
        self.page.quit()


if __name__ == "__main__":
    bot = AutoAnswer()
    bot.run()