# -*- coding: utf-8 -*-
"""
自动绘画程序 - 使用turtle库自动绘制各种精美图案
"""

import turtle
import random
import math
import time


class AutoPainter:
    def __init__(self, screen_width=1200, screen_height=800):
        self.screen = turtle.Screen()
        self.screen.setup(screen_width, screen_height)
        self.screen.bgcolor("#1a1a2e")
        self.screen.title("自动绘画程序")
        self.screen.tracer(0, 0)
        
        self.painter = turtle.Turtle()
        self.painter.speed(0)
        self.painter.hideturtle()
        self.painter.pensize(2)
        
        self.colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
            "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
            "#F8B500", "#00CED1", "#FF69B4", "#7FFF00", "#FF4500"
        ]
        
        self.running = False

    def clear_screen(self):
        self.painter.clear()
        self.painter.home()
        self.painter.pendown()
        self.screen.bgcolor("#1a1a2e")

    def draw_fractal_tree(self, branch_len=120, min_len=15, angle=25):
        """绘制分形树"""
        self.clear_screen()
        self.painter.color(random.choice(self.colors))
        self.painter.left(90)
        self.painter.penup()
        self.painter.goto(0, -300)
        self.painter.pendown()
        
        self._draw_branch(branch_len, min_len, angle)
        self.screen.update()

    def _draw_branch(self, length, min_len, angle):
        if length < min_len:
            return
        
        self.painter.forward(length)
        
        # 随机改变颜色
        if random.random() > 0.7:
            self.painter.color(random.choice(self.colors))
        
        # 左分支
        self.painter.left(angle)
        self._draw_branch(length * 0.75, min_len, angle)
        self.painter.right(angle)
        
        # 右分支
        self.painter.right(angle)
        self._draw_branch(length * 0.75, min_len, angle)
        self.painter.left(angle)
        
        self.painter.backward(length)

    def draw_spiral(self, turns=200):
        """绘制彩色螺旋"""
        self.clear_screen()
        self.painter.penup()
        self.painter.goto(0, 0)
        self.painter.pendown()
        
        for i in range(turns):
            self.painter.color(self.colors[i % len(self.colors)])
            angle = i * 0.1
            radius = i * 2
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            self.painter.goto(x, y)
            self.screen.update()

    def draw_flower(self, petals=36):
        """绘制花朵"""
        self.clear_screen()
        self.painter.penup()
        self.painter.goto(0, 0)
        self.painter.pendown()
        
        for i in range(petals):
            color = self.colors[i % len(self.colors)]
            self.painter.color(color)
            
            # 绘制花瓣
            self.painter.begin_fill()
            self.painter.circle(100, 60)
            self.painter.circle(30, 60)
            self.painter.end_fill()
            
            self.painter.left(360 / petals)
            self.screen.update()
        
        # 绘制花心
        self.painter.color("#F8B500")
        self.painter.begin_fill()
        self.painter.circle(30)
        self.painter.end_fill()
        self.screen.update()

    def draw_geometric_pattern(self, size=50):
        """绘制几何图案"""
        self.clear_screen()
        self.painter.penup()
        self.painter.goto(-300, 0)
        self.painter.pendown()
        
        # 绘制多个彩色六边形
        for i in range(12):
            self.painter.color(self.colors[i % len(self.colors)])
            self.painter.begin_fill()
            
            for j in range(6):
                self.painter.forward(size)
                self.painter.right(60)
            
            self.painter.end_fill()
            self.painter.right(30)
            self.screen.update()

    def draw_random_dots(self, count=500):
        """绘制随机点"""
        self.clear_screen()
        self.screen.colormode(255)
        
        for i in range(count):
            x = random.randint(-500, 500)
            y = random.randint(-350, 350)
            size = random.randint(5, 30)
            
            r = random.randint(100, 255)
            g = random.randint(100, 255)
            b = random.randint(100, 255)
            
            self.painter.penup()
            self.painter.goto(x, y)
            self.painter.pendown()
            self.painter.color(r, g, b)
            self.painter.begin_fill()
            self.painter.circle(size)
            self.painter.end_fill()
            self.screen.update()

    def draw_starry_night(self, stars=200):
        """绘制星空"""
        self.clear_screen()
        self.screen.bgcolor("#0d0d1a")
        
        # 绘制星星
        for i in range(stars):
            x = random.randint(-550, 550)
            y = random.randint(-380, 380)
            size = random.uniform(0.5, 2.5)
            
            self.painter.penup()
            self.painter.goto(x, y)
            self.painter.pendown()
            
            # 闪烁效果
            brightness = random.uniform(0.5, 1.0)
            self.painter.color(brightness, brightness, brightness)
            
            self.painter.begin_fill()
            self.painter.circle(size)
            self.painter.end_fill()
        
        # 绘制月亮
        self.painter.penup()
        self.painter.goto(200, 150)
        self.painter.pendown()
        self.painter.color("#FFFACD")
        self.painter.begin_fill()
        self.painter.circle(50)
        self.painter.end_fill()
        
        # 月亮阴影
        self.painter.penup()
        self.painter.goto(220, 160)
        self.painter.pendown()
        self.painter.color("#1a1a2e")
        self.painter.begin_fill()
        self.painter.circle(45)
        self.painter.end_fill()
        
        self.screen.update()

    def draw_sunset(self):
        """绘制日落场景"""
        self.clear_screen()
        self.screen.bgcolor("#1a1a2e")
        
        # 渐变天空
        colors_sky = [
            "#1a1a2e", "#16213e", "#0f3460", "#533483",
            "#e94560", "#ff6b6b", "#f0a500", "#ffd93d"
        ]
        
        for i, color in enumerate(colors_sky):
            self.painter.fillcolor(color)
            self.painter.penup()
            self.painter.goto(-600, 400 - i * 100)
            self.painter.pendown()
            self.painter.begin_fill()
            self.painter.goto(600, 400 - i * 100)
            self.painter.goto(600, 300 - i * 100)
            self.painter.goto(-600, 300 - i * 100)
            self.painter.end_fill()
        
        # 太阳
        self.painter.penup()
        self.painter.goto(0, 50)
        self.painter.pendown()
        self.painter.color("#FF6B35")
        self.painter.begin_fill()
        self.painter.circle(80)
        self.painter.end_fill()
        
        self.painter.penup()
        self.painter.goto(0, 50)
        self.painter.pendown()
        self.painter.color("#FFE66D")
        self.painter.begin_fill()
        self.painter.circle(60)
        self.painter.end_fill()
        
        # 山峦
        self.painter.penup()
        self.painter.goto(-600, -100)
        self.painter.pendown()
        self.painter.color("#2d3436")
        self.painter.begin_fill()
        self.painter.goto(-400, 100)
        self.painter.goto(-200, -50)
        self.painter.goto(0, 150)
        self.painter.goto(200, -30)
        self.painter.goto(400, 80)
        self.painter.goto(600, -100)
        self.painter.goto(600, -400)
        self.painter.goto(-600, -400)
        self.painter.end_fill()
        
        # 水面
        self.painter.penup()
        self.painter.goto(-600, -200)
        self.painter.pendown()
        self.painter.color("#1e272e")
        self.painter.begin_fill()
        self.painter.goto(600, -200)
        self.painter.goto(600, -400)
        self.painter.goto(-600, -400)
        self.painter.end_fill()
        
        # 水面倒影
        self.painter.penup()
        self.painter.goto(0, -150)
        self.painter.pendown()
        self.painter.color("#FF6B35")
        self.painter.begin_fill()
        self.painter.circle(30)
        self.painter.end_fill()
        
        self.screen.update()

    def draw_mandala(self, layers=8):
        """绘制曼陀罗图案"""
        self.clear_screen()
        self.painter.penup()
        self.painter.goto(0, 0)
        self.painter.pendown()
        
        for layer in range(layers):
            radius = 30 + layer * 40
            self.painter.color(self.colors[layer % len(self.colors)])
            
            # 绘制圆形
            self.painter.penup()
            self.painter.goto(0, -radius)
            self.painter.pendown()
            self.painter.circle(radius)
            
            # 绘制装饰线
            if layer % 2 == 0:
                petals = 8 + layer * 2
                for i in range(petals):
                    angle = (360 / petals) * i
                    self.painter.penup()
                    self.painter.goto(0, 0)
                    self.painter.pendown()
                    
                    x1 = radius * math.cos(math.radians(angle))
                    y1 = radius * math.sin(math.radians(angle))
                    self.painter.goto(x1, y1)
                    
                    self.screen.update()
        
        # 中心点
        self.painter.penup()
        self.painter.goto(0, -15)
        self.painter.pendown()
        self.painter.color("#F8B500")
        self.painter.begin_fill()
        self.painter.circle(15)
        self.painter.end_fill()
        self.screen.update()

    def draw_fibonacci_spiral(self):
        """绘制斐波那契螺旋"""
        self.clear_screen()
        
        # 斐波那契数列
        fib = [0, 1]
        for i in range(20):
            fib.append(fib[-1] + fib[-2])
        
        self.painter.penup()
        self.painter.goto(0, 0)
        self.painter.pendown()
        
        angle = 0
        for i, value in enumerate(fib[2:], 2):
            self.painter.color(self.colors[i % len(self.colors)])
            
            # 绘制正方形
            x = value * math.cos(math.radians(angle))
            y = value * math.sin(math.radians(angle))
            
            self.painter.penup()
            self.painter.goto(x - value/2, y - value/2)
            self.painter.pendown()
            self.painter.begin_fill()
            
            for j in range(4):
                self.painter.forward(value)
                self.painter.left(90)
            
            self.painter.end_fill()
            
            # 绘制四分之一圆
            self.painter.penup()
            self.painter.goto(x, y)
            self.painter.pendown()
            self.painter.circle(value, 90)
            
            angle += 90
            self.screen.update()

    def draw_rainbow(self):
        """绘制彩虹"""
        self.clear_screen()
        
        rainbow_colors = [
            "#FF0000", "#FF7F00", "#FFFF00", "#00FF00",
            "#0000FF", "#4B0082", "#9400D3"
        ]
        
        # 彩虹弧
        for i, color in enumerate(rainbow_colors):
            self.painter.color(color)
            self.painter.pensize(15)
            self.painter.penup()
            self.painter.goto(-450, 0)
            self.painter.setheading(90)
            self.painter.pendown()
            self.painter.circle(450 - i * 15, 180)
            self.screen.update()
        
        self.painter.pensize(2)
        
        # 草地
        self.painter.penup()
        self.painter.goto(-600, 0)
        self.painter.pendown()
        self.painter.color("#2E8B57")
        self.painter.begin_fill()
        self.painter.goto(600, 0)
        self.painter.goto(600, -400)
        self.painter.goto(-600, -400)
        self.painter.end_fill()
        self.screen.update()

    def draw_sierpinski_triangle(self, size=600, depth=6):
        """绘制谢尔宾斯基三角形"""
        self.clear_screen()
        self.screen.colormode(255)
        
        # 初始三角形顶点
        p1 = (-300, -200)
        p2 = (300, -200)
        p3 = (0, 250)
        
        self._draw_sierpinski(p1, p2, p3, depth)
        self.screen.update()

    def _draw_sierpinski(self, p1, p2, p3, depth):
        if depth == 0:
            # 绘制三角形
            self.painter.penup()
            self.painter.goto(p1)
            self.painter.pendown()
            
            r = random.randint(50, 200)
            g = random.randint(50, 200)
            b = random.randint(100, 255)
            self.painter.fillcolor(r, g, b)
            self.painter.color(r, g, b)
            
            self.painter.begin_fill()
            self.painter.goto(p2)
            self.painter.goto(p3)
            self.painter.end_fill()
            return
        
        # 计算中点
        mid12 = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        mid23 = ((p2[0] + p3[0]) / 2, (p2[1] + p3[1]) / 2)
        mid13 = ((p1[0] + p3[0]) / 2, (p1[1] + p3[1]) / 2)
        
        # 递归绘制三个小三角形
        self._draw_sierpinski(p1, mid12, mid13, depth - 1)
        self._draw_sierpinski(mid12, p2, mid23, depth - 1)
        self._draw_sierpinski(mid13, mid23, p3, depth - 1)

    def draw_random_walk(self, steps=2000):
        """绘制随机游走"""
        self.clear_screen()
        self.painter.penup()
        self.painter.goto(0, 0)
        self.painter.pendown()
        self.painter.pensize(1)
        
        # 记录路径
        x, y = 0, 0
        
        for i in range(steps):
            self.painter.color(self.colors[i % len(self.colors)])
            
            # 随机方向
            direction = random.randint(0, 3)
            step_length = random.randint(5, 20)
            
            if direction == 0:
                y += step_length
            elif direction == 1:
                y -= step_length
            elif direction == 2:
                x += step_length
            else:
                x -= step_length
            
            self.painter.goto(x, y)
            self.screen.update()

    def draw_pythagoras_tree(self, depth=10):
        """绘制毕达哥拉斯树"""
        self.clear_screen()
        self.painter.penup()
        self.painter.goto(0, -300)
        self.painter.setheading(90)
        self.painter.pendown()
        
        self._draw_pythagoras_tree(120, depth)
        self.screen.update()

    def _draw_pythagoras_tree(self, size, depth):
        if depth == 0 or size < 2:
            return
        
        # 随机颜色
        color_idx = random.randint(0, len(self.colors) - 1)
        self.painter.color(self.colors[color_idx])
        
        self.painter.forward(size)
        
        # 保存当前状态
        pos = self.painter.pos()
        heading = self.painter.heading()
        
        # 左分支
        self.painter.left(45)
        self._draw_pythagoras_tree(size * 0.75, depth - 1)
        
        # 恢复状态
        self.painter.setpos(pos)
        self.painter.setheading(heading)
        
        # 右分支
        self.painter.right(45)
        self._draw_pythagoras_tree(size * 0.75, depth - 1)

    def show_menu(self):
        """显示菜单"""
        print("\n" + "=" * 50)
        print("        自动绘画程序 - 菜单")
        print("=" * 50)
        print("\n请选择要绘制的图案:")
        print("-" * 40)
        print("  1. 分形树")
        print("  2. 彩色螺旋")
        print("  3. 绚丽花朵")
        print("  4. 几何图案")
        print("  5. 随机点")
        print("  6. 星空夜空")
        print("  7. 日落场景")
        print("  8. 曼陀罗图案")
        print("  9. 斐波那契螺旋")
        print("  10. 彩虹")
        print("  11. 谢尔宾斯基三角形")
        print("  12. 随机游走")
        print("  13. 毕达哥拉斯树")
        print("  14. 随机绘制所有图案")
        print("  0. 退出程序")
        print("-" * 40)
        print("=" * 50)

    def run(self):
        """运行主循环"""
        patterns = [
            self.draw_fractal_tree,
            self.draw_spiral,
            self.draw_flower,
            self.draw_geometric_pattern,
            self.draw_random_dots,
            self.draw_starry_night,
            self.draw_sunset,
            self.draw_mandala,
            self.draw_fibonacci_spiral,
            self.draw_rainbow,
            self.draw_sierpinski_triangle,
            self.draw_random_walk,
            self.draw_pythagoras_tree,
        ]
        
        while True:
            self.show_menu()
            
            try:
                choice = input("\n请输入选项 (0-14): ").strip()
                
                if choice == '0':
                    print("\n感谢使用自动绘画程序！再见！")
                    self.screen.bye()
                    break
                
                elif choice == '14':
                    print("\n开始随机绘制所有图案...")
                    for pattern in patterns:
                        print(f"  - 正在绘制: {pattern.__name__}")
                        pattern()
                        time.sleep(1)
                    
                    print("\n所有图案绘制完成！")
                    input("\n按回车键继续...")
                
                elif choice in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13']:
                    idx = int(choice) - 1
                    print(f"\n正在绘制: {patterns[idx].__name__}")
                    patterns[idx]()
                    print("绘制完成！")
                    input("\n按回车键继续...")
                
                else:
                    print("\n无效选项，请重新选择。")
            
            except (KeyboardInterrupt, EOFError):
                print("\n\n程序已停止。再见！")
                self.screen.bye()
                break
            except Exception as e:
                print(f"\n发生错误: {e}")
                input("按回车键继续...")


def main():
    """主函数"""
    print("=" * 50)
    print("    欢迎使用 自动绘画程序 v1.0")
    print("    基于 Python Turtle 库")
    print("=" * 50)
    print("\n程序将自动绘制各种精美的图案。")
    print("请选择你想要绘制的图案类型。\n")
    
    painter = AutoPainter()
    painter.run()


if __name__ == "__main__":
    main()