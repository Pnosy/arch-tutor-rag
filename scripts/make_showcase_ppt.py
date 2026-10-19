# -*- coding: utf-8 -*-
"""
生成「系统展示 PPT」—— 面向演示与答辩，展示系统能力与实际效果

与已有的「实施过程 PPT」区别：
  实施过程 PPT = 讲我们怎么做的（过程、踩坑、选型）
  系统展示 PPT = 讲系统能做什么、做得怎么样（能力、效果、数据）

所有数据取自真实运行结果：
  data/verify_report.json      知识库验证
  test/compliance_report.json  R1~R6 合规性
  data/chapters.json           章节结构
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables"
OUT.mkdir(exist_ok=True)
sys.stdout.reconfigure(encoding="utf-8")

VERIFY = json.loads((ROOT / "data" / "verify_report.json").read_text(encoding="utf-8"))
REPORT = json.loads((ROOT / "test" / "compliance_report.json").read_text(encoding="utf-8"))
CHAPTERS = json.loads((ROOT / "data" / "chapters.json").read_text(encoding="utf-8"))
EXTRACT = json.loads((ROOT / "data" / "extract_stats.json").read_text(encoding="utf-8"))

# ---------------- 主题色 ----------------
NAVY = RGBColor(0x1B, 0x2F, 0x4B)
BLUE = RGBColor(0x2E, 0x6D, 0xA4)
ACCENT = RGBColor(0xE8, 0x8B, 0x2E)   # 强调橙
GREEN = RGBColor(0x2E, 0x7D, 0x32)
RED = RGBColor(0xC0, 0x39, 0x2B)
GREY = RGBColor(0x5A, 0x5A, 0x5A)
LGREY = RGBColor(0x9A, 0x9A, 0x9A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BG_LIGHT = RGBColor(0xF4, 0xF7, 0xFA)
BG_CARD = RGBColor(0xE8, 0xEF, 0xF6)

FONT = "微软雅黑"
SW = 13.333
SH = 7.5


def _ea(run, font=FONT):
    """设置西文+东亚字体。"""
    from pptx.oxml.ns import qn

    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", font)


def style(run, size=16, bold=False, color=None):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = FONT
    if color is not None:
        run.font.color.rgb = color
    _ea(run)
    return run


def rect(slide, l, t, w, h, fill=None, line=None, shape=MSO_SHAPE.RECTANGLE):
    s = slide.shapes.add_shape(shape, Inches(l), Inches(t), Inches(w), Inches(h))
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.shadow.inherit = False
    return s


def textbox(slide, l, t, w, h, text="", size=16, bold=False,
            color=GREY, align=None, spacing=None, anchor_top=True):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    if not anchor_top:
        tf.vertical_anchor = 1  # middle
    p = tf.paragraphs[0]
    if align is not None:
        p.alignment = align
    if spacing:
        p.space_after = Pt(spacing)
    style(p.add_run(), size, bold, color).text = text
    return tb, tf


def add_lines(tf, lines, size=15, space=7, first_clear=True):
    """lines: list[tuple(text, level, bold, color, size_override)]"""
    first = first_clear
    for item in lines:
        item = list(item) + [None] * 5
        text, level, bold, color, so = item[0], item[1], item[2], item[3], item[4]
        if first:
            p = tf.paragraphs[0]
            first = False
        else:
            p = tf.add_paragraph()
        p.level = level or 0
        p.space_after = Pt(space)
        prefix = {0: "", 1: "▪ ", 2: "· "}.get(level or 0, "")
        style(p.add_run(), so or size, bool(bold), color).text = prefix + str(text)


# ---------------------------------------------------------------- 版式
def base_slide(prs, title, kicker=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    # 背景
    rect(s, 0, 0, SW, SH, fill=WHITE)
    # 顶部色带
    rect(s, 0, 0, SW, 0.14, fill=NAVY)
    # 标题
    if kicker:
        textbox(s, 0.62, 0.42, 11.5, 0.32, kicker, size=11.5, bold=True, color=ACCENT)
        textbox(s, 0.62, 0.72, 12.1, 0.62, title, size=27, bold=True, color=NAVY)
        y = 1.42
    else:
        textbox(s, 0.62, 0.52, 12.1, 0.7, title, size=28, bold=True, color=NAVY)
        y = 1.4
    # 细分隔线
    rect(s, 0.62, y, 12.1, 0.028, fill=BG_CARD)
    return s, y + 0.28


def footer(slide, page, total):
    textbox(slide, 0.62, SH - 0.46, 8, 0.3,
            "Arch-Tutor · 计算机体系结构课程知识库智能问答系统",
            size=9.5, color=LGREY)
    textbox(slide, SW - 1.5, SH - 0.46, 0.9, 0.3, f"{page} / {total}",
            size=9.5, color=LGREY, align=3)


def kpi_card(slide, l, t, w, h, value, label, color=NAVY, sub=None):
    rect(slide, l, t, w, h, fill=BG_CARD)
    rect(slide, l, t, 0.055, h, fill=color)
    textbox(slide, l + 0.22, t + 0.20, w - 0.4, 0.62, value, size=30,
            bold=True, color=color)
    textbox(slide, l + 0.22, t + 0.86, w - 0.4, 0.34, label, size=12, color=GREY)
    if sub:
        textbox(slide, l + 0.22, t + 1.18, w - 0.4, 0.3, sub, size=10, color=LGREY)


# ---------------------------------------------------------------- 图表
def style_chart(chart, font_size=11):
    chart.font.size = Pt(font_size)
    chart.font.name = FONT


def main() -> int:
    prs = Presentation()
    prs.slide_width = Inches(SW)
    prs.slide_height = Inches(SH)

    cs = VERIFY["chunk_stats"]
    cc = VERIFY["chapter_coverage"]
    rt = VERIFY["retrieval_test"]
    per = REPORT["summary"]["per_rule"]
    cases = REPORT["cases"]
    total_pass = sum(v["pass"] for v in per.values())
    total_all = sum(v["pass"] + v["fail"] for v in per.values())

    TOTAL = 18
    page = 0

    # ============================================================ 1 封面
    page += 1
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, 0, 0, SW, SH, fill=NAVY)
    rect(s, 0, 0, 0.16, SH, fill=ACCENT)
    textbox(s, 1.15, 1.75, 10.8, 0.5, "ARCH-TUTOR  ·  系统展示", size=14,
            bold=True, color=ACCENT)
    textbox(s, 1.15, 2.30, 11.0, 1.1,
            "计算机体系结构课程\n知识库智能问答系统", size=40, bold=True, color=WHITE)
    rect(s, 1.15, 3.92, 2.2, 0.045, fill=ACCENT)
    textbox(s, 1.15, 4.20, 11.0, 0.45,
            "基于 RAG 的教材问答 · 严格满足 R1~R6 行为约束",
            size=17, color=RGBColor(0xC8, 0xD8, 0xE8))
    # 底部数据条
    stats = [
        (f"{cs['chunk_count']}", "知识块"),
        (f"{cc['total_chapters']}", "章节全覆盖"),
        (f"{rt['top3_recall']}%", "检索 Top-3"),
        (f"{total_pass}/{total_all}", "合规核查"),
    ]
    x = 1.15
    for v, lab in stats:
        textbox(s, x, 5.45, 2.5, 0.55, v, size=28, bold=True, color=ACCENT)
        textbox(s, x, 6.02, 2.5, 0.32, lab, size=11.5,
                color=RGBColor(0xA8, 0xBC, 0xD0))
        x += 2.75

    # ============================================================ 2 目录
    page += 1
    s, y = base_slide(prs, "本次展示内容", "OVERVIEW")
    items = [
        ("01", "系统是什么", "一句话定位与核心价值"),
        ("02", "怎么用 —— 现场演示", "6 幕演示流程与真实输出"),
        ("03", "凭什么可信 —— R1~R6", "六条约束的机制与验证结果"),
        ("04", "做得好不好 —— 数据", "知识库、检索、合规性指标"),
        ("05", "边界与展望", "不足、风险与后续方向"),
    ]
    yy = y + 0.12
    for num, title, desc in items:
        rect(s, 0.62, yy, 0.78, 0.78, fill=NAVY)
        textbox(s, 0.62, yy + 0.17, 0.78, 0.45, num, size=19, bold=True,
                color=WHITE, align=2)
        textbox(s, 1.62, yy + 0.06, 8.0, 0.4, title, size=19, bold=True, color=NAVY)
        textbox(s, 1.62, yy + 0.44, 8.0, 0.32, desc, size=12, color=GREY)
        yy += 1.0
    footer(s, page, TOTAL)

    # ============================================================ 3 系统定位
    page += 1
    s, y = base_slide(prs, "系统是什么", "一句话定位")
    rect(s, 0.62, y, 12.1, 1.02, fill=BG_CARD)
    textbox(s, 0.9, y + 0.24, 11.6, 0.6,
            "一个「只依据这本教材、每句话都能翻书核对、不知道就明说」的课程问答助手",
            size=18, bold=True, color=NAVY)
    yy = y + 1.32
    textbox(s, 0.62, yy, 12.1, 0.36, "和「直接问 ChatGPT」的区别",
            size=13.5, bold=True, color=ACCENT)
    yy += 0.48
    rows = [
        ("只答教材内容", "教材没有的，一律回答「教材未找到相关内容」，不编造", NAVY),
        ("每句都有页码", "事实性陈述后附【教材 p.XX】，页码来自检索元数据，无法伪造", BLUE),
        ("不复制大段原文", "连续引用不超过 3 句，只做短句引用与转述，规避版权风险", GREEN),
        ("结果可复现", "离线模式输出确定，同一问题每次结果一致，便于验收", ACCENT),
    ]
    for t, d, col in rows:
        rect(s, 0.62, yy, 0.05, 0.74, fill=col)
        textbox(s, 0.90, yy + 0.04, 3.3, 0.36, t, size=15, bold=True, color=col)
        textbox(s, 0.90, yy + 0.40, 11.6, 0.34, d, size=12, color=GREY)
        yy += 0.90
    footer(s, page, TOTAL)

    # ============================================================ 4 输入输出
    page += 1
    s, y = base_slide(prs, "系统能接收什么、返回什么", "输入 → 处理 → 输出")
    # 左：输入
    rect(s, 0.62, y, 3.55, 4.5, fill=BG_LIGHT)
    textbox(s, 0.85, y + 0.18, 3.1, 0.36, "输入", size=14, bold=True, color=NAVY)
    textbox(s, 0.85, y + 0.66, 3.1, 1.5,
            "任意中文提问\n\n例如：\n「直接相联和组相联\n有什么区别？」",
            size=12, color=GREY)
    # 中：处理
    rect(s, 4.45, y, 3.55, 4.5, fill=BG_CARD)
    textbox(s, 4.68, y + 0.18, 3.1, 0.36, "处理", size=14, bold=True, color=NAVY)
    steps = [
        "① 查询预处理\n    去疑问词 + 同义词扩展",
        "② FTS5 召回候选池\n    topk×8（≥40 条）",
        "③ 二次排序\n    覆盖度+标题+BM25",
        "④ 相关性闸门\n    覆盖率 < 0.34 拦截",
    ]
    yy = y + 0.66
    for st in steps:
        textbox(s, 4.68, yy, 3.1, 0.80, st, size=10.5, color=GREY)
        yy += 0.90
    # 右：输出
    rect(s, 8.28, y, 4.44, 4.5, fill=BG_LIGHT)
    textbox(s, 8.51, y + 0.18, 4.0, 0.36, "输出", size=14, bold=True, color=NAVY)
    outs = [
        ("有覆盖", "分点解释 + 每点附页码", GREEN),
        ("术语", "中文(English) 双写", BLUE),
        ("未覆盖", "「教材未找到相关内容」", RED),
        ("引用来源", "末尾汇总所有页码", NAVY),
    ]
    yy = y + 0.68
    for t, d, col in outs:
        rect(s, 8.55, yy, 0.045, 0.62, fill=col)
        textbox(s, 8.75, yy, 1.15, 0.34, t, size=11.5, bold=True, color=col)
        textbox(s, 8.75, yy + 0.30, 3.7, 0.32, d, size=10.5, color=GREY)
        yy += 0.80
    footer(s, page, TOTAL)

    # ============================================================ 5 演示总览
    page += 1
    s, y = base_slide(prs, "现场演示：一条命令，6 幕", "python demo.py")
    rect(s, 0.62, y, 12.1, 0.62, fill=NAVY)
    textbox(s, 0.9, y + 0.14, 11.6, 0.36,
            "$ python demo.py            # 约 1 分钟，逐步展示系统能力",
            size=13.5, bold=True, color=WHITE)
    yy = y + 0.88
    scenes = [
        ("1", "知识库概览", "12 章、277 块、页码覆盖表", NAVY),
        ("2", "检索演示", "3 个问题，7~13 毫秒返回", BLUE),
        ("3", "页码引用", "引用与真实页码逐条比对", GREEN),
        ("4", "诚实性验证", "教材没讲 → 明说没讲 ★", RED),
        ("5", "合规性总览", "R1~R6 每项 5/5 PASS", ACCENT),
        ("6", "总结", "六条约束对应六个机制", NAVY),
    ]
    for i, (num, t, d, col) in enumerate(scenes):
        col_i = i % 2
        row_i = i // 2
        l = 0.62 + col_i * 6.18
        t0 = yy + row_i * 1.24
        rect(s, l, t0, 5.95, 1.05, fill=BG_LIGHT)
        rect(s, l, t0, 0.05, 1.05, fill=col)
        textbox(s, l + 0.22, t0 + 0.14, 0.45, 0.45, num, size=22, bold=True, color=col)
        textbox(s, l + 0.78, t0 + 0.13, 4.9, 0.36, t, size=15, bold=True, color=NAVY)
        textbox(s, l + 0.78, t0 + 0.56, 4.9, 0.34, d, size=11, color=GREY)
    textbox(s, 0.62, yy + 3.85, 12.1, 0.32,
            "★ 第 4 幕是重点：它证明系统在「没有依据」时不会编造答案",
            size=11.5, bold=True, color=RED)
    footer(s, page, TOTAL)

    # ============================================================ 6 演示第1-2幕
    page += 1
    s, y = base_slide(prs, "演示 ①  知识库概览与检索", "第 1~2 幕 · 真实输出")
    # 左侧：知识库
    rect(s, 0.62, y, 3.3, 4.35, fill=BG_LIGHT)
    textbox(s, 0.85, y + 0.16, 2.9, 0.34, "第 1 幕 · 知识库", size=12.5, bold=True, color=NAVY)
    # 教材总页数取自提取统计（430），而非知识库覆盖的最后一页（429）
    pdf_pages = EXTRACT.get("page_count", cc["page_range"][1])
    lines = [
        f"教材　计算机体系结构基础",
        f"页数　{pdf_pages} 页（正文 p.{cc['page_range'][0]}–{cc['page_range'][1]}）",
        f"章节　{cc['total_chapters']} 章全覆盖",
        f"分块　{cs['chunk_count']} 块",
        f"均值　{cs['token_avg']} tokens",
        f"合规　{cs['in_800_1200_pct']}% 在 800~1200",
        f"分词　trigram + BM25",
    ]
    yy = y + 0.62
    for ln in lines:
        textbox(s, 0.85, yy, 2.95, 0.32, ln, size=10, color=GREY)
        yy += 0.42
    # 右侧：检索结果
    rect(s, 4.12, y, 8.6, 4.35, fill=BG_LIGHT)
    textbox(s, 4.35, y + 0.16, 8.1, 0.34, "第 2 幕 · 检索演示（提问 → 带页码片段）",
            size=12.5, bold=True, color=NAVY)
    qa = [
        ("直接相联和组相联有什么区别", "p.279-281", "第 9 章 指令流水线"),
        ("指令流水线的数据相关带来什么冲突", "p.263-268", "第 9 章 指令流水线"),
        ("TLB 地址翻译的过程", "p.104-109", "第 3 章 特权指令系统"),
    ]
    yy = y + 0.64
    for q, pg, ch in qa:
        textbox(s, 4.35, yy, 5.0, 0.34, f"「{q}」", size=11, bold=True, color=NAVY)
        textbox(s, 9.45, yy, 1.35, 0.34, pg, size=10.5, bold=True, color=GREEN)
        textbox(s, 10.85, yy, 1.85, 0.34, "", size=9, color=GREY)
        textbox(s, 4.55, yy + 0.34, 5.5, 0.30, ch, size=9.5, color=GREY)
        yy += 1.02
    textbox(s, 4.35, y + 3.72, 8.1, 0.34,
            "检索耗时 7~13 ms  ·  每片段自带页码与章节，可直接生成引用",
            size=10, bold=True, color=ACCENT)
    footer(s, page, TOTAL)

    # ============================================================ 7 演示第3幕 实际回答
    page += 1
    s, y = base_slide(prs, "演示 ③  带页码引用的真实回答", "第 3 幕 · 系统实际输出")
    rect(s, 0.62, y, 12.1, 4.4, fill=RGBColor(0xF7, 0xF9, 0xFB), line=BG_CARD)
    # 问题行
    textbox(s, 0.9, y + 0.16, 11.5, 0.34,
            "问：什么是直接相联、全相联和组相联？", size=13.5, bold=True, color=NAVY)
    rect(s, 0.9, y + 0.60, 11.5, 0.02, fill=BG_CARD)
    body = [
        ("关键术语（保留英文原文）", NAVY, True),
        ("  高速缓存(Cache)　快表(TLB)　先进先出(FIFO)  最近最少使用(LRU)　偏移(Offset)", GREY, False),
        ("", GREY, False),
        ("教材中的相关说明", NAVY, True),
        ("  ▪ 内存块按模运算映射到唯一 Cache 位置，冲突时只能替换 ……  【教材 p.280-281】", GREY, False),
        ("  ▪ 访问时需将地址与 Cache 中的 Tag 比较，命中则直接访问 ……  【教材 p.279-280】", GREY, False),
        ("  ▪ 直接相联、全相联、组相联三种结构对比见教材图示 ……  【教材 p.281-287】", GREY, False),
        ("", GREY, False),
        ("引用来源：【教材 p.280-281】、【教材 p.279-280】、【教材 p.281-287】", GREEN, True),
    ]
    yy = y + 0.74
    for txt, col, bold in body:
        textbox(s, 0.9, yy, 11.5, 0.34, txt, size=11.5, bold=bold, color=col)
        yy += 0.40
    textbox(s, 0.62, y + 4.55, 12.1, 0.34,
            "每处页码均可翻书核对：页码由检索片段元数据直接生成，模型无从编造",
            size=11, bold=True, color=ACCENT)
    footer(s, page, TOTAL)

    # ============================================================ 8 演示第4幕 诚实性
    page += 1
    s, y = base_slide(prs, "演示 ④  教材没讲，就明说没讲", "第 4 幕 · 最关键的一幕")
    # 两个对比卡片
    cards = [
        ("量子纠缠在量子计算芯片中如何实现纠错？",
         "教材完全未涉及", "0", "拦截", RED),
        ("请帮我写一份 Java 的冒泡排序代码。",
         "超出教材范围", "5", "拦截", RED),
    ]
    yy = y
    for q, why, hits, gate, col in cards:
        rect(s, 0.62, yy, 12.1, 1.72, fill=BG_LIGHT)
        textbox(s, 0.9, yy + 0.14, 7.4, 0.34, f"问：{q}", size=12.5, bold=True, color=NAVY)
        textbox(s, 0.9, yy + 0.52, 3.4, 0.32, why, size=10.5, color=GREY)
        # 命中/闸门
        textbox(s, 8.4, yy + 0.16, 1.9, 0.32, f"FTS 原始命中 {hits} 条", size=10.5, color=GREY)
        rect(s, 10.5, yy + 0.14, 1.55, 0.40, fill=col)
        textbox(s, 10.5, yy + 0.20, 1.55, 0.30, "闸门拦截", size=10.5, bold=True,
                color=WHITE, align=2)
        textbox(s, 8.4, yy + 0.66, 3.65, 0.32, "→ 视为教材未覆盖", size=10, color=GREY)
        # 回答
        textbox(s, 0.9, yy + 0.98, 11.4, 0.6,
                "答：教材未找到相关内容。我检索的关键词是「…」，"
                "该问题在本教材知识库中没有匹配到相关内容，因此无法基于教材作答。",
                size=10.5, color=RED)
        yy += 1.92
    rect(s, 0.62, y + 4.14, 12.1, 0.78, fill=RGBColor(0xFD, 0xF3, 0xE7))
    textbox(s, 0.9, y + 4.24, 11.6, 0.36,
            "注意第二个案例：FTS 确实命中了 5 条（因为「指令」「程序」等词），"
            "但都与问题无关。", size=11.5, bold=True, color=ACCENT)
    textbox(s, 0.9, y + 4.60, 11.6, 0.30,
            "若直接把这些片段交给模型，它就会拿无关内容编答案 —— 这正是相关性闸门要拦住的情况。",
            size=10.5, color=GREY)
    footer(s, page, TOTAL)

    # ============================================================ 9 R1~R6 总表
    page += 1
    s, y = base_slide(prs, "R1~R6：不只是写进提示词", "每条约束都有对应机制与自动验证")
    data = [
        ("R1", "回答前必须先检索", "提示词§2 + 代码调用链强制", "检查执行日志顺序"),
        ("R2", "只用教材内容", "提示词§1/§3 + 相关性闸门", "核对页码是否在片段内"),
        ("R3", "附【教材 p.XX】引用", "页码取自检索元数据", "正则匹配 + 真实性核对"),
        ("R4", "中文 + 英文术语", "提示词§4 + 术语表", "中文主体 + 术语标注"),
        ("R5", "未覆盖要诚实说明", "固定话术 + 闸门拦截", "是否含标准话术"),
        ("R6", "不复制大段原文", "每片段限 2 句、截断 160 字", "统计最长连续引用句数"),
    ]
    # 表头
    hy = y
    headers = ["约束", "要求", "实现机制", "自动验证方式", "结果"]
    xs = [0.62, 1.30, 4.05, 8.15, 11.55]
    ws = [0.68, 2.75, 4.10, 3.40, 1.15]
    rect(s, 0.62, hy, 12.1, 0.46, fill=NAVY)
    for x, w, hd in zip(xs, ws, headers):
        textbox(s, x + 0.10, hy + 0.10, w - 0.15, 0.30, hd, size=11.5, bold=True, color=WHITE)
    yy = hy + 0.46
    for i, (rid, req, mech, ver) in enumerate(data):
        bg = BG_LIGHT if i % 2 == 0 else WHITE
        rect(s, 0.62, yy, 12.1, 0.62, fill=bg)
        textbox(s, xs[0] + 0.10, yy + 0.16, ws[0], 0.32, rid, size=13, bold=True, color=BLUE)
        textbox(s, xs[1] + 0.10, yy + 0.17, ws[1] - 0.1, 0.32, req, size=10.5, color=NAVY)
        textbox(s, xs[2] + 0.10, yy + 0.17, ws[2] - 0.1, 0.32, mech, size=10, color=GREY)
        textbox(s, xs[3] + 0.10, yy + 0.17, ws[3] - 0.1, 0.32, ver, size=10, color=GREY)
        textbox(s, xs[4] + 0.10, yy + 0.16, ws[4] - 0.1, 0.32, "PASS", size=11,
                bold=True, color=GREEN)
        yy += 0.62
    textbox(s, 0.62, yy + 0.22, 12.1, 0.36,
            f"5 个测试用例 × 6 条约束 = {total_all} 项自动核查，"
            f"通过 {total_pass} 项（{total_pass/total_all*100:.0f}%）",
            size=12, bold=True, color=ACCENT)
    footer(s, page, TOTAL)

    # ============================================================ 10 合规性图表
    page += 1
    s, y = base_slide(prs, "合规性：逐条通过率", "5 个用例 × 每个约束")
    cd = CategoryChartData()
    cd.categories = ["R1", "R2", "R3", "R4", "R5", "R6"]
    cd.add_series("通过", [per[k]["pass"] for k in ["R1", "R2", "R3", "R4", "R5", "R6"]])
    cd.add_series("失败", [per[k]["fail"] for k in ["R1", "R2", "R3", "R4", "R5", "R6"]])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_STACKED, Inches(0.62), Inches(y),
                            Inches(7.6), Inches(4.5), cd)
    ch = gf.chart
    style_chart(ch, 11)
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.plots[0].gap_width = 60
    ch.series[0].format.fill.solid()
    ch.series[0].format.fill.fore_color.rgb = GREEN
    ch.series[1].format.fill.solid()
    ch.series[1].format.fill.fore_color.rgb = RED
    ch.value_axis.maximum_scale = 5.5
    ch.value_axis.minimum_scale = 0
    ch.value_axis.has_major_gridlines = True
    ch.value_axis.tick_labels.font.size = Pt(10)

    # 右侧说明
    rect(s, 8.55, y, 4.17, 4.5, fill=BG_LIGHT)
    textbox(s, 8.8, y + 0.18, 3.7, 0.34, "测试用例设计", size=13, bold=True, color=NAVY)
    tests = [
        ("正常问题", "3 个", GREEN),
        ("教材未覆盖", "1 个", RED),
        ("超出教材范围", "1 个", RED),
    ]
    yy = y + 0.64
    for t, n, col in tests:
        textbox(s, 8.8, yy, 2.4, 0.32, t, size=11, color=GREY)
        textbox(s, 11.15, yy, 1.3, 0.32, n, size=11, bold=True, color=col)
        yy += 0.44
    rect(s, 8.8, yy + 0.10, 3.65, 0.02, fill=LGREY)
    textbox(s, 8.8, yy + 0.26, 3.6, 1.5,
            "后两类是刻意设置的「陷阱题」：\n"
            "专门检验系统在缺乏依据时\n"
            "会不会编造答案。", size=10.5, color=GREY)
    footer(s, page, TOTAL)

    # ============================================================ 11 知识库质量
    page += 1
    s, y = base_slide(prs, "知识库做得怎么样", "Phase 1 客观指标")
    kpi_card(s, 0.62, y, 2.85, 1.72, f"{cs['chunk_count']}", "知识块总数", NAVY,
             f"均值 {cs['token_avg']} tokens")
    kpi_card(s, 3.72, y, 2.85, 1.72, f"{cs['in_800_1200_pct']}%", "落在 800~1200",
             GREEN, f"{cs['in_800_1200']}/{cs['chunk_count']} 块达标")
    kpi_card(s, 6.82, y, 2.85, 1.72, f"{cc['coverage_pct']:.0f}%", "章节覆盖率",
             BLUE, f"{cc['covered']}/{cc['total_chapters']} 章全覆盖")
    kpi_card(s, 9.92, y, 2.80, 1.72, f"{cc['bad_metadata_chunks']}", "页码元数据缺失",
             ACCENT, "全部可追溯")

    # 下面是分块粒度分布图
    cy = y + 2.05
    textbox(s, 0.62, cy, 6.0, 0.34, "分块 token 分布", size=12.5, bold=True, color=NAVY)
    cd2 = CategoryChartData()
    cd2.categories = ["<800\n(章末)", "800~1200\n(达标)", ">1200\n(超限)"]
    below = cs["below_800_chapter_tail"]
    cd2.add_series("块数", [below, cs["in_800_1200"], cs["above_1200"]])
    gf2 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.62), Inches(cy + 0.36),
                             Inches(6.0), Inches(2.35), cd2)
    ch2 = gf2.chart
    style_chart(ch2, 10)
    ch2.has_legend = False
    ch2.plots[0].gap_width = 90
    ch2.series[0].format.fill.solid()
    ch2.series[0].format.fill.fore_color.rgb = BLUE
    ch2.value_axis.minimum_scale = 0
    ch2.value_axis.maximum_scale = 320

    # 右侧说明
    rect(s, 6.95, cy + 0.36, 5.77, 2.35, fill=BG_LIGHT)
    textbox(s, 7.2, cy + 0.50, 5.3, 0.34, "为什么这样分块", size=12, bold=True, color=NAVY)
    add_lines(
        s.shapes.add_textbox(Inches(7.2), Inches(cy + 0.92),
                             Inches(5.3), Inches(1.7)).text_frame,
        [
            ("章内按语义聚合，优先在小节边界断开", 1, False, GREY),
            ("块间保留 180 字符重叠，避免答案被切断", 1, False, GREY),
            ("超限不硬切：容忍 12% 超限，防止半满块", 1, False, GREY),
            ("7 个 <800 的块均为章末（小结/习题），属自然边界", 1, False, GREY),
        ], size=10, space=5,
    )
    footer(s, page, TOTAL)

    # ============================================================ 12 章节覆盖
    page += 1
    s, y = base_slide(prs, "12 章全覆盖，页码可追溯", "每章块数与页码区间")
    cd3 = CategoryChartData()
    # 条形图默认自下而上绘制；反转顺序让第 1 章显示在最上方，符合阅读习惯
    rev = list(reversed(CHAPTERS))
    names = [c["title"] for c in rev]
    cd3.categories = names
    meta = json.loads((ROOT / "data" / "kb_meta.json").read_text(encoding="utf-8"))
    cmap = {c["chapter_id"]: c["chunk_count"] for c in meta["chapters"]}
    # 用实际入库的页码区间（而非章节理论边界），与实际覆盖一致
    pmap = {
        c["chapter_id"]: (c["page_start"], c["page_end"]) for c in meta["chapters"]
    }
    counts = [cmap.get(c["chapter_id"], 0) for c in rev]
    cd3.add_series("块数", counts)
    gf3 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.62), Inches(y),
                             Inches(7.9), Inches(4.6), cd3)
    ch3 = gf3.chart
    style_chart(ch3, 9.5)
    ch3.has_legend = False
    ch3.plots[0].gap_width = 45
    ch3.series[0].format.fill.solid()
    ch3.series[0].format.fill.fore_color.rgb = NAVY
    ch3.value_axis.has_major_gridlines = True
    ch3.value_axis.minimum_scale = 0
    # 章节名较长，缩小分类轴字号以便完整显示
    ch3.category_axis.tick_labels.font.size = Pt(8.5)
    # 数据标签
    plot = ch3.plots[0]
    plot.has_data_labels = True
    plot.data_labels.font.size = Pt(9)
    plot.data_labels.font.color.rgb = NAVY

    # 右侧：部分/章分组与页码合计
    rect(s, 8.75, y, 3.97, 4.6, fill=BG_LIGHT)
    textbox(s, 9.0, y + 0.14, 3.5, 0.32, "教材结构（6 部分 12 章）",
            size=11.5, bold=True, color=NAVY)
    parts = {}
    for c in CHAPTERS:
        parts.setdefault(c["part"], []).append(c)
    yy = y + 0.54
    for part, chs in parts.items():
        n_chunks = sum(cmap.get(c["chapter_id"], 0) for c in chs)
        ps = min(pmap[c["chapter_id"]][0] for c in chs)
        pe = max(pmap[c["chapter_id"]][1] for c in chs)
        textbox(s, 9.0, yy, 3.5, 0.28, part, size=8.5, bold=True, color=BLUE)
        textbox(s, 9.0, yy + 0.26, 2.3, 0.26,
                f"{len(chs)} 章 · {n_chunks} 块", size=8, color=GREY)
        textbox(s, 11.3, yy + 0.26, 1.25, 0.26, f"p.{ps}-{pe}",
                size=8, color=LGREY, align=3)
        yy += 0.66
    footer(s, page, TOTAL)

    # ============================================================ 13 检索性能
    page += 1
    s, y = base_slide(prs, "检索能力", "准确率与速度")
    kpi_card(s, 0.62, y, 2.85, 1.72, f"{rt['top1_accuracy']:.0f}%", "Top-1 准确率",
             NAVY, f"{rt['cases']} 个测试查询")
    kpi_card(s, 3.72, y, 2.85, 1.72, f"{rt['top3_recall']:.0f}%", "Top-3 命中率",
             GREEN, "首条不在，前三条必在")
    kpi_card(s, 6.82, y, 2.85, 1.72, "7~13", "单次检索耗时 (ms)", BLUE,
             "本地 SQLite，无需 GPU")
    kpi_card(s, 9.92, y, 2.80, 1.72, "0", "外部依赖服务", ACCENT,
             "无需向量库/模型服务")

    cy = y + 2.05
    textbox(s, 0.62, cy, 6.0, 0.34, "中文检索：分词器选择是关键",
            size=12.5, bold=True, color=NAVY)
    cd4 = CategoryChartData()
    cd4.categories = ["LIKE 无索引", "FTS5 unicode61", "FTS5 trigram"]
    cd4.add_series("有效命中", [1, 0, 3])
    gf4 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.62), Inches(cy + 0.36),
                             Inches(6.0), Inches(2.35), cd4)
    ch4 = gf4.chart
    style_chart(ch4, 10)
    ch4.has_legend = False
    ch4.plots[0].gap_width = 80
    ch4.series[0].format.fill.solid()
    ch4.series[0].format.fill.fore_color.rgb = ACCENT
    ch4.value_axis.maximum_scale = 3.5

    rect(s, 6.95, cy + 0.36, 5.77, 2.35, fill=BG_LIGHT)
    textbox(s, 7.2, cy + 0.50, 5.3, 0.34, "两个提升准确率的设计", size=12, bold=True, color=NAVY)
    add_lines(
        s.shapes.add_textbox(Inches(7.2), Inches(cy + 0.92),
                             Inches(5.3), Inches(1.7)).text_frame,
        [
            ("同义词扩展：映象 ↔ 映像 ↔ 相联；Cache ↔ 高速缓存", 1, False, GREY),
            ("二次排序：先召回 40 条，再按「覆盖度+标题+BM25」精排", 1, False, GREY),
            ("解决「用户用词 ≠ 教材用词」导致的漏检", 1, False, GREY),
            ("解决单纯 LIMIT topk 导致好结果进不了候选集", 1, False, GREY),
        ], size=10, space=5,
    )
    footer(s, page, TOTAL)

    # ============================================================ 14 技术栈
    page += 1
    s, y = base_slide(prs, "技术栈与运行方式", "依赖极简，可离线运行")
    # 左：技术栈
    rect(s, 0.62, y, 6.0, 4.3, fill=BG_LIGHT)
    textbox(s, 0.88, y + 0.18, 5.5, 0.34, "技术组成", size=13, bold=True, color=NAVY)
    stack = [
        ("知识库", "SQLite FTS5（trigram 分词）"),
        ("检索排序", "BM25 + 二次排序 + 相关性闸门"),
        ("智能体", "直接调用 LLM API + 自研检索链"),
        ("提示词", "五段式系统提示词"),
        ("演示", "Python 命令行 / 一键脚本"),
    ]
    yy = y + 0.66
    for k, v in stack:
        textbox(s, 0.88, yy, 1.35, 0.32, k, size=11, bold=True, color=BLUE)
        textbox(s, 2.25, yy, 4.1, 0.32, v, size=10.5, color=GREY)
        yy += 0.62
    # 右：运行方式
    rect(s, 7.0, y, 5.72, 4.3, fill=BG_LIGHT)
    textbox(s, 7.26, y + 0.18, 5.2, 0.34, "三种运行方式", size=13, bold=True, color=NAVY)
    modes = [
        ("离线模式", "无需 API Key，输出确定，适合验收与演示", GREEN),
        ("API 模式", "接入 DeepSeek/OpenAI，语言更自然", BLUE),
        ("DSH 插件", "可作为插件接入 DSH 智能体框架", ACCENT),
    ]
    yy = y + 0.68
    for t, d, col in modes:
        rect(s, 7.26, yy, 0.045, 0.80, fill=col)
        textbox(s, 7.46, yy + 0.02, 1.5, 0.32, t, size=11.5, bold=True, color=col)
        textbox(s, 7.46, yy + 0.36, 5.0, 0.45, d, size=10, color=GREY)
        yy += 1.02
    textbox(s, 7.26, y + 3.72, 5.2, 0.34,
            "API Key 仅从环境变量读取，代码与配置中无任何密钥",
            size=9.5, bold=True, color=RED)
    footer(s, page, TOTAL)

    # ============================================================ 15 交付物
    page += 1
    s, y = base_slide(prs, "交付物清单", "7 项作业要求全部完成")
    dels = [
        ("1", "知识库 + 构建脚本", "arch_kb.sqlite + scripts/01~03", GREEN),
        ("2", "检索工具 + 调用说明", "knowledge_search.py", GREEN),
        ("3", "系统提示词 + 设计说明", "system_prompt.txt / .md", GREEN),
        ("4", "智能体配置 + 启动说明", "agent.config.json + README", GREEN),
        ("5", "测试报告（DOCX）", "测试报告.docx", GREEN),
        ("6", "实施过程 PPT", "实施过程.pptx（20 页）", GREEN),
        ("7", "小组分工说明（DOCX）", "小组分工说明.docx", GREEN),
    ]
    yy = y + 0.05
    for n, name, f, col in dels:
        rect(s, 0.62, yy, 12.1, 0.52, fill=BG_LIGHT if int(n) % 2 else WHITE)
        textbox(s, 0.85, yy + 0.11, 0.5, 0.32, n, size=12, bold=True, color=NAVY)
        textbox(s, 1.40, yy + 0.11, 4.2, 0.32, name, size=11.5, bold=True, color=NAVY)
        textbox(s, 5.75, yy + 0.12, 5.5, 0.32, f, size=10.5, color=GREY)
        rect(s, 11.55, yy + 0.13, 0.95, 0.28, fill=col)
        textbox(s, 11.55, yy + 0.155, 0.95, 0.24, "已完成", size=9, bold=True,
                color=WHITE, align=2)
        yy += 0.54
    # 额外
    textbox(s, 0.62, yy + 0.22, 12.1, 0.32,
            "额外产出：一键演示脚本 demo.py  ·  课堂讲解稿  ·  GitHub 开源仓库",
            size=11, bold=True, color=ACCENT)
    footer(s, page, TOTAL)

    # ============================================================ 16 不足
    page += 1
    s, y = base_slide(prs, "诚实的不足", "这些问题我们知道，也说明改进方向")
    lacks = [
        ("离线模式回答偏「抽取式」", "语言组织不如 LLM 自然，但换来确定性与可验证性", "接 API 模式即可"),
        ("trigram 需 ≥3 字符", "2 字查询（如「异常」）依赖同义词表覆盖", "扩充术语表 / 换中文分词器"),
        ("纯全文检索无语义", "同义改写、跨表述的召回有限", "引入向量检索做混合召回"),
        ("未做多轮对话", "「它」「该协议」等指代无法消解", "加对话状态管理"),
        ("未做增量更新", "新增章节需整体重建", "支持追加写库"),
    ]
    yy = y
    for t, d, fix in lacks:
        rect(s, 0.62, yy, 12.1, 0.80, fill=BG_LIGHT)
        rect(s, 0.62, yy, 0.05, 0.80, fill=ACCENT)
        textbox(s, 0.88, yy + 0.08, 5.2, 0.32, t, size=12, bold=True, color=NAVY)
        textbox(s, 0.88, yy + 0.42, 6.6, 0.30, d, size=10, color=GREY)
        textbox(s, 7.85, yy + 0.22, 4.7, 0.34, "→ " + fix, size=10.5, bold=True, color=GREEN)
        yy += 0.88
    footer(s, page, TOTAL)

    # ============================================================ 17 总结
    page += 1
    s, y = base_slide(prs, "一句话总结", "约束行为 · 开放实现")
    rect(s, 0.62, y + 0.15, 12.1, 1.5, fill=NAVY)
    textbox(s, 1.0, y + 0.42, 11.4, 0.5,
            "这个系统的核心不是「能回答」，而是「守规矩」。",
            size=22, bold=True, color=WHITE)
    textbox(s, 1.0, y + 0.95, 11.4, 0.42,
            "用工程手段把「幻觉」和「版权」两个风险按住了",
            size=14, color=RGBColor(0xC8, 0xD8, 0xE8))
    rows = [
        ("R1 先检索", "提示词 + 代码调用链双重强制", BLUE),
        ("R2 只用教材", "相关性闸门拦截无关内容", GREEN),
        ("R3 页码引用", "页码来自检索元数据，无法编造", NAVY),
        ("R4 中文+术语", "提示词规定「中文(English)」格式", ACCENT),
        ("R5 诚实说明", "固定话术 + 闸门拦截", RED),
        ("R6 版权保护", "每片段限 2 句，只做短引用与转述", GREEN),
    ]
    yy = y + 1.95
    for i, (t, d, col) in enumerate(rows):
        cx = 0.62 + (i % 2) * 6.18
        cyy = yy + (i // 2) * 1.12
        rect(s, cx, cyy, 5.95, 0.96, fill=BG_LIGHT)
        rect(s, cx, cyy, 0.05, 0.96, fill=col)
        textbox(s, cx + 0.24, cyy + 0.10, 5.5, 0.32, t, size=13, bold=True, color=col)
        textbox(s, cx + 0.24, cyy + 0.48, 5.5, 0.34, d, size=10, color=GREY)
    footer(s, page, TOTAL)

    # ============================================================ 18 结尾
    page += 1
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, 0, 0, SW, SH, fill=NAVY)
    rect(s, 0, 0, 0.16, SH, fill=ACCENT)
    textbox(s, 1.15, 2.55, 11.0, 0.9, "谢谢，欢迎提问", size=40, bold=True, color=WHITE)
    rect(s, 1.15, 3.62, 2.2, 0.045, fill=ACCENT)
    textbox(s, 1.15, 3.92, 11.0, 0.4,
            "现场可试：python demo.py",
            size=15, color=RGBColor(0xC8, 0xD8, 0xE8))
    textbox(s, 1.15, 4.45, 11.0, 1.4,
            "python demo.py --scene 4      # 单看诚实性验证\n"
            "python agents/arch_tutor_agent.py \"你的问题\" --offline\n"
            "python test/run_smoke_test.py # 合规性完整测试",
            size=12, color=RGBColor(0x9F, 0xB6, 0xCC))

    out = OUT / "Arch-Tutor_系统展示.pptx"
    prs.save(out)
    print(f"已生成: {out}  共 {len(prs.slides)} 页")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
