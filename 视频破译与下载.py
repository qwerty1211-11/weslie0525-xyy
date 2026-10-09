#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频播放与下载助手 - PyQt5版
功能：播放视频（通过解析接口）和下载视频
"""

import sys
import re
import os
import threading
import webbrowser
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QProgressBar,
    QGroupBox, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    import requests
except ImportError:
    requests = None

# 解析接口列表
PARSE_URLS = [
    ("https://www.pouyun.com/?url=", "PouYun解析 (推荐)"),
    ("https://jx.xmflv.com/?url=", "XMFLV解析"),
    ("https://www.8090g.cn/?url=", "8090G解析 (无广告)"),
    ("https://jx.yparse.com/index.php?url=", "YParse解析"),
    ("https://api.qianqi.net/vip/?url=", "千奇解析"),
]


class DownloadSignals(QObject):
    """下载信号类"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)
    log = pyqtSignal(str)


class VideoPlayerApp(QMainWindow):
    """视频播放与下载主窗口"""

    def __init__(self):
        super().__init__()
        self.download_signals = DownloadSignals()
        self.download_signals.progress.connect(self.update_progress)
        self.download_signals.finished.connect(self.on_download_finished)
        self.download_signals.log.connect(self.append_log)

        self.is_downloading = False
        self.download_thread = None

        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("视频播放与下载助手")
        self.setFixedSize(900, 600)
        self.center_window()

        # 主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 标题
        title_label = QLabel("🎬 视频播放与下载助手")
        title_label.setFont(QFont("WenQuanYi Zen Hei", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #6B46C1; margin-bottom: 10px;")
        main_layout.addWidget(title_label)

        # URL输入区域
        url_group = QGroupBox("target_url")
        url_layout = QHBoxLayout(url_group)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入视频链接地址 (支持各大视频平台,url_link)")
        self.url_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #E2E8F0;
                border-radius: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #6B46C1;
            }
        """)
        url_layout.addWidget(self.url_input)

        main_layout.addWidget(url_group)

        # 解析通道选择
        channel_group = QGroupBox("解析通道")
        channel_layout = QHBoxLayout(channel_group)

        channel_label = QLabel("选择通道:")
        channel_label.setStyleSheet("font-size: 14px;")
        channel_layout.addWidget(channel_label)

        self.channel_combo = QComboBox()
        for url, name in PARSE_URLS:
            self.channel_combo.addItem(name, url)
        self.channel_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 15px;
                border: 2px solid #E2E8F0;
                border-radius: 8px;
                font-size: 14px;
                min-width: 200px;
            }
            QComboBox:focus {
                border-color: #6B46C1;
            }
        """)
        channel_layout.addWidget(self.channel_combo)
        channel_layout.addStretch()

        main_layout.addWidget(channel_group)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)

        self.play_btn = QPushButton("▶ 播放视频")
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #48BB78;
                color: white;
                padding: 15px 30px;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38A169;
            }
            QPushButton:pressed {
                background-color: #2F855A;
            }
        """)
        self.play_btn.clicked.connect(self.play_video)
        button_layout.addWidget(self.play_btn)

        self.download_btn = QPushButton("⬇ 下载视频")
        self.download_btn.setStyleSheet("""
            QPushButton {
                background-color: #6B46C1;
                color: white;
                padding: 15px 30px;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #553C9A;
            }
            QPushButton:pressed {
                background-color: #44337A;
            }
            QPushButton:disabled {
                background-color: #A0AEC0;
            }
        """)
        self.download_btn.clicked.connect(self.start_download)
        button_layout.addWidget(self.download_btn)

        self.stop_btn = QPushButton("⏹ 停止下载")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #E53E3E;
                color: white;
                padding: 15px 30px;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C53030;
            }
            QPushButton:pressed {
                background-color: #9B2C2C;
            }
            QPushButton:disabled {
                background-color: #A0AEC0;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_download)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.stop_btn)

        main_layout.addLayout(button_layout)

        # 进度条
        progress_group = QGroupBox("下载进度")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #E2E8F0;
                border-radius: 8px;
                text-align: center;
                font-size: 14px;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #6B46C1;
                border-radius: 6px;
            }
        """)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #718096; font-size: 13px;")
        progress_layout.addWidget(self.status_label)

        main_layout.addWidget(progress_group)

        # 日志区域
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1A202C;
                color: #A0AEC0;
                border: 2px solid #2D3748;
                border-radius: 8px;
                padding: 10px;
                font-family: monospace;
                font-size: 13px;
            }
        """)
        log_layout.addWidget(self.log_text)

        main_layout.addWidget(log_group)

        # 初始日志
        self.append_log("程序启动成功")
        self.append_log("支持播放和下载各大视频平台的视频")
        if yt_dlp:
            self.append_log("✓ yt-dlp 已加载，下载功能可用")
        else:
            self.append_log("✗ yt-dlp 未安装，请安装: pip install yt-dlp")

    def center_window(self):
        """窗口居中"""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def append_log(self, message):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def get_video_url(self):
        """获取视频URL"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入视频地址")
            return None

        # 验证URL格式
        if not re.match(r'https?://\w.+$', url):
            QMessageBox.warning(self, "错误", "视频地址格式无效，请检查")
            return None

        return url

    def play_video(self):
        """播放视频"""
        url = self.get_video_url()
        if not url:
            return

        # 获取选中的解析通道
        parse_url = self.channel_combo.currentData()
        play_url = parse_url + url

        self.append_log(f"正在播放: {url}")
        self.append_log(f"解析通道: {self.channel_combo.currentText()}")

        try:
            webbrowser.open(play_url)
            self.append_log("✓ 已在浏览器中打开播放页面")
        except Exception as e:
            self.append_log(f"✗ 播放失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"无法打开浏览器: {str(e)}")

    def start_download(self):
        """开始下载"""
        if self.is_downloading:
            QMessageBox.warning(self, "提示", "已有下载任务进行中")
            return

        url = self.get_video_url()
        if not url:
            return

        if not yt_dlp:
            QMessageBox.critical(self, "错误",
                                 "yt-dlp 未安装，无法下载\n请运行: pip install yt-dlp")
            return

        # 选择保存目录
        save_dir = QFileDialog.getExistingDirectory(
            self, "选择保存目录",
            os.path.expanduser("~/Downloads")
        )
        if not save_dir:
            return

        self.is_downloading = True
        self.download_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)

        self.append_log(f"开始下载: {url}")
        self.append_log(f"保存目录: {save_dir}")

        # 启动下载线程
        self.download_thread = threading.Thread(
            target=self.download_video,
            args=(url, save_dir),
            daemon=True
        )
        self.download_thread.start()

    def download_video(self, url, save_dir):
        """下载视频（在线程中执行）"""
        try:
            def progress_hook(d):
                if d['status'] == 'downloading':
                    # 计算进度
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    if total > 0:
                        percent = int(downloaded * 100 / total)
                        self.download_signals.progress.emit(percent)

                    # 更新状态
                    speed = d.get('speed', 0)
                    if speed:
                        speed_str = self.format_size(speed) + "/s"
                        self.download_signals.log.emit(f"下载中... {speed_str}")

                elif d['status'] == 'finished':
                    self.download_signals.log.emit("下载完成，正在处理...")

            # yt-dlp 配置
            ydl_opts = {
                'outtmpl': os.path.join(save_dir, '%(title)s.%(ext)s'),
                'progress_hooks': [progress_hook],
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.download_signals.finished.emit(True, "下载完成")

        except Exception as e:
            error_msg = str(e)
            if "HTTP Error 403" in error_msg:
                error_msg = "访问被拒绝，视频可能需要登录或有地区限制"
            elif "Video unavailable" in error_msg:
                error_msg = "视频不可用或已被删除"
            elif "Unsupported URL" in error_msg:
                error_msg = "不支持的视频网站"

            self.download_signals.finished.emit(False, f"下载失败: {error_msg}")

    def format_size(self, bytes_num):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_num < 1024:
                return f"{bytes_num:.1f}{unit}"
            bytes_num /= 1024
        return f"{bytes_num:.1f}TB"

    def update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
        self.status_label.setText(f"下载进度: {value}%")

    def on_download_finished(self, success, message):
        """下载完成回调"""
        self.is_downloading = False
        self.download_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if success:
            self.progress_bar.setValue(100)
            self.status_label.setText("下载完成")
            self.append_log(f"✓ {message}")
            QMessageBox.information(self, "成功", message)
        else:
            self.append_log(f"✗ {message}")
            QMessageBox.critical(self, "下载失败", message)

    def stop_download(self):
        """停止下载"""
        if self.is_downloading:
            self.is_downloading = False
            self.download_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("下载已取消")
            self.append_log("✗ 用户取消下载")
            QMessageBox.information(self, "提示", "下载已取消")


def main():
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # 设置全局字体
    font = QFont("WenQuanYi Zen Hei", 12)
    app.setFont(font)

    window = VideoPlayerApp()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()