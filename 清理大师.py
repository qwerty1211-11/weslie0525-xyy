import os
import shutil
import customtkinter as ctk
from tkinter import filedialog, messagebox


# =========================
# 基础设置
# =========================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


FILE_TYPES = {
    "图片": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
    "文档": [".doc", ".docx", ".pdf", ".txt", ".ppt", ".pptx"],
    "表格": [".xls", ".xlsx", ".csv"],
    "视频": [".mp4", ".avi", ".mov", ".mkv", ".flv"],
    "音频": [".mp3", ".wav", ".flac", ".aac"],
    "压缩包": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "安装包": [".exe", ".msi"],
    "代码": [".py", ".html", ".css", ".js", ".java", ".cpp", ".c", ".json"],
    "其他": []
}


CATEGORY_ICON = {
    "图片": "🖼️",
    "文档": "📄",
    "表格": "📊",
    "视频": "🎬",
    "音频": "🎧",
    "压缩包": "🗜️",
    "安装包": "⚙️",
    "代码": "💻",
    "其他": "📦"
}


def get_file_category(file_name):
    """根据后缀名判断文件分类"""
    ext = os.path.splitext(file_name)[1].lower()

    for category, extensions in FILE_TYPES.items():
        if ext in extensions:
            return category

    return "其他"


def get_unique_path(target_path):
    """防止同名文件覆盖"""
    if not os.path.exists(target_path):
        return target_path

    folder = os.path.dirname(target_path)
    file_name = os.path.basename(target_path)
    name, ext = os.path.splitext(file_name)

    index = 1
    while True:
        new_name = f"{name}_{index}{ext}"
        new_path = os.path.join(folder, new_name)

        if not os.path.exists(new_path):
            return new_path

        index += 1


class FileOrganizerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("桌面垃圾桶清理大师")
        self.geometry("980x640")
        self.resizable(False, False)

        self.folder_path = ctk.StringVar(value="")
        self.category_cards = {}

        self.create_ui()

    # =========================
    # UI 创建
    # =========================
    def create_ui(self):
        # 主背景
        self.configure(fg_color="#0f172a")

        # 整体布局
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 左侧栏
        self.sidebar = ctk.CTkFrame(
            self,
            width=240,
            corner_radius=0,
            fg_color="#111827"
        )
        self.sidebar.grid(row=0, column=0, sticky="nswe")
        self.sidebar.grid_propagate(False)

        self.create_sidebar()

        # 右侧主区域
        self.main_area = ctk.CTkFrame(
            self,
            corner_radius=0,
            fg_color="#0f172a"
        )
        self.main_area.grid(row=0, column=1, sticky="nswe", padx=0, pady=0)

        self.create_main_area()

    def create_sidebar(self):
        title = ctk.CTkLabel(
            self.sidebar,
            text="🧹\n桌面垃圾桶\n清理大师",
            font=("Microsoft YaHei UI", 26, "bold"),
            text_color="#f9fafb",
            justify="center"
        )
        title.pack(pady=(38, 18))

        desc = ctk.CTkLabel(
            self.sidebar,
            text="让电脑自己收拾自己\n一键整理桌面 / 下载文件夹",
            font=("Microsoft YaHei UI", 13),
            text_color="#9ca3af",
            justify="center"
        )
        desc.pack(pady=(0, 30))

        self.stat_total = self.create_stat_card("待整理文件", "0 个")
        self.stat_success = self.create_stat_card("成功整理", "0 个")
        self.stat_failed = self.create_stat_card("整理失败", "0 个")

        tip = ctk.CTkLabel(
            self.sidebar,
            text="首次使用建议：\n先新建测试文件夹体验\n不要直接整理重要资料",
            font=("Microsoft YaHei UI", 12),
            text_color="#fbbf24",
            justify="center"
        )
        tip.pack(side="bottom", pady=28)

    def create_stat_card(self, label, value):
        card = ctk.CTkFrame(
            self.sidebar,
            width=190,
            height=70,
            fg_color="#1f2937",
            corner_radius=16
        )
        card.pack(pady=8)
        card.pack_propagate(False)

        label_widget = ctk.CTkLabel(
            card,
            text=label,
            font=("Microsoft YaHei UI", 12),
            text_color="#9ca3af"
        )
        label_widget.pack(pady=(10, 0))

        value_widget = ctk.CTkLabel(
            card,
            text=value,
            font=("Microsoft YaHei UI", 20, "bold"),
            text_color="#60a5fa"
        )
        value_widget.pack()

        return value_widget

    def create_main_area(self):
        # 顶部标题区
        header = ctk.CTkFrame(
            self.main_area,
            fg_color="transparent"
        )
        header.pack(fill="x", padx=32, pady=(28, 14))

        main_title = ctk.CTkLabel(
            header,
            text="Python 文件自动整理助手",
            font=("Microsoft YaHei UI", 30, "bold"),
            text_color="#f9fafb"
        )
        main_title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header,
            text="选择一个文件夹，自动按图片、文档、视频、压缩包、代码等类型进行归类整理。",
            font=("Microsoft YaHei UI", 14),
            text_color="#94a3b8"
        )
        subtitle.pack(anchor="w", pady=(6, 0))

        # 路径选择卡片
        path_card = ctk.CTkFrame(
            self.main_area,
            fg_color="#111827",
            corner_radius=20
        )
        path_card.pack(fill="x", padx=32, pady=(10, 18))

        path_card.grid_columnconfigure(0, weight=1)

        self.path_entry = ctk.CTkEntry(
            path_card,
            textvariable=self.folder_path,
            placeholder_text="请选择需要整理的文件夹路径",
            height=44,
            font=("Microsoft YaHei UI", 13),
            fg_color="#020617",
            border_color="#334155",
            corner_radius=14
        )
        self.path_entry.grid(row=0, column=0, padx=(18, 10), pady=18, sticky="we")

        choose_btn = ctk.CTkButton(
            path_card,
            text="选择文件夹",
            height=44,
            width=120,
            font=("Microsoft YaHei UI", 13, "bold"),
            corner_radius=14,
            command=self.choose_folder
        )
        choose_btn.grid(row=0, column=1, padx=(0, 18), pady=18)

        # 操作按钮区
        action_frame = ctk.CTkFrame(
            self.main_area,
            fg_color="transparent"
        )
        action_frame.pack(fill="x", padx=32, pady=(0, 16))

        preview_btn = ctk.CTkButton(
            action_frame,
            text="🔍 整理前预览",
            width=160,
            height=44,
            font=("Microsoft YaHei UI", 14, "bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            corner_radius=14,
            command=self.preview_files
        )
        preview_btn.pack(side="left", padx=(0, 12))

        organize_btn = ctk.CTkButton(
            action_frame,
            text="🚀 开始整理",
            width=160,
            height=44,
            font=("Microsoft YaHei UI", 14, "bold"),
            fg_color="#16a34a",
            hover_color="#15803d",
            corner_radius=14,
            command=self.organize_files
        )
        organize_btn.pack(side="left", padx=(0, 12))

        clear_btn = ctk.CTkButton(
            action_frame,
            text="🧽 清空日志",
            width=140,
            height=44,
            font=("Microsoft YaHei UI", 14, "bold"),
            fg_color="#475569",
            hover_color="#334155",
            corner_radius=14,
            command=self.clear_log
        )
        clear_btn.pack(side="left")

        # 分类预览区域
        category_title = ctk.CTkLabel(
            self.main_area,
            text="文件分类预览",
            font=("Microsoft YaHei UI", 18, "bold"),
            text_color="#f9fafb"
        )
        category_title.pack(anchor="w", padx=34, pady=(0, 8))

        self.category_frame = ctk.CTkFrame(
            self.main_area,
            fg_color="#111827",
            corner_radius=20
        )
        self.category_frame.pack(fill="x", padx=32, pady=(0, 18))

        for i in range(4):
            self.category_frame.grid_columnconfigure(i, weight=1)

        categories = list(FILE_TYPES.keys())
        for index, category in enumerate(categories):
            row = index // 4
            col = index % 4
            self.create_category_card(category, row, col)

        # 进度条
        self.progress = ctk.CTkProgressBar(
            self.main_area,
            height=16,
            corner_radius=12,
            progress_color="#38bdf8"
        )
        self.progress.pack(fill="x", padx=32, pady=(0, 16))
        self.progress.set(0)

        # 日志区域
        log_title = ctk.CTkLabel(
            self.main_area,
            text="整理日志",
            font=("Microsoft YaHei UI", 18, "bold"),
            text_color="#f9fafb"
        )
        log_title.pack(anchor="w", padx=34, pady=(0, 8))

        self.log_box = ctk.CTkTextbox(
            self.main_area,
            height=150,
            font=("Microsoft YaHei UI", 12),
            fg_color="#020617",
            text_color="#d1d5db",
            corner_radius=18,
            border_width=1,
            border_color="#1e293b"
        )
        self.log_box.pack(fill="x", padx=32, pady=(0, 20))

        self.log("欢迎使用桌面垃圾桶清理大师。")
        self.log("建议先选择一个测试文件夹，再点击“整理前预览”。")

    def create_category_card(self, category, row, col):
        card = ctk.CTkFrame(
            self.category_frame,
            fg_color="#1e293b",
            corner_radius=16,
            width=160,
            height=82
        )
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        card.grid_propagate(False)

        icon = CATEGORY_ICON.get(category, "📦")

        label = ctk.CTkLabel(
            card,
            text=f"{icon} {category}",
            font=("Microsoft YaHei UI", 14, "bold"),
            text_color="#f9fafb"
        )
        label.pack(pady=(13, 2))

        count = ctk.CTkLabel(
            card,
            text="0 个",
            font=("Microsoft YaHei UI", 20, "bold"),
            text_color="#38bdf8"
        )
        count.pack()

        self.category_cards[category] = count

    # =========================
    # 功能逻辑
    # =========================
    def choose_folder(self):
        folder = filedialog.askdirectory()

        if folder:
            self.folder_path.set(folder)
            self.log(f"已选择文件夹：{folder}")

    def log(self, message):
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.update_idletasks()

    def clear_log(self):
        self.log_box.delete("1.0", "end")

    def reset_category_cards(self):
        for category in self.category_cards:
            self.category_cards[category].configure(text="0 个")

    def get_files(self):
        folder = self.folder_path.get().strip()

        if not folder:
            messagebox.showwarning("提示", "请先选择一个文件夹")
            return []

        if not os.path.exists(folder):
            messagebox.showerror("错误", "文件夹不存在，请重新选择")
            return []

        files = []

        for file_name in os.listdir(folder):
            file_path = os.path.join(folder, file_name)

            if os.path.isfile(file_path):
                files.append(file_name)

        return files

    def preview_files(self):
        files = self.get_files()

        if not files:
            self.log("当前文件夹没有可整理的文件。")
            self.reset_category_cards()
            self.stat_total.configure(text="0 个")
            return

        category_count = {category: 0 for category in FILE_TYPES.keys()}

        for file_name in files:
            category = get_file_category(file_name)
            category_count[category] += 1

        self.reset_category_cards()

        for category, count in category_count.items():
            self.category_cards[category].configure(text=f"{count} 个")

        self.stat_total.configure(text=f"{len(files)} 个")
        self.stat_success.configure(text="0 个")
        self.stat_failed.configure(text="0 个")
        self.progress.set(0)

        self.log("=" * 42)
        self.log("整理前预览完成：")
        self.log(f"共发现 {len(files)} 个可整理文件。")

        for category, count in category_count.items():
            if count > 0:
                self.log(f"{CATEGORY_ICON.get(category, '')} {category}：{count} 个")

    def organize_files(self):
        folder = self.folder_path.get().strip()
        files = self.get_files()

        if not files:
            return

        confirm = messagebox.askyesno(
            "确认整理",
            f"即将整理当前文件夹中的 {len(files)} 个文件。\n\n"
            f"程序会自动创建分类文件夹，并移动文件。\n\n"
            f"第一次使用建议先测试。\n\n"
            f"是否继续？"
        )

        if not confirm:
            self.log("用户取消了本次整理。")
            return

        success_count = 0
        failed_count = 0

        self.progress.set(0)
        self.log("=" * 42)
        self.log("开始整理文件...")

        for index, file_name in enumerate(files, start=1):
            old_path = os.path.join(folder, file_name)

            try:
                category = get_file_category(file_name)
                category_folder = os.path.join(folder, category)

                if not os.path.exists(category_folder):
                    os.makedirs(category_folder)

                target_path = os.path.join(category_folder, file_name)
                target_path = get_unique_path(target_path)

                shutil.move(old_path, target_path)

                new_name = os.path.basename(target_path)
                self.log(f"✅ {file_name}  →  {category}/{new_name}")
                success_count += 1

            except Exception as e:
                self.log(f"❌ {file_name} 整理失败，原因：{e}")
                failed_count += 1

            self.progress.set(index / len(files))
            self.update_idletasks()

        self.stat_success.configure(text=f"{success_count} 个")
        self.stat_failed.configure(text=f"{failed_count} 个")

        self.log("文件整理完成！")
        self.log(f"成功整理：{success_count} 个")
        self.log(f"整理失败：{failed_count} 个")
        self.log("=" * 42)

        messagebox.showinfo(
            "整理完成",
            f"文件整理完成！\n\n成功整理：{success_count} 个\n整理失败：{failed_count} 个"
        )

        self.preview_files()


if __name__ == "__main__":
    app = FileOrganizerApp()
    app.mainloop()