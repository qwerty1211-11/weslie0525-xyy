#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校园跑自动化脚本 V1.00
功能：模拟GPS轨迹 + 自动点击，实现校园跑打卡
依赖：pure-python-adb + platform-tools（首次运行自动下载）
使用前请开启手机USB调试并连接电脑
"""

import time
import math
import random
import threading
import sys
import os
import subprocess
import zipfile
import urllib.request
from ppadb.client import Client as AdbClient

# ==================== 配置区域 ====================

# ADB配置（保持默认即可，不需要改）
ADB_HOST = "127.0.0.1"
ADB_PORT = 5037

# 跑步配置
target_RUN_DISTANCE_KM = 2.0          # 目标跑步距离（公里）
RUN_SPEED_KMH = 8.0            # 跑步速度（公里/小时），约等于正常慢跑速度
GPS_UPDATE_INTERVAL = 2        # GPS位置更新间隔（秒）

# GPS轨迹起点（可以通过高德/百度地图坐标拾取获取）
START_LAT = 41.7258           # 起点纬度
START_LNG =123.4965            # 起点经度

# 轨迹模式：'loop'(绕圈往返) 或 'rectangle'(矩形路线)
TRACK_MODE = "rectangle"

# 路线偏移（度），用于生成绕圈路线
LAT_OFFSET = 0.0015            # 纬度方向偏移（约166米）
LNG_OFFSET = 0.0015            # 经度方向偏移（约144米，取决于纬度）

# 触摸操作配置（坐标需要根据实际APP调整）
# 建议使用项目中的 "目标点位定位程序.py" 来获取坐标
TOUCH_COORDS = {
    "start_btn": {"x": 540, "y": 1820},   # 开始跑步按钮坐标
    "end_btn": {"x": 540, "y": 1820},     # 结束跑步按钮坐标
    "confirm_btn": {"x": 540, "y": 1400},  # 确认/保存按钮坐标
}

# 动作延时（秒）
ACTION_DELAY = 3

# ================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADB_PATH = os.path.join(SCRIPT_DIR, "platform-tools", "adb.exe")


def ensure_adb():
    """确保ADB工具存在并启动ADB Server"""
    if os.path.exists(ADB_PATH):
        print(f"[+] ADB已存在: {ADB_PATH}")
    else:
        print("[*] 首次运行，正在下载ADB工具...")
        zip_path = os.path.join(SCRIPT_DIR, "platform-tools.zip")
        url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
        try:
            urllib.request.urlretrieve(url, zip_path)
            print("[+] 下载完成，正在解压...")
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(SCRIPT_DIR)
            os.remove(zip_path)
            print("[+] ADB工具准备完成")
        except Exception as e:
            print(f"[-] 下载ADB失败: {e}")
            print("    请手动下载: https://developer.android.com/studio/releases/platform-tools")
            return False

    print("[*] 正在启动ADB Server...")
    try:
        subprocess.run([ADB_PATH, "kill-server"], capture_output=True, timeout=5)
        time.sleep(0.5)
        result = subprocess.run([ADB_PATH, "start-server"], capture_output=True, timeout=10)
        time.sleep(1)
        result = subprocess.run([ADB_PATH, "devices"], capture_output=True, text=True, timeout=5)
        if "List of devices" in result.stdout:
            print(f"[+] ADB Server已启动 (版本: {get_adb_version()})")
            return True
        else:
            print(f"[-] ADB Server启动异常: {result.stdout}")
            return False
    except Exception as e:
        print(f"[-] 启动ADB Server失败: {e}")
        return False


def get_adb_version():
    """获取ADB版本号"""
    try:
        result = subprocess.run([ADB_PATH, "version"], capture_output=True, text=True, timeout=5)
        for line in result.stdout.splitlines():
            if "Android Debug Bridge" in line:
                return line.split()[-1]
    except Exception:
        pass
    return "未知"


class CampusRunAutomation:
    def __init__(self):
        self.device = None
        self.running = False
        self.gps_thread = None
        self.current_lat = START_LAT
        self.current_lng = START_LNG
        self.total_distance = 0.0
        self.target_distance = target_RUN_DISTANCE_KM * 1000
        self.speed = RUN_SPEED_KMH / 3.6
        self.gps_points = []
        self.paused = False

    def connect_device(self, max_retries=3):
        """
        连接ADB设备（支持重试、多设备选择、无线ADB）
        
        Args:
            max_retries: 最大重试次数
            
        Returns:
            bool: 连接是否成功
        """
        print("\n" + "=" * 50)
        print("  【第一步】连接设备")
        print("=" * 50)

        for attempt in range(1, max_retries + 1):
            print(f"\n[*] 第 {attempt}/{max_retries} 次扫描设备...")

            try:
                client = AdbClient(host=ADB_HOST, port=ADB_PORT)
                devices = client.devices()

                devices = [d for d in devices if d.serial != "host"]

                if not devices:
                    print("[-] 未找到任何ADB设备")
                    self._print_connect_help()
                    if attempt < max_retries:
                        print(f"[*] 5秒后重试... (Ctrl+C 跳过无线连接)")
                        time.sleep(5)
                        continue
                    else:
                        choice = input("\n[?] 重试无线ADB连接吗？(y/n): ").strip().lower()
                        if choice == "y":
                            return self._connect_wireless()
                        return False

                authorized = [d for d in devices if d.serial != "unauthorized"]
                unauthorized = [d for d in devices if d.serial == "unauthorized"]

                if unauthorized:
                    for d in unauthorized:
                        print(f"[-] 设备 {d.serial} 未授权！请在手机上点击 '允许USB调试'")
                    if not authorized:
                        if attempt < max_retries:
                            print(f"[*] 等待授权中... (Ctrl+C 跳过)")
                            time.sleep(5)
                            continue
                        return False

                if len(authorized) > 1:
                    self.device = self._select_device(authorized)
                else:
                    self.device = authorized[0]

                self._print_device_info()
                return True

            except Exception as e:
                print(f"[-] 连接异常: {e}")
                if attempt < max_retries:
                    print("[*] 重启ADB Server后重试...")
                    try:
                        subprocess.run([ADB_PATH, "kill-server"], capture_output=True)
                        subprocess.run([ADB_PATH, "start-server"], capture_output=True)
                        time.sleep(2)
                    except Exception:
                        pass
                else:
                    return False

        return False

    def _select_device(self, devices):
        """多设备时让用户选择"""
        print(f"\n[!] 检测到 {len(devices)} 台已授权设备：")
        print("-" * 50)
        for i, d in enumerate(devices):
            model = self._get_prop(d, "ro.product.model")
            addr = d.serial
            if ":" in d.serial:
                addr += " (无线)"
            else:
                addr += " (USB)"
            print(f"  [{i}] {model}  ->  {addr}")
        print("-" * 50)
        while True:
            try:
                choice = input(f"请选择设备编号 [0-{len(devices)-1}] (默认0): ").strip()
                if choice == "":
                    return devices[0]
                idx = int(choice)
                if 0 <= idx < len(devices):
                    return devices[idx]
            except ValueError:
                pass
            print("[!] 请输入有效数字")

    def _get_prop(self, device, prop_name):
        """获取设备属性"""
        try:
            result = device.shell(f"getprop {prop_name}").strip()
            return result if result else "未知"
        except Exception:
            return "未知"

    def _print_device_info(self):
        """打印设备详细信息"""
        model = self._get_prop(self.device, "ro.product.model")
        brand = self._get_prop(self.device, "ro.product.brand")
        android_ver = self._get_prop(self.device, "ro.build.version.release")
        sdk_ver = self._get_prop(self.device, "ro.build.version.sdk")
        device_sn = self._get_prop(self.device, "ro.serialno")
        cpu_abi = self._get_prop(self.device, "ro.product.cpu.abi")
        battery = self._get_battery_level()
        mock_enabled = self._check_mock_location()

        conn_type = "无线" if ":" in self.device.serial else "USB"

        print("\n" + "┌─────────────────────────────────────────┐")
        print("│           设备连接成功 ✓                │")
        print("├─────────────────────────────────────────┤")
        print(f"│  品牌型号  : {brand} {model}")
        print(f"│  Android   : {android_ver} (SDK {sdk_ver})")
        print(f"│  连接方式  : {conn_type}")
        print(f"│  序列号    : {self.device.serial}")
        print(f"│  CPU架构   : {cpu_abi}")
        print(f"│  电量      : {battery}%")
        print(f"│  Mock开关  : {'已开启' if mock_enabled else '未开启'}")
        print("└─────────────────────────────────────────┘")

    def _get_battery_level(self):
        """获取电池电量"""
        try:
            result = self.device.shell("dumpsys battery | grep level").strip()
            return result.split(":")[-1].strip()
        except Exception:
            return "??"

    def _check_mock_location(self):
        """检查Mock Location是否已开启"""
        try:
            result = self.device.shell("settings get secure mock_location").strip()
            return result == "1"
        except Exception:
            return False

    def _print_connect_help(self):
        """打印连接帮助"""
        print("\n┌──────────────────────────────────────────────┐")
        print("│  📱 设备连接排查指南                          │")
        print("├──────────────────────────────────────────────┤")
        print("│  USB连接:                                     │")
        print("│   1. 用原装数据线连接手机和电脑               │")
        print("│   2. 手机开启: 设置 → 开发者选项 → USB调试    │")
        print("│   3. 选择传输文件模式(非仅充电)               │")
        print("│   4. 手机弹窗点击 '允许USB调试'               │")
        print("│                                              │")
        print("│  无线连接 (需先USB连接过):                    │")
        print("│   adb tcpip 5555                              │")
        print("│   adb connect 手机IP:5555                     │")
        print("└──────────────────────────────────────────────┘")

    def _connect_wireless(self):
        """通过无线ADB连接设备"""
        print("\n[*] 尝试无线ADB连接...")
        print("[*] 手机需先通过USB连接过并开启USB调试")
        ip = input("请输入手机IP地址 (如 192.168.1.100): ").strip()
        if not ip:
            return False
        try:
            subprocess.run([ADB_PATH, "connect", f"{ip}:5555"], capture_output=True, timeout=10)
            time.sleep(2)
            client = AdbClient(host=ADB_HOST, port=ADB_PORT)
            devices = [d for d in client.devices() if d.serial != "host" and d.serial != "unauthorized"]
            if devices:
                self.device = devices[0]
                self._print_device_info()
                return True
        except Exception as e:
            print(f"[-] 无线连接失败: {e}")
        return False

    def reconnect_device(self):
        """重新连接设备"""
        print("[*] 正在重新连接...")
        try:
            subprocess.run([ADB_PATH, "kill-server"], capture_output=True)
            time.sleep(0.5)
            subprocess.run([ADB_PATH, "start-server"], capture_output=True)
            time.sleep(1)
            client = AdbClient(host=ADB_HOST, port=ADB_PORT)
            devices = [d for d in client.devices() if d.serial != "host" and d.serial != "unauthorized"]
            if devices:
                self.device = devices[0]
                print(f"[+] 重连成功: {self.device.serial}")
                return True
        except Exception as e:
            print(f"[-] 重连失败: {e}")
        return False

    def generate_route_points(self):
        """生成GPS轨迹路线点"""
        points = []
        total_points_needed = int(self.target_distance / (self.speed * GPS_UPDATE_INTERVAL))

        if TRACK_MODE == "loop":
            half_points = total_points_needed // 2
            for i in range(half_points):
                ratio = i / half_points
                lat = START_LAT + LAT_OFFSET * ratio
                lng = START_LNG + LNG_OFFSET * ratio
                points.append((lat, lng))
            for i in range(half_points):
                ratio = i / half_points
                lat = START_LAT + LAT_OFFSET * (1 - ratio)
                lng = START_LNG + LNG_OFFSET * (1 - ratio)
                points.append((lat, lng))

        elif TRACK_MODE == "rectangle":
            points_per_side = total_points_needed // 4
            for i in range(points_per_side):
                ratio = i / points_per_side
                points.append((START_LAT, START_LNG + LNG_OFFSET * ratio))
            for i in range(points_per_side):
                ratio = i / points_per_side
                points.append((START_LAT + LAT_OFFSET * ratio, START_LNG + LNG_OFFSET))
            for i in range(points_per_side):
                ratio = i / points_per_side
                points.append((START_LAT + LAT_OFFSET, START_LNG + LNG_OFFSET * (1 - ratio)))
            for i in range(points_per_side):
                ratio = i / points_per_side
                points.append((START_LAT + LAT_OFFSET * (1 - ratio), START_LNG))

        points = self.add_jitter(points)
        return points

    def add_jitter(self, points):
        """添加GPS随机抖动（模拟真实GPS信号波动）"""
        jittered = []
        for lat, lng in points:
            lat_jitter = random.uniform(-0.00008, 0.00008)
            lng_jitter = random.uniform(-0.00008, 0.00008)
            jittered.append((lat + lat_jitter, lng + lng_jitter))
        return jittered

    def haversine_distance(self, lat1, lng1, lat2, lng2):
        """计算两点间的距离（米）"""
        R = 6371000
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lng2 - lng1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def setup_mock_location(self):
        """初始化Mock Location环境（现代Android方式）"""
        try:
            self.device.shell("settings put secure mock_location 1")
            self.device.shell("cmd location providers remove-test-provider gps")
            self.device.shell("cmd location providers add-test-provider gps")
            self.device.shell("cmd location providers set-test-provider-enabled gps true")
            print("[+] Mock Location环境初始化完成")
            return True
        except Exception as e:
            print(f"[-] Mock Location初始化失败: {e}")
            return False

    def cleanup_mock_location(self):
        """清理Mock Location环境"""
        try:
            self.device.shell("cmd location providers set-test-provider-enabled gps false")
            self.device.shell("cmd location providers remove-test-provider gps")
            self.device.shell("settings put secure mock_location 0")
            print("[+] Mock Location环境已清理")
        except Exception as e:
            print(f"[-] Mock Location清理失败: {e}")

    def mock_gps(self, lat, lng):
        """使用现代Android方式模拟GPS位置"""
        try:
            cmd = f"cmd location providers set-test-provider-location gps --location {lat:.6f},{lng:.6f}"
            self.device.shell(cmd)
        except Exception as e:
            print(f"\n[-] GPS模拟失败: {e}")

    def touch(self, x, y):
        """模拟触摸屏幕"""
        try:
            cmd = f"input tap {x} {y}"
            self.device.shell(cmd)
            time.sleep(0.3)
        except Exception as e:
            print(f"[-] 触摸失败: {e}")

    def swipe(self, x1, y1, x2, y2, duration=300):
        """模拟滑动"""
        try:
            cmd = f"input swipe {x1} {y1} {x2} {y2} {duration}"
            self.device.shell(cmd)
        except Exception as e:
            print(f"[-] 滑动失败: {e}")

    def press_key(self, keycode):
        """模拟按键"""
        try:
            cmd = f"input keyevent {keycode}"
            self.device.shell(cmd)
        except Exception as e:
            print(f"[-] 按键失败: {e}")

    def take_screenshot(self, save_path="screenshot.png"):
        """截取手机屏幕"""
        try:
            result = self.device.shell("screencap -p", timeout=10)
            with open(save_path, "wb") as f:
                f.write(result)
            print(f"[+] 截图已保存: {save_path}")
            return True
        except Exception as e:
            print(f"[-] 截图失败: {e}")
            return False

    def gps_loop(self):
        """GPS模拟主循环"""
        print("[*] GPS模拟线程启动")
        self.gps_points = self.generate_route_points()
        print(f"[+] 已生成 {len(self.gps_points)} 个轨迹点")
        print(f"[+] 总距离: {target_RUN_DISTANCE_KM}km, 速度: {RUN_SPEED_KMH}km/h")

        prev_lat, prev_lng = START_LAT, START_LNG
        self.mock_gps(prev_lat, prev_lng)
        print(f"[+] 起始位置: ({prev_lat}, {prev_lng})")

        while self.running:
            if self.paused:
                time.sleep(0.5)
                continue

            for lat, lng in self.gps_points:
                if not self.running:
                    break

                while self.paused and self.running:
                    time.sleep(0.5)

                self.mock_gps(lat, lng)

                dist = self.haversine_distance(prev_lat, prev_lng, lat, lng)
                self.total_distance += dist
                prev_lat, prev_lng = lat, lng

                progress = (self.total_distance / self.target_distance) * 100
                elapsed = self.total_distance / self.speed
                remaining = self.target_distance - self.total_distance
                eta = remaining / self.speed

                mins, secs = divmod(int(elapsed), 60)
                eta_mins, eta_secs = divmod(int(eta), 60)

                sys.stdout.write(
                    f"\r[*] 进度: {progress:5.1f}% | "
                    f"距离: {self.total_distance/1000:.2f}km / {target_RUN_DISTANCE_KM}km | "
                    f"用时: {mins:02d}:{secs:02d} | "
                    f"剩余: {eta_mins:02d}:{eta_secs:02d}"
                )
                sys.stdout.flush()

                time.sleep(GPS_UPDATE_INTERVAL)

            if self.total_distance < self.target_distance and self.running:
                self.gps_points = self.generate_route_points()

        print("\n[*] GPS模拟线程已停止")

    def run_campus(self, auto_click=True):
        """主运行函数：自动完成校园跑"""
        if not self.device:
            if not self.connect_device():
                return

        if not self.setup_mock_location():
            print("[-] Mock Location初始化失败，无法继续")
            return

        print("\n" + "=" * 50)
        print("  校园跑自动化 V1.00")
        print("=" * 50)
        print(f"  目标距离: {target_RUN_DISTANCE_KM} km")
        print(f"  跑步速度: {RUN_SPEED_KMH} km/h")
        print(f"  预计用时: {target_RUN_DISTANCE_KM / RUN_SPEED_KMH * 60:.0f} 分钟")
        print(f"  路线模式: {TRACK_MODE}")
        print("=" * 50)

        self.running = True
        self.gps_thread = threading.Thread(target=self.gps_loop, daemon=True)
        self.gps_thread.start()

        time.sleep(3)

        if auto_click:
            print(f"\n[*] {ACTION_DELAY}秒后点击开始按钮...")
            time.sleep(ACTION_DELAY)
            self.touch(TOUCH_COORDS["start_btn"]["x"], TOUCH_COORDS["start_btn"]["y"])
            print("[+] 已点击开始按钮")

        print("\n[*] 跑步进行中，按 Ctrl+C 可提前结束...")
        self.gps_thread.join()

        if auto_click:
            print(f"\n[*] {ACTION_DELAY}秒后点击结束按钮...")
            time.sleep(ACTION_DELAY)
            self.touch(TOUCH_COORDS["end_btn"]["x"], TOUCH_COORDS["end_btn"]["y"])
            print("[+] 已点击结束按钮")

            time.sleep(1)
            self.touch(TOUCH_COORDS["confirm_btn"]["x"], TOUCH_COORDS["confirm_btn"]["y"])
            print("[+] 已点击确认按钮")

        self.cleanup_mock_location()
        print("\n[+] 校园跑完成！")

    def stop(self):
        """停止运行"""
        self.running = False
        if self.gps_thread and self.gps_thread.is_alive():
            self.gps_thread.join(timeout=3)
        self.cleanup_mock_location()
        print("[*] 已停止")

    def quick_test(self):
        """快速测试连接和GPS模拟"""
        if not self.device:
            if not self.connect_device():
                return

        if not self.setup_mock_location():
            print("[-] Mock Location初始化失败")
            return

        print("\n[*] 测试GPS模拟...")
        print(f"[*] 起点: ({START_LAT}, {START_LNG})")
        self.mock_gps(START_LAT, START_LNG)
        print("[+] 已发送GPS位置")

        time.sleep(2)
        lat2 = START_LAT + LAT_OFFSET
        lng2 = START_LNG + LNG_OFFSET
        self.mock_gps(lat2, lng2)
        print(f"[+] 已移动到: ({lat2}, {lng2})")

        time.sleep(2)
        self.mock_gps(START_LAT, START_LNG)
        print("[+] 已回到起点")

        self.cleanup_mock_location()
        print("\n[+] 测试完成！请检查手机上的地图/跑步APP是否有位置变化。")

    def interactive(self):
        """交互模式"""
        if not self.device:
            if not self.connect_device():
                return

        print("\n" + "=" * 50)
        print("  交互控制模式")
        print("=" * 50)
        print("  1. 测试连接")
        print("  2. 开始跑步（自动GPS+点击）")
        print("  3. 仅模拟GPS轨迹")
        print("  4. 模拟触摸点击")
        print("  5. 截屏")
        print("  6. 按坐标移动GPS")
        print("  q. 退出")
        print("=" * 50)

        while True:
            try:
                choice = input("\n请选择操作 > ").strip().lower()

                if choice == "1":
                    print("[+] 设备已连接:", self.device.serial)
                elif choice == "2":
                    self.run_campus(auto_click=True)
                elif choice == "3":
                    self.run_campus(auto_click=False)
                elif choice == "4":
                    x = int(input("X坐标: "))
                    y = int(input("Y坐标: "))
                    self.touch(x, y)
                    print(f"[+] 已点击 ({x}, {y})")
                elif choice == "5":
                    self.take_screenshot()
                elif choice == "6":
                    lat = float(input("纬度: "))
                    lng = float(input("经度: "))
                    self.mock_gps(lat, lng)
                    print(f"[+] GPS已设置为 ({lat}, {lng})")
                elif choice == "q":
                    print("再见！")
                    break
            except KeyboardInterrupt:
                print("\n[*] 正在停止...")
                self.stop()
                break
            except Exception as e:
                print(f"[-] 错误: {e}")
def main():
    if not ensure_adb():
        print("[-] 无法启动ADB，请手动配置后重试")
        input("按回车键退出...")
        return
    run = CampusRunAutomation()
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "test":
            run.quick_test()
        elif mode == "run":
            try:
                run.run_campus(auto_click=True)
            except KeyboardInterrupt:
                print("\n[!] 用户中断")
                run.stop()
        elif mode == "gps":
            try:
                run.run_campus(auto_click=False)
            except KeyboardInterrupt:
                print("\n[!] 用户中断")
                run.stop()
        elif mode == "shell":
            run.interactive()
        else:
            print("用法:")
            print("  python 校园跑自动运行化脚本.py test   - 快速测试")
            print("  python 校园跑自动运行化脚本.py run     - 完整自动跑步")
            print("  python 校园跑自动运行化脚本.py gps     - 仅GPS轨迹")
            print("  python 校园跑自动运行化脚本.py shell   - 交互模式")
    else:
        run.interactive()
if __name__ == "__main__":
    main()