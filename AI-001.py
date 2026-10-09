import subprocess
import time
import sys
import random
from pathlib import Path


class SimpleYoudaoBot:
    CONFIG = {
        'mumu': {'port': 7555, 'app_package': 'com.youdao.word',
                 'main_activity': '.activity.MainActivity'},
        'mumu12': {'port': 16384, 'app_package': 'com.youdao.word',
                   'main_activity': '.activity.MainActivity'},
        'leidian': {'port': 5555, 'app_package': 'com.youdao.word',
                    'main_activity': '.activity.MainActivity'},
        'yeshen': {'port': 62001, 'app_package': 'com.youdao.word',
                   'main_activity': '.activity.MainActivity'},
    }

    def __init__(self, emulator='mumu', adb_path='adb'):
        self.adb = adb_path
        self.emulator = emulator
        self.port = self.CONFIG[emulator]['port']
        self.device = f'emulator-{self.port}'
        self.stats = {'done': 0, 'errors': 0}

    def _run(self, *args, timeout=15):
        cmd = [self.adb, '-s', self.device] + list(args)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return r.stdout.strip()
        except Exception as e:
            print(f'[!] ADB 错误: {e}')
            return ''

    def connect(self):
        print(f'[*] 连接 {self.emulator} 模拟器 (端口 {self.port})...')
        self._run('connect', f'127.0.0.1:{self.port}')
        time.sleep(1)
        out = self._run('devices')
        if self.port in out or 'emulator' in out:
            print('[+] 连接成功')
            return True
        print('[-] 连接失败')
        return False

    def launch(self):
        cfg = self.CONFIG[self.emulator]
        pkg = cfg['app_package']
        act = cfg['main_activity']
        print(f'[*] 启动 {pkg}...')
        self._run('shell', 'am', 'start', '-n', f'{pkg}/{act}')
        time.sleep(4)
        print('[+] 已启动')

    def _tap(self, x, y):
        self._run('shell', 'input', 'tap', str(x), str(y))
        time.sleep(0.4 + random.uniform(0.1, 0.3))

    def _swipe(self, x1, y1, x2, y2, duration=300):
        self._run('shell', 'input', 'swipe', str(x1), str(y1), str(x2), str(y2), str(duration))
        time.sleep(0.5)

    def _size(self):
        out = self._run('shell', 'wm', 'size')
        import re
        m = re.search(r'(\d+)x(\d+)', out)
        return (int(m.group(1)), int(m.group(2))) if m else (1080, 1920)

    def _screenshot(self, path):
        self._run('shell', 'screencap', '-p', '/sdcard/tmp.png')
        self._run('pull', '/sdcard/tmp.png', path)
        self._run('shell', 'rm', '/sdcard/tmp.png')

    def click_start_button(self, w, h):
        positions = [
            (w // 2, int(h * 0.65)),
            (w // 2, int(h * 0.7)),
            (w // 2, int(h * 0.75)),
            (int(w * 0.3), int(h * 0.85)),
            (int(w * 0.5), int(h * 0.85)),
            (int(w * 0.7), int(h * 0.85)),
        ]
        for x, y in positions:
            self._tap(x, y)
            time.sleep(0.8)

    def handle_word(self, w, h, strategy='swipe'):
        if strategy == 'tap_know':
            self._tap(int(w * 0.25), int(h * 0.85))
        elif strategy == 'tap_unknown':
            self._tap(int(w * 0.75), int(h * 0.85))
        elif strategy == 'swipe':
            self._swipe(w // 2, int(h * 0.6), w // 2, int(h * 0.35), 300)
        elif strategy == 'random':
            r = random.random()
            if r < 0.4:
                self._tap(int(w * 0.25), int(h * 0.85))
            elif r < 0.7:
                self._tap(int(w * 0.75), int(h * 0.85))
            else:
                self._swipe(w // 2, int(h * 0.6), w // 2, int(h * 0.35), 300)

        time.sleep(0.8)
        self._tap(w // 2, int(h * 0.7))
        time.sleep(0.6)

    def answer_multiple_choice(self, w, h):
        options = [
            (int(w * 0.3), int(h * 0.5)),
            (int(w * 0.3), int(h * 0.6)),
            (int(w * 0.3), int(h * 0.7)),
            (int(w * 0.3), int(h * 0.8)),
        ]
        random.shuffle(options)
        for x, y in options:
            self._tap(x, y)
            time.sleep(1.2)
            self._tap(w // 2, int(h * 0.9))
            time.sleep(0.5)

    def run(self, count=50, mode='mixed'):
        print(f'\n{"=" * 50}')
        print(f' 有道背单词轻量刷词机')
        print(f' 目标: {count} 词 | 模式: {mode}')
        print(f'{"=" * 50}\n')

        if not self.connect():
            return

        self.launch()
        time.sleep(3)

        w, h = self._size()
        print(f'[*] 分辨率: {w}x{h}')

        print('[*] 点击开始学习...')
        self.click_start_button(w, h)
        time.sleep(2)

        strategies = {
            'swipe': lambda i: self.handle_word(w, h, 'swipe'),
            'tap_know': lambda i: self.handle_word(w, h, 'tap_know'),
            'tap_unknown': lambda i: self.handle_word(w, h, 'tap_unknown'),
            'random': lambda i: self.handle_word(w, h, 'random'),
            'mixed': lambda i: (self.answer_multiple_choice(w, h)
                                if random.random() < 0.3
                                else self.handle_word(w, h, 'random')),
        }

        handler = strategies.get(mode, strategies['mixed'])

        for i in range(count):
            print(f'  [{i + 1}/{count}]', end=' ')
            try:
                handler(i)
                self.stats['done'] += 1
                print('✓')
            except Exception as e:
                self.stats['errors'] += 1
                print(f'✗ ({e})')

            if (i + 1) % 10 == 0:
                print(f'  --- 已完成 {i + 1}，继续 ---')
                time.sleep(1)

        print(f'\n[+] 完成! 共刷 {self.stats["done"]} 个词，错误 {self.stats["errors"]} 次')


def main():
    print('''
╔══════════════════════════════════════════════════╗
║     有道背单词 - 轻量刷词机 (无需OCR)           ║
╠══════════════════════════════════════════════════╣
║  支持模拟器: MuMu / MuMu12 / 雷电 / 夜神        ║
║  原理: ADB 模拟点击滑动，按节奏刷词             ║
╚══════════════════════════════════════════════════╝
    ''')

    print('请选择模拟器:')
    print('  1. MuMu 模拟器')
    print('  2. MuMu12 模拟器')
    print('  3. 雷电模拟器')
    print('  4. 夜神模拟器')

    emu_choice = input('选择 [1-4] (默认 1): ').strip() or '1'
    emu_map = {'1': 'mumu', '2': 'mumu12', '3': 'leidian', '4': 'yeshen'}
    emulator = emu_map.get(emu_choice, 'mumu')

    print('\n选择刷词模式:')
    print('  1. 混合模式 (推荐) - 随机答题')
    print('  2. 只点认识')
    print('  3. 只点不认识')
    print('  4. 只滑动 (适合复习模式)')
    print('  5. 随机策略')

    mode_choice = input('选择 [1-5] (默认 1): ').strip() or '1'
    mode_map = {'1': 'mixed', '2': 'tap_know', '3': 'tap_unknown',
                '4': 'swipe', '5': 'random'}
    mode = mode_map.get(mode_choice, 'mixed')

    count = int(input('刷词数量 (默认 50): ').strip() or '50')

    bot = SimpleYoudaoBot(emulator=emulator)
    try:
        bot.run(count=count, mode=mode)
    except KeyboardInterrupt:
        print('\n[!] 已停止')


if __name__ == '__main__':
    main()