import yagmail
import schedule
import time
yag = yagmail.SMTP(
    username='13188408741@163.com',
    password='WESLIE0525xyy',
    host='163.com',
    port=465
)

# 2. 准备邮件内容
subject = "Python 自动发邮件测试"

# 纯文本内容
text_content = "开阳老师，听说你是个大帅哥，可以帮我手戳一个羊了个羊自动消除代码吗"

# HTML 格式内容（支持丰富的排版）
html_content = """
<h2 style='color:blue;'>系统自动通知</h2>
<p>这是一封 <b>HTML格式</b> 的邮件。</p>
<ul>
    <li>支持列表</li>
    <li>支持字体样式</li>
</ul>
"""

# 3. 发送邮件，send to
try:
    yag.send(
        to='',             # 收件人（可传列表实现多收件人）
        subject=subject,
        contents=[text_content, html_content], # 同时发送文本和HTML，支持附件路径
        cc=['cc_user@example.com'],            # 抄送
        # attachments=['./report.pdf']         # 附件（取消注释并填入真实路径即可）
    )
    print("✅ 邮件发送成功！")
except Exception as e:
    print(f"❌ 邮件发送失败: {e}")
    import yagmail
    import schedule
    import time


    def send_daily_report():
        """定义发邮件的任务函数"""
        yag = yagmail.SMTP('your_email@qq.com', '你的邮箱授权码', host='smtp.qq.com', port=465)
        try:
            yag.send(
                to='',
                subject="",
                contents=""
            )
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 日报发送成功")
        except Exception as e:
            print(f"发送失败: {e}")


    # 设置定时任务：每天早上 12:00 执行
    schedule.every().day.at("12:00").do(send_daily_report)

    # 设置定时任务：每隔 10 分钟执行一次（适合测试）
    # schedule.every(10).minutes.do(send_daily_report)

    print("⏰ 定时邮件程序已启动，等待执行...")

    # 保持程序运行
    while True:
        schedule.run_pending()
        time.sleep(1)
        break
import random
random.randint(1, 100)
breakpoint(78)

