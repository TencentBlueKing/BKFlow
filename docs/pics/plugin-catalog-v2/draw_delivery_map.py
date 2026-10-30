"""Render the review map, not a deployed-system claim. Requires Pillow."""

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W, H, SCALE = 1440, 1170, 2
FONT = os.environ.get("DIAGRAM_FONT", "/System/Library/Fonts/STHeiti Medium.ttc")
INK, MUTED = "#243651", "#667A95"
BLUE, GREEN, PURPLE, AMBER = "#3C6DC3", "#138978", "#8061BE", "#B37D22"
im = Image.new("RGB", (W * SCALE, H * SCALE), "white")
draw = ImageDraw.Draw(im)


def text(x, y, value, size=24, color=INK, width=None):
    font = ImageFont.truetype(FONT, size * SCALE)
    for index, line in enumerate(value.split("\n")):
        if width is not None:
            assert draw.textlength(line, font=font) <= width * SCALE, (line, width)
        draw.text((x * SCALE, (y + index * size * 1.5) * SCALE), line, font=font, fill=color)


def rect(x, y, w, h, fill="white", border="#CAD6E7", radius=18):
    draw.rounded_rectangle(
        (x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE),
        radius=radius * SCALE,
        fill=fill,
        outline=border,
        width=2 * SCALE,
    )


def box(x, y, w, h, title, detail, fill):
    rect(x, y, w, h, fill)
    text(x + 20, y + 18, title, 27, width=w - 40)
    text(x + 20, y + 64, detail, 23, MUTED, width=w - 40)


def arrow(points, color=BLUE, dashed=False):
    pts = [(x * SCALE, y * SCALE) for x, y in points]
    for a, b in zip(pts, pts[1:]):
        if dashed:
            length = math.dist(a, b)
            for start in range(0, int(length), 18 * SCALE):
                end = min(start + 10 * SCALE, length)
                draw.line(
                    [
                        (a[0] + (b[0] - a[0]) * start / length, a[1] + (b[1] - a[1]) * start / length),
                        (a[0] + (b[0] - a[0]) * end / length, a[1] + (b[1] - a[1]) * end / length),
                    ],
                    fill=color,
                    width=3 * SCALE,
                )
        else:
            draw.line([a, b], fill=color, width=3 * SCALE)
    x, y = pts[-1]
    px, py = pts[-2]
    angle = math.atan2(y - py, x - px)
    draw.polygon(
        [
            (x, y),
            (x - 13 * SCALE * math.cos(angle - 0.45), y - 13 * SCALE * math.sin(angle - 0.45)),
            (x - 13 * SCALE * math.cos(angle + 0.45), y - 13 * SCALE * math.sin(angle + 0.45)),
        ],
        fill=color,
    )


def label(x, y, value, color=BLUE, size=21):
    font = ImageFont.truetype(FONT, size * SCALE)
    longest = max(draw.textlength(line, font=font) for line in value.split("\n")) / SCALE
    rect(x - 5, y - 3, longest + 10, len(value.split("\n")) * size * 1.5, "white", "white", 3)
    text(x, y, value, size, color)


text(40, 28, "插件管理 V2｜开发改动与模块边界", 38)
text(42, 85, "目标设计，尚未实现 · 拆分方向已确认 · 字段兼容与恢复细节见待确认清单", 24, MUTED)

cards = [
    ("4 新增＋3 复用", "模型均归 Interface"),
    ("11 个 HTTP 操作", "9 条路径，按用途鉴权"),
    ("2 新增＋3 改造", "Celery，复用 2 个周期"),
    ("1 个新命令", "存量由运维手动初始化"),
]
for index, (title, detail) in enumerate(cards):
    box(40 + index * 345, 145, 325, 116, title, detail, "#F4F7FC")

rect(40, 300, 600, 715, "#F7F9FE")
rect(930, 300, 470, 715, "#F3FAF7")
text(64, 320, "Interface｜目录管理与校验", 29)
text(954, 320, "Engine｜任务与运行", 29)
text(677, 320, "内部 HTTP", 25, BLUE)
text(670, 360, "既有 Token＋空间上下文", 19, MUTED)

box(70, 390, 540, 208, "Web 进程", "管理接口 · 可选列表 · 当前引用\n新增节点检查 · 运行快照与预检\n手动 AI：返回编辑结果，不保存目录", "#EEF3FD")
box(960, 390, 410, 208, "Web 进程", "空间对应的 Engine 接收任务\n建任务时准备快照\n启动前回调预检", "#E5F5EF")

arrow([(610, 425), (960, 425)], BLUE)
label(676, 398, "① 创建任务 / extra_info", BLUE)
arrow([(960, 495), (610, 495)], GREEN)
label(662, 466, "② 取快照 / 启动预检", GREEN)
arrow([(610, 566), (960, 566)], GREEN, True)
label(675, 535, "③ 快照 / 预检结果", GREEN)

box(70, 690, 250, 158, "Worker / Beat", "2 新增＋3 改造\n复用 2 个周期入口", "#F1EBFA")
box(370, 690, 240, 158, "管理数据", "4 新表＋3 旧模型\n目录、状态、引用", "#FFF4DF")
box(960, 690, 410, 158, "任务数据", "execution_data / extra_info\n快照随任务保存，目录不复制", "#FFF4DF")
arrow([(192, 598), (192, 690)], PURPLE)
label(80, 625, "投递后台工作", PURPLE)
arrow([(490, 598), (490, 690)], AMBER)
label(505, 625, "读写", AMBER)
arrow([(320, 775), (370, 775)], AMBER)
arrow([(1165, 598), (1165, 690)], AMBER)
label(1180, 625, "保存快照", AMBER)

box(70, 910, 540, 82, "手动初始化命令 → 共用初始化服务", "", "#EEF3FD")
arrow([(490, 910), (490, 848)], AMBER)
label(505, 866, "提交", AMBER)
box(960, 910, 410, 82, "Worker · 沿用快照执行任务", "", "#E5F5EF")
arrow([(1165, 848), (1165, 910)], GREEN)

text(660, 660, "边界", 26)
text(660, 708, "不新增 Engine 管理接口\n不让 Engine 直接查目录\n不建立跨模块数据库事务", 21, MUTED, width=260)
text(660, 843, "实线：请求 / 数据写入\n虚线：回调响应\n①②是既有不同调用场景", 20, MUTED, width=260)

text(42, 1046, "数据库物理部署可共享或隔离；图中展示逻辑归属，不假设两套独立数据库。", 24, MUTED)
text(42, 1092, "管理停用不拦截存量运行；精确版本、真实来源权限、内部 HTTP 故障仍需分别处理。", 24, MUTED)

im.save(ROOT / "delivery-map.png")
im.resize((1200, round(H * 1200 / W)), Image.Resampling.LANCZOS).save(ROOT / "delivery-map-preview.png")
print("Rendered delivery-map.png and delivery-map-preview.png")
