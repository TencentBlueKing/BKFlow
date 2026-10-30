"""Render the plugin catalog V2 target architecture; no product code is executed.

Source: docs/specs/2026-10-30-space-plugin-catalog-v2-design.md.
Style: architecture-flow-diagrams skill. Run with Python + Pillow.
"""

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
W, H, SCALE = 1440, 1110, 2
FONT = os.environ.get("DIAGRAM_FONT", "/System/Library/Fonts/STHeiti Medium.ttc")
INK, MUTED = "#243651", "#667A95"
BLUE, GREEN, PURPLE, AMBER = "#3C6DC3", "#138978", "#8061BE", "#B37D22"
im = Image.new("RGB", (W * SCALE, H * SCALE), "white")
draw = ImageDraw.Draw(im)


def text(x, y, value, size=24, color=INK, width=None):
    font = ImageFont.truetype(FONT, size * SCALE)
    for index, line in enumerate(value.split("\n")):
        if width:
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
    text(x + 20, y + 20, title, 28, width=w - 40)
    text(x + 20, y + 72, detail, 23, MUTED, width=w - 40)


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


def label(x, y, value, color=BLUE):
    font = ImageFont.truetype(FONT, 22 * SCALE)
    length = draw.textlength(value, font=font) / SCALE
    rect(x - 5, y - 3, length + 10, 32, "white", "white", 3)
    text(x, y, value, 22, color)


text(40, 28, "插件管理 V2｜目标架构", 38)
text(42, 86, "沿用 BKFlow Interface 与 Engine；新增能力位于现有进程内 · 2026-10-30", 24, MUTED)

rect(400, 150, 610, 860, "#F7F9FE")
text(425, 168, "BKFlow Interface｜管理数据归属", 29)

box(430, 230, 550, 190, "Web 进程 · 插件目录模块", "管理接口 · 可选列表 · 当前引用\n新增节点检查 · AI 调用适配", "#EEF3FD")
box(430, 550, 255, 195, "后台任务", "Worker / Beat\n采集 · 有限重试\n恢复与自动分类", "#F1EBFA")
box(735, 550, 245, 195, "管理数据库", "目录与管理决定\n来源状态与引用\n按空间保存", "#FFF4DF")
box(430, 850, 550, 145, "手动初始化命令", "预览 · 按空间执行 · 可重复运行\n默认 migrate 只建表", "#EEF3FD")

box(40, 230, 300, 190, "管理页 / 两套画布", "管理员整理与审核\n编排者查找与配置节点", "#EEF3FD")
box(40, 550, 300, 195, "插件来源", "内置 · 蓝鲸 · API\nV2 / V3 / V4 逐插件采集\n保留来源分类与精确版本", "#E5F5EF")
box(1070, 230, 330, 190, "BKFlow Engine", "独立运行模块\n使用授权后的运行快照\n不直接查询目录数据库", "#E5F5EF")
box(1070, 610, 330, 180, "bkaidev LLM", "外部模型服务\nBKFlow 自身应用凭证\n只返回分类结果", "#F1EBFA")

arrow([(340, 315), (430, 315)], BLUE)
label(353, 278, "请求", BLUE)
arrow([(980, 315), (1070, 315)], GREEN)
label(995, 278, "快照", GREEN)
arrow([(550, 420), (550, 550)], PURPLE)
label(564, 474, "派发任务", PURPLE)
arrow([(860, 420), (860, 550)], AMBER)
label(872, 474, "读写数据", AMBER)
arrow([(685, 640), (735, 640)], AMBER)
label(688, 603, "提交", AMBER)
arrow([(430, 615), (340, 615)], GREEN)
label(352, 578, "采集", GREEN)
arrow([(340, 695), (430, 695)], GREEN, dashed=True)
label(352, 707, "清单", GREEN)
arrow([(550, 850), (550, 745)], BLUE)
label(564, 757, "初始化", BLUE)
arrow([(980, 380), (1035, 380), (1035, 665), (1070, 665)], PURPLE)
label(1060, 506, "应用态分类请求", PURPLE)
arrow([(1070, 750), (1024, 750), (1024, 445), (935, 445), (935, 420)], PURPLE, dashed=True)
arrow([(685, 710), (710, 710), (710, 790), (1048, 790), (1048, 700), (1070, 700)], PURPLE)
label(755, 758, "自动分类请求", PURPLE)

text(42, 848, "读图说明", 27)
text(42, 893, "实线：请求 / 提交\n虚线：返回结果\n图示为目标设计，尚未实现", 23, MUTED)
text(1070, 855, "恢复闭环", 27)
text(1070, 902, "失败：保留原管理决定\n重试耗尽：低频检查\n成功：恢复原状态与推荐", 23, MUTED, width=330)
text(42, 1045, "目录数据由 Interface 保存；来源故障不覆盖管理员决定，AI 不参与审核。", 25, MUTED)

im.save(ROOT / "architecture.png")
im.resize((1000, round(H * 1000 / W)), Image.Resampling.LANCZOS).save(ROOT / "architecture-preview.png")
print("Rendered architecture.png and architecture-preview.png")
