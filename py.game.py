import pygame
import random
import sys

# 初始化pygame
pygame.init()

# 窗口设置
WIDTH, HEIGHT = 480, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("仿羊了个羊消消乐")

# 颜色定义
GREEN_BG = (113, 184, 95)
SLOT_BG = (88, 153, 71)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
YELLOW = (247, 200, 70)

# 卡牌素材（emoji文字代替图片）
CARD_ICONS = ["🍎", "🍐", "🍊", "🍋", "🍇", "🍓", "🥕", "🌽", "🥦", "🍄"]
MAX_SLOT = 7  # 卡槽最大容量
CARD_SIZE = 52

# 修复：使用默认字体，不再指定simhei
font_card = pygame.font.Font(None, 30)
font_text = pygame.font.Font(None, 20)
font_btn = pygame.font.Font(None, 16)

# 游戏数据
card_list = []
slot_list = []
history = []  # 撤销记录
game_over = False
win = False
tip_msg = "点击卡牌放入卡槽，三张相同自动消除"


class Card:
    def __init__(self, icon, x, y, layer):
        self.icon = icon
        self.x = x
        self.y = y
        self.layer = layer
        self.exist = True  # 是否还在场上
        self.lock = False  # 是否被上层遮挡锁定

    def draw(self):
        if not self.exist:
            return
        rect = pygame.Rect(self.x, self.y, CARD_SIZE, CARD_SIZE)
        # 卡牌底色
        pygame.draw.rect(screen, WHITE, rect, border_radius=8)
        # 锁定变灰
        if self.lock:
            s = pygame.Surface((CARD_SIZE, CARD_SIZE))
            s.set_alpha(150)
            s.fill((100, 100, 100))
            screen.blit(s, rect)
        # 绘制文字图标
        text = font_card.render(self.icon, True, BLACK)
        text_rect = text.get_rect(center=rect.center)
        screen.blit(text, text_rect)

    def is_click(self, mx, my):
        if not self.exist or self.lock:
            return False
        return self.x <= mx <= self.x + CARD_SIZE and self.y <= my <= self.y + CARD_SIZE


def shuffle(arr):
    new_arr = arr.copy()
    random.shuffle(new_arr)
    return new_arr


def init_game():
    global card_list, slot_list, history, game_over, win, tip_msg
    card_list = []
    slot_list = []
    history = []
    game_over = False
    win = False
    tip_msg = "点击卡牌放入卡槽，三张相同自动消除"

    # 生成卡牌池，每种3张
    temp_cards = []
    for icon in CARD_ICONS:
        temp_cards += [icon, icon, icon]
    temp_cards = shuffle(temp_cards)

    pos_list = []
    # 上层12张
    for i in range(12):
        px = 20 + (i % 4) * 62
        py = 80 + (i // 4) * 62
        pos_list.append((px, py, 1))
    # 下层18张
    for i in range(18):
        px = 10 + (i % 6) * 58
        py = 220 + (i // 6) * 58
        pos_list.append((px, py, 2))

    # 创建卡牌对象
    for idx, icon in enumerate(temp_cards):
        x, y, layer = pos_list[idx]
        card_list.append(Card(icon, x, y, layer))
    refresh_lock()


def refresh_lock():
    # 上层有卡牌则下层全部锁定
    has_top = any(c.exist for c in card_list if c.layer == 1)
    for card in card_list:
        if card.layer == 2:
            card.lock = has_top
        else:
            card.lock = False


def check_remove():
    global tip_msg
    icon_map = {}
    for idx, c in enumerate(slot_list):
        if c.icon not in icon_map:
            icon_map[c.icon] = []
        icon_map[c.icon].append(idx)

    remove_index = set()
    remove_cards = []
    for indexes in icon_map.values():
        if len(indexes) >= 3:
            for i in indexes[:3]:
                remove_index.add(i)
    if len(remove_index) == 0:
        check_win()
        return

    # 从后往前删除
    sorted_idx = sorted(list(remove_index), reverse=True)
    for i in sorted_idx:
        remove_cards.append(slot_list[i])
        del slot_list[i]
    history.append({"type": "remove", "cards": remove_cards})
    tip_msg = "成功消除一组！"


def check_win():
    global game_over, win
    # 场上无卡牌 + 卡槽清空 = 胜利
    has_remain = any(c.exist for c in card_list)
    if not has_remain and len(slot_list) == 0:
        game_over = True
        win = True


def click_card(card):
    global tip_msg, game_over
    if len(slot_list) >= MAX_SLOT:
        tip_msg = "卡槽已满，游戏失败！"
        game_over = True
        return
    # 记录操作用于撤销
    history.append({"type": "add", "card": card})
    card.exist = False
    slot_list.append(card)
    refresh_lock()
    check_remove()


def undo_operate():
    global tip_msg
    if not history:
        tip_msg = "没有可撤销的操作"
        return
    last = history.pop()
    if last["type"] == "add":
        # 把卡牌放回场上
        c = last["card"]
        c.exist = True
        slot_list.pop()
        refresh_lock()
    elif last["type"] == "remove":
        # 恢复消除的卡牌
        for c in reversed(last["cards"]):
            slot_list.append(c)
    tip_msg = "已撤销上一步"


def shuffle_board():
    global tip_msg
    remain = [c for c in card_list if c.exist]
    if len(remain) < 3:
        tip_msg = "剩余卡牌太少，无需洗牌"
        return
    pos = [(c.x, c.y) for c in remain]
    pos = shuffle(pos)
    for i, c in enumerate(remain):
        c.x, c.y = pos[i]
    tip_msg = "卡牌已重新洗牌"


# 按钮区域
btn_undo = pygame.Rect(20, 10, 80, 30)
btn_shuffle = pygame.Rect(110, 10, 80, 30)
btn_reset = pygame.Rect(200, 10, 80, 30)


def draw_ui():
    # 背景
    screen.fill(GREEN_BG)

    # 绘制按钮
    pygame.draw.rect(screen, YELLOW, btn_undo, border_radius=6)
    pygame.draw.rect(screen, YELLOW, btn_shuffle, border_radius=6)
    pygame.draw.rect(screen, YELLOW, btn_reset, border_radius=6)
    screen.blit(font_btn.render("撤销", True, BLACK), btn_undo.move(22, 5))
    screen.blit(font_btn.render("洗牌", True, BLACK), btn_shuffle.move(22, 5))
    screen.blit(font_btn.render("重开", True, BLACK), btn_reset.move(22, 5))

    # 绘制所有场上卡牌
    for card in card_list:
        card.draw()

    # 卡槽区域
    slot_rect = pygame.Rect(10, HEIGHT - 90, WIDTH - 20, 80)
    pygame.draw.rect(screen, SLOT_BG, slot_rect, border_radius=10)
    # 绘制卡槽内卡牌
    x_off = 20
    for c in slot_list:
        r = pygame.Rect(slot_rect.x + x_off, slot_rect.y + 12, CARD_SIZE + 4, CARD_SIZE + 4)
        pygame.draw.rect(screen, WHITE, r, border_radius=8)
        t = font_card.render(c.icon, True, BLACK)
        screen.blit(t, t.get_rect(center=r.center))
        x_off += CARD_SIZE + 8

    # 提示文字
    tip_text = font_text.render(tip_msg, True, WHITE)
    screen.blit(tip_text, (20, HEIGHT - 115))

    # 游戏结束弹窗
    if game_over:
        mask = pygame.Surface((WIDTH, HEIGHT))
        mask.set_alpha(150)
        mask.fill((0, 0, 0))
        screen.blit(mask, (0, 0))
        pop_rect = pygame.Rect(90, 250, 300, 180)
        pygame.draw.rect(screen, WHITE, pop_rect, border_radius=12)
        if win:
            pop_text = font_text.render("恭喜通关！", True, BLACK)
        else:
            pop_text = font_text.render("挑战失败", True, BLACK)
        screen.blit(pop_text, pop_text.get_rect(center=(WIDTH//2, 310)))
        restart_btn = pygame.Rect(140, 360, 200, 40)
        pygame.draw.rect(screen, GREEN_BG, restart_btn, border_radius=8)
        restart_text = font_text.render("再来一局", True, WHITE)
        screen.blit(restart_text, restart_text.get_rect(center=restart_btn.center))
        return restart_btn
    return None


# 初始化第一局
init_game()
clock = pygame.time.Clock()

# 主循环
while True:
    clock.tick(60)
    restart_btn = draw_ui()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            # 弹窗再来一局
            if game_over and restart_btn.collidepoint(mx, my):
                init_game()
                continue
            # 按钮点击
            if btn_undo.collidepoint(mx, my):
                undo_operate()
                continue
            if btn_shuffle.collidepoint(mx, my):
                shuffle_board()
                continue
            if btn_reset.collidepoint(mx, my):
                init_game()
                continue
            # 点击场上卡牌
            if not game_over:
                for card in card_list:
                    if card.is_click(mx, my):
                        click_card(card)
                        break
    pygame.display.update()