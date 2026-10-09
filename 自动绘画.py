import cv2
import numpy as np
import os
import sys


class HighFidelityPainter:
    def __init__(self, image_name='input_image.jpg'):
        # 获取当前脚本所在的绝对路径
        base_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(base_dir, image_name)

        print(f"正在尝试读取图片: {image_path}")

        # 1. 检查文件是否存在
        if not os.path.exists(image_path):
            print(f"\n❌ 错误：找不到文件 '{image_name}'")
            print(f"📂 当前代码所在目录是: {base_dir}")
            print("💡 解决方法：请把图片和代码放在同一个文件夹里！")
            return

        # 2. 读取原图
        self.original_img = cv2.imread(image_path)
        if self.original_img is None:
            print("❌ 错误：文件存在但无法解码，可能是图片损坏或格式不对。")
            return

        print("✅ 图片读取成功！开始处理...")
        self.height, self.width = self.original_img.shape[:2]

        # 这里可以继续你后续的绘图逻辑...
        # 例如显示图片测试一下
        cv2.imshow("Original", self.original_img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    # 实例化并运行
    painter = HighFidelityPainter()