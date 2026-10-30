"""Render target call sequences from explicit, editable steps. Requires Pillow."""

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
FONT = os.environ.get("DIAGRAM_FONT", "/System/Library/Fonts/STHeiti Medium.ttc")
W, SCALE = 1440, 2
INK, MUTED, BORDER = "#243651", "#667A95", "#CAD6E7"
BLUE, GREEN, PURPLE, AMBER = "#3C6DC3", "#138978", "#8061BE", "#B37D22"


class Sequence:
    def __init__(self, title, actors, positions, height):
        self.im = Image.new("RGB", (W * SCALE, height * SCALE), "white")
        self.draw = ImageDraw.Draw(self.im)
        self.height = height
        self.positions = positions
        self.text(40, 28, title, 36)
        self.text(42, 82, "目标设计 · 实线：请求 / 动作；虚线：返回；时间从上到下", 24, MUTED)
        for name, x in zip(actors, positions):
            self.rect(x - 120, 136, 240, 92, "#EEF3FD")
            self.center(x, 149, name, 25, width=218)
            self.line([(x, 228), (x, height - 112)], BORDER, dashed=True, head=False, size=2)

    def text(self, x, y, content, size=23, color=INK, width=None):
        font = ImageFont.truetype(FONT, size * SCALE)
        for n, line in enumerate(content.split("\n")):
            if width is not None:
                assert self.draw.textlength(line, font=font) <= width * SCALE, (line, width)
            self.draw.text((x * SCALE, (y + n * size * 1.45) * SCALE), line, font=font, fill=color)

    def center(self, x, y, content, size=23, color=INK, width=None):
        font = ImageFont.truetype(FONT, size * SCALE)
        for n, line in enumerate(content.split("\n")):
            length = self.draw.textlength(line, font=font) / SCALE
            if width is not None:
                assert length <= width, (line, width)
            self.text(x - length / 2, y + n * size * 1.45, line, size, color)

    def rect(self, x, y, width, height, fill, border=None):
        self.draw.rounded_rectangle(
            (x * SCALE, y * SCALE, (x + width) * SCALE, (y + height) * SCALE),
            radius=10 * SCALE,
            fill=fill,
            outline=border or fill,
            width=2 * SCALE,
        )

    def line(self, points, color=BLUE, dashed=False, head=True, size=3):
        ps = [(x * SCALE, y * SCALE) for x, y in points]
        for a, b in zip(ps, ps[1:]):
            if dashed:
                length = math.dist(a, b)
                for d in range(0, int(length), 16 * SCALE):
                    end = min(d + 9 * SCALE, length)
                    self.draw.line(
                        [
                            (a[0] + (b[0] - a[0]) * d / length, a[1] + (b[1] - a[1]) * d / length),
                            (a[0] + (b[0] - a[0]) * end / length, a[1] + (b[1] - a[1]) * end / length),
                        ],
                        fill=color,
                        width=size * SCALE,
                    )
            else:
                self.draw.line([a, b], fill=color, width=size * SCALE)
        if head:
            (px, py), (x, y) = ps[-2:]
            a = math.atan2(y - py, x - px)
            self.draw.polygon(
                [
                    (x, y),
                    (x - 12 * SCALE * math.cos(a - 0.45), y - 12 * SCALE * math.sin(a - 0.45)),
                    (x - 12 * SCALE * math.cos(a + 0.45), y - 12 * SCALE * math.sin(a + 0.45)),
                ],
                fill=color,
            )

    def message(self, sender, receiver, y, label, color=BLUE, returned=False):
        a, b = self.positions[sender], self.positions[receiver]
        self.line([(a, y), (b, y)], color, returned)
        size = 22
        lines = label.split("\n")
        font = ImageFont.truetype(FONT, size * SCALE)
        width = max(self.draw.textlength(v, font=font) / SCALE for v in lines)
        assert width < abs(b - a) - 20, (label, abs(b - a))
        top = y - 12 - len(lines) * size * 1.45
        self.rect((a + b - width) / 2 - 6, top - 2, width + 12, len(lines) * size * 1.45, "white")
        self.center((a + b) / 2, top, label, size, color)

    def note(self, actor, y, label, width=330, color="#FFF4DF", side="right"):
        x = self.positions[actor]
        left = x + 20 if side == "right" else x - width - 20
        self.rect(left, y, width, 82, color)
        self.text(left + 14, y + 10, label, 22, width=width - 28)

    def phase(self, y, label):
        self.rect(40, y, W - 80, 40, "#F1F4F8")
        self.text(55, y + 5, label, 23, MUTED, width=W - 120)

    def footer(self, text):
        self.rect(40, self.height - 105, W - 80, 87, "#F7F9FE")
        self.text(58, self.height - 94, text, 23, MUTED, width=W - 116)

    def save(self, name):
        self.im.save(ROOT / f"{name}.png")
        self.im.resize((1200, round(self.height * 1200 / W)), Image.Resampling.LANCZOS).save(
            ROOT / f"{name}-preview.png"
        )


def save_flow():
    s = Sequence(
        "流程保存｜当前引用与内容一起提交",
        ["调用方\n画布 / 网关", "Interface Web\n共用保存服务", "Interface 数据库\n流程 / 目录 / 引用"],
        [170, 710, 1250],
        1000,
    )
    s.message(0, 1, 305, "提交流程与已授权上下文")
    s.note(1, 330, "检查新增节点\n先于后端重建节点 ID", width=350)
    s.phase(435, "同一数据库事务：最终状态复核 → 写流程 → 更新当前引用")
    s.message(1, 2, 545, "读取并复核插件管理状态", GREEN)
    s.message(1, 2, 625, "按既有入口写流程 / 快照", GREEN)
    s.message(1, 2, 705, "替换当前角色引用，提交事务", GREEN)
    s.message(2, 1, 785, "事务成功", GREEN, True)
    s.message(1, 0, 865, "返回保存结果", BLUE, True)
    s.footer("失败：新增不可选节点被拒绝；流程或引用写入失败一起回滚。\n原创建 / 复制 / 导入 / 回滚例外保留，引用仍更新；不依赖异步统计任务。")
    s.save("sequence-save")


def sync_flow():
    s = Sequence(
        "来源同步｜准入先提交，AI 单独分类",
        [
            "触发方\n周期 / 配置变更",
            "Interface Worker\n同步 / AI 任务",
            "来源系统\n既有 Provider",
            "Interface 数据库\n来源 / 决定 / 目录",
            "bkaidev\n分类接口",
        ],
        [135, 425, 715, 1005, 1295],
        1325,
    )
    s.message(0, 1, 310, "投递来源任务", PURPLE)
    s.message(1, 2, 400, "事务外采集\n蓝鲸复用租户级清单", GREEN)
    s.message(2, 1, 490, "完整结果或明确错误", GREEN, True)
    s.message(1, 3, 580, "校验代次 / 覆盖范围，提交来源状态与首次准入", GREEN)
    s.message(3, 1, 665, "提交结果；失败不覆盖人工决定", GREEN, True)
    s.phase(710, "成功且需要自动 AI：提交后投递分类任务；补投机制待确认 E04")
    s.message(1, 4, 825, "分类摘要、目录、选定范围；使用 BKFlow 应用凭证", PURPLE)
    s.message(4, 1, 915, "分类结果 / 空结果 / 错误", PURPLE, True)
    s.message(1, 3, 1005, "独立目录事务：校验范围 / 修订号 / 重复请求后提交", GREEN)
    s.message(3, 1, 1095, "提交结果；不改审核 / 推荐", GREEN, True)
    s.phase(1140, "可重试来源失败：有限退避；耗尽后低频检查，同一故障不重开快速重试")
    s.footer("首次超时 / 鉴权失败：按实际范围失效，保留管理决定与推荐；只有新成功证据可恢复。\n自动 AI 空结果进未分类；错误单独记录，不改审核。派发失败与 Worker 中断见 E04。")
    s.save("sequence-sync")


def engine_flow():
    s = Sequence(
        "Interface / Engine｜建任务与启动分开",
        ["调用方\n已有执行入口", "Interface Web\n路由 / 快照 / 预检", "Engine Web\n任务入口", "Engine 内部\n任务数据与调度"],
        [150, 530, 910, 1290],
        1480,
    )
    s.message(0, 1, 305, "发起执行请求")
    s.message(1, 2, 390, "按空间路由，创建任务")
    s.message(2, 1, 475, "需要时回调准备运行快照", GREEN)
    s.message(1, 2, 560, "返回引用 / schema 快照", GREEN, True)
    s.message(2, 3, 645, "保存任务与 extra_info", GREEN)
    s.message(2, 1, 730, "任务创建结果", BLUE, True)
    s.message(1, 0, 730, "返回任务标识", BLUE, True)
    s.phase(780, "后续启动请求：内部预检通过后进入既有执行调度；保存流程不会自动执行")
    s.message(0, 1, 890, "启动任务")
    s.message(1, 2, 890, "转发启动请求")
    s.message(2, 1, 975, "回调启动前预检", GREEN)
    s.message(1, 2, 1060, "返回通过 / 明确错误", GREEN, True)
    s.message(2, 3, 1145, "通过后保存状态、派发执行", GREEN)
    s.message(2, 1, 1230, "返回启动结果", BLUE, True)
    s.message(1, 0, 1230, "回显结果", BLUE, True)
    s.phase(1280, "返回启动成功不代表执行完成；运行结果沿用原任务状态链路")
    s.footer("两个模块各自事务，通过既有内部 HTTP 与 Token 交互；Engine 不查询目录 ORM。\n管理停用不拦截存量；真实版本 / 来源授权 / 内部 HTTP 错误仍分别处理。")
    s.save("sequence-engine")


if __name__ == "__main__":
    save_flow()
    sync_flow()
    engine_flow()
    print("Rendered three call sequences and previews")
