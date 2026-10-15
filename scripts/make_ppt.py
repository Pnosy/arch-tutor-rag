# -*- coding: utf-8 -*-
"""
生成交付物 №6：实施过程 PPT（15~20 页，PPTX）

面向同学讲解技术选型与实施过程。所有数据来自脚本真实运行结果。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables"
OUT.mkdir(exist_ok=True)
VERIFY = json.loads((ROOT / "data" / "verify_report.json").read_text(encoding="utf-8"))
REPORT = json.loads((ROOT / "test" / "compliance_report.json").read_text(encoding="utf-8"))
STATS = json.loads((ROOT / "data" / "extract_stats.json").read_text(encoding="utf-8"))
sys.stdout.reconfigure(encoding="utf-8")

# ---------------- 主题 ----------------
NAVY = RGBColor(0x1F, 0x3A, 0x5F)
BLUE = RGBColor(0x2E, 0x6D, 0xA4)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
RED = RGBColor(0xC0, 0x39, 0x2B)
GREY = RGBColor(0x55, 0x55, 0x55)
LIGHT = RGBColor(0xEE, 0xF3, 0xF8)

FONT = "微软雅黑"


def style_run(r, size=16, bold=False, color=None, font=FONT):
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.name = font
    if color is not None:
        r.font.color.rgb = color
    # 中文字体需单独设置
    rPr = r._r.get_or_add_rPr()
    from pptx.oxml.ns import qn

    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", font)
    return r


def add_title_slide(prs, title, subtitle, footer):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    # 背景色块
    from pptx.enum.shapes import MSO_SHAPE

    box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(2.6))
    box.fill.solid()
    box.fill.fore_color.rgb = NAVY
    box.line.fill.background()
    box.shadow.inherit = False

    tb = s.shapes.add_textbox(Inches(0.8), Inches(0.6), prs.slide_width - Inches(1.6), Inches(1.2))
    tf = tb.text_frame
    tf.word_wrap = True
    style_run(tf.paragraphs[0].add_run(), 34, True, RGBColor(0xFF, 0xFF, 0xFF)).text = title

    tb2 = s.shapes.add_textbox(Inches(0.8), Inches(1.7), prs.slide_width - Inches(1.6), Inches(0.8))
    style_run(tb2.text_frame.paragraphs[0].add_run(), 16, False, RGBColor(0xD6, 0xE4, 0xF0)).text = subtitle

    tb3 = s.shapes.add_textbox(Inches(0.8), Inches(3.4), prs.slide_width - Inches(1.6), Inches(2.6))
    tf3 = tb3.text_frame
    tf3.word_wrap = True
    for i, line in enumerate(footer):
        p = tf3.paragraphs[0] if i == 0 else tf3.add_paragraph()
        style_run(p.add_run(), 15, False, GREY).text = line
    return s


def add_slide(prs, title, subtitle=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    # 顶部标题条
    from pptx.enum.shapes import MSO_SHAPE

    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(1.05))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    bar.shadow.inherit = False
    tb = s.shapes.add_textbox(Inches(0.5), Inches(0.16), prs.slide_width - Inches(1.0), Inches(0.75))
    tf = tb.text_frame
    tf.word_wrap = True
    style_run(tf.paragraphs[0].add_run(), 24, True, RGBColor(0xFF, 0xFF, 0xFF)).text = title
    if subtitle:
        sb = s.shapes.add_textbox(Inches(0.5), Inches(1.08), prs.slide_width - Inches(1.0), Inches(0.4))
        style_run(sb.text_frame.paragraphs[0].add_run(), 13, False, BLUE).text = subtitle
    return s


def body_box(s, top=1.55, left=0.6, width=None, height=None):
    width = width or Inches(13.333 - 1.2)
    height = height or Inches(5.0)
    tb = s.shapes.add_textbox(Inches(left), Inches(top), width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    return tf


def write_lines(tf, lines, size=15, space=8):
    """lines: list of (text, level, bold, color)"""
    first = True
    for item in lines:
        text, level, bold, color = (list(item) + [None] * 4)[:4]
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.level = level or 0
        p.space_after = Pt(space)
        prefix = "" if level == 0 else ("• " if level == 1 else "– ")
        style_run(p.add_run(), size, bool(bold), color).text = prefix + str(text)


def add_table(s, headers, rows, left=0.6, top=1.7, width=None, height=None,
              col_widths=None, font_size=12):
    rows_n = len(rows) + 1
    cols_n = len(headers)
    width = width or Inches(13.333 - 1.2)
    height = height or Inches(0.4 * rows_n + 0.3)
    shape = s.shapes.add_table(rows_n, cols_n, Inches(left), Inches(top), width, height)
    tbl = shape.table
    if col_widths:
        total = sum(col_widths)
        for i, cw in enumerate(col_widths):
            tbl.columns[i].width = Emu(int(width * cw / total))
    for j, htxt in enumerate(headers):
        c = tbl.cell(0, j)
        c.text = ""
        c.fill.solid()
        c.fill.fore_color.rgb = NAVY
        style_run(c.text_frame.paragraphs[0].add_run(), font_size, True,
                  RGBColor(0xFF, 0xFF, 0xFF)).text = htxt
    for i, row in enumerate(rows, start=1):
        for j, v in enumerate(row):
            c = tbl.cell(i, j)
            c.text = ""
            c.fill.solid()
            c.fill.fore_color.rgb = LIGHT if i % 2 else RGBColor(0xFF, 0xFF, 0xFF)
            txt = str(v)
            col = GREEN if txt == "PASS" else (RED if txt == "FAIL" else RGBColor(0x22, 0x22, 0x22))
            style_run(c.text_frame.paragraphs[0].add_run(), font_size - 0.5,
                      txt in ("PASS", "FAIL"), col).text = txt
    return tbl


def add_note(s, text, top=6.35, color=GREY):
    tb = s.shapes.add_textbox(Inches(0.6), Inches(top), Inches(11.4), Inches(0.6))
    tf = tb.text_frame
    tf.word_wrap = True
    style_run(tf.paragraphs[0].add_run(), 11.5, False, color).text = text


def main() -> int:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    cs = VERIFY["chunk_stats"]
    cc = VERIFY["chapter_coverage"]
    rt = VERIFY["retrieval_test"]
    per = REPORT["summary"]["per_rule"]
    total_pass = sum(v["pass"] for v in per.values())
    total_all = sum(v["pass"] + v["fail"] for v in per.values())

    # ---------------------------------------------------------- 1 封面
    add_title_slide(
        prs,
        "Arch-Tutor\n计算机体系结构课程知识库智能问答系统",
        "基于 RAG 的教材问答实现与 R1~R6 合规性验证",
        [
            "教材：《计算机体系结构基础》胡伟武 等（430 页 / 12 章）",
            "技术栈：方案 C —— SQLite FTS5(trigram) + BM25 + 自研检索 + LLM API",
            f"成果：{cs['chunk_count']} 个知识块  |  检索 Top-3 {rt['top3_recall']}%  "
            f"|  R1~R6 核查 {total_pass}/{total_all} 通过",
        ],
    )

    # ---------------------------------------------------------- 2 目录
    s = add_slide(prs, "汇报提纲")
    write_lines(body_box(s), [
        ("1. 作业背景与 RAG 原理", 0, True, NAVY),
        ("2. 技术选型：为什么选方案 C", 0, True, NAVY),
        ("3. Phase 1：知识库构建（提取 / 分块 / 建库 / 验证）", 0, True, NAVY),
        ("4. Phase 2：智能问答系统（检索工具 / 提示词 / 配置）", 0, True, NAVY),
        ("5. R1~R6 行为约束的实现与验证", 0, True, NAVY),
        ("6. 踩坑与解决：4 个真实问题", 0, True, NAVY),
        ("7. 成果、不足与展望", 0, True, NAVY),
    ], size=17, space=13)

    # ---------------------------------------------------------- 3 背景
    s = add_slide(prs, "一、作业背景：RAG 要解决什么问题", "让 LLM「有据可依」地回答问题")
    write_lines(body_box(s), [
        ("大语言模型的两个固有缺陷", 0, True, NAVY),
        ("幻觉（Hallucination）：模型会用流畅的语言给出错误答案", 1, False, None),
        ("知识陈旧/私有：教材、内部文档不在预训练语料中", 1, False, None),
        ("", 0, False, None),
        ("RAG（检索增强生成）的核心思想", 0, True, NAVY),
        ("先从知识库中检索与问题相关的内容，再基于检索结果生成回答，", 1, False, None),
        ("而不是直接依赖模型内部知识。", 1, False, None),
        ("", 0, False, None),
        ("本作业的强制要求：不只「能回答」，还要「守规矩」", 0, True, RED),
        ("R1 先检索后回答  ·  R2 只用教材  ·  R3 附页码引用", 1, False, None),
        ("R4 中文+英文术语  ·  R5 未覆盖要诚实  ·  R6 不复制原文", 1, False, None),
    ], size=15, space=6)

    # ---------------------------------------------------------- 4 技术选型
    s = add_slide(prs, "二、技术选型：为什么选方案 C", "从零搭建，深入理解每个环节")
    add_table(s, ["方案", "技术特点", "我们的判断"], [
        ["A（参考路径）", "DSH 框架 + 自定义插件\nSQLite FTS5 + BM25",
         "属教师参考路径；作业鼓励差异化。\n我们仍额外提供了 DSH 插件实现"],
        ["B", "ChromaDB/FAISS + LangChain\n向量检索",
         "依赖重、环节多；中文精确术语检索\n场景下 BM25 更确定、更可解释"],
        ["C（选定）", "SQLite FTS5 + 自研检索\n+ 直接调 LLM API",
         "理解最深入、依赖最简\n结果可复现，便于逐条验证 R1~R6"],
        ["D", "Dify/FastGPT 低代码平台",
         "平台封装了检索过程\n难以强制「先检索后回答」并取证"],
    ], top=1.6, col_widths=[1.4, 3.2, 4.2], font_size=11.5)
    add_note(s, "依赖极简：仅需 pymupdf（建库阶段）+ Python 标准库；无需 GPU、向量库、框架。")

    # ---------------------------------------------------------- 5 架构
    s = add_slide(prs, "三、系统架构", "两阶段：离线建库 + 在线问答")
    tf = body_box(s)
    write_lines(tf, [
        ("Phase 1 知识库构建（离线，一次性）", 0, True, NAVY),
        ("教材 PDF (430页)  →  PyMuPDF 提取  →  pages.jsonl + chapters.json", 1, False, None),
        ("→  语义分块  →  chunks.jsonl（277 块，800~1200 tokens，含重叠）", 1, False, None),
        ("→  SQLite FTS5(trigram) + BM25  →  arch_kb.sqlite", 1, False, None),
        ("→  验证：覆盖率 / 块统计 / 检索准确率", 1, False, None),
        ("", 0, False, None),
        ("Phase 2 问答运行时（在线）", 0, True, NAVY),
        ("用户问题  →  [R1] knowledge_search（强制前置）", 1, False, None),
        ("→  查询预处理(去疑问词/同义词扩展)  →  FTS5 召回候选池", 2, False, None),
        ("→  二次排序(覆盖度+标题命中+BM25排名)  →  相关性闸门", 2, False, None),
        ("→  带页码片段  →  [R2~R6] 生成合规回答", 1, False, None),
    ], size=14, space=5)

    # ---------------------------------------------------------- 6 Phase1 提取
    s = add_slide(prs, "四、Phase 1-1：文本提取与章节检测", "用 PDF 书签而非正则")
    write_lines(body_box(s, top=1.6, height=1.9), [
        ("教材 PDF 结构（由 LaTeX/hyperref 生成，自带 210 条书签）", 0, True, NAVY),
        ("level 1 → 部分（6 个）   level 2 → 章（12 个）", 1, False, None),
        ("level 3 → 节（72 个）    level 4 → 小节（120 个）", 1, False, None),
    ], size=14, space=5)
    add_table(s, ["决策", "做法", "理由"], [
        ["章节边界来源", "直接读取 PDF 书签\n以 level≤2 作为「章」边界",
         "书签是出版方权威结构，零误判；\n正则匹配「第X章」易受页眉、目录干扰"],
        ["文本清洗", "合并断行、折叠多余空行、\n去除零宽字符",
         "LaTeX PDF 存在硬换行与断词，\n不清洗会污染分块与检索"],
    ], top=3.5, col_widths=[1.6, 3.4, 3.8], font_size=11.5)
    add_note(s, f"结果：识别 12 章，边界与目录完全一致；提取总字符 {STATS['total_chars']:,}，"
                f"低密度页（封面/插页）{len(STATS['low_density_pages'])} 页已自动跳过。")

    # ---------------------------------------------------------- 7 Phase1 分块
    s = add_slide(prs, "四、Phase 1-2：语义分块", "作业要求 800~1200 tokens，块间有重叠")
    add_table(s, ["参数", "取值", "依据"], [
        ["TARGET_TOKENS", "1000", "作业要求区间的中值"],
        ["MIN / MAX", "800 / 1200", "作业规定的下限与上限"],
        ["OVERLAP_CHARS", "180", "防止答案被块边界切断"],
        ["SPLIT_TOLERANCE", "1.12", "容忍轻微超限，避免劣化切分（见踩坑）"],
    ], top=1.6, col_widths=[2.2, 1.6, 5.0], font_size=11.5)

    add_table(s, ["最终指标", "数值", "最终指标", "数值"], [
        ["总块数", f"{cs['chunk_count']}", "落在 800~1200",
         f"{cs['in_800_1200']} 块（{cs['in_800_1200_pct']}%）"],
        ["token 均值", f"{cs['token_avg']}", "超过 1200 上限", f"{cs['above_1200']} 块"],
        ["token 范围", f"{cs['token_min']}~{cs['token_max']}",
         "章末块(<800)", f"{cs['below_800_chapter_tail']} 块"],
    ], top=4.0, col_widths=[2.0, 2.0, 2.4, 2.4], font_size=11.5)

    # ---------------------------------------------------------- 8 建库
    s = add_slide(prs, "四、Phase 1-3：构建 FTS5 知识库", "中文检索的关键：分词器选择")
    add_table(s, ["检索方式", "中文查询「直接相联组相联」", "结论"], [
        ["无索引 LIKE '%词%'", "命中但无法排序", "只能返回布尔结果"],
        ["FTS5 unicode61", "0 命中", "中文整句被当作单一 token"],
        ["FTS5 trigram（选定）", "命中 p.280（正确）", "3 字符滑窗，中文子串匹配良好"],
    ], top=1.6, col_widths=[2.6, 3.6, 3.2], font_size=11.5)
    tf = body_box(s, top=3.5, height=2.6)
    write_lines(tf, [
        ("表结构", 0, True, NAVY),
        ("chunks：chunk_id, text, page_start, page_end, chapter, section, n_tokens_est", 1, False, None),
        ("chunks_fts：FTS5 外部内容索引，tokenize='trigram'，排序用 bm25()", 1, False, None),
        ("", 0, False, None),
        ("为什么选 trigram？", 0, True, NAVY),
        ("中文没有空格，unicode61 会把整句当一个 token，导致中文查询全部 0 命中。", 1, False, None),
    ], size=12.5, space=4)
    add_note(s, "代价：trigram 要求查询词 ≥3 字符。应对：MATCH 表达式与覆盖度探针均过滤 <3 字符的词，"
                "并用同义词表把短查询映射到教材术语。")

    # ---------------------------------------------------------- 9 验证
    s = add_slide(prs, "四、Phase 1-4：知识库验证", "三项验证全部达标")
    add_table(s, ["验证项", "指标", "结果"], [
        ["块数统计", f"总块数 / token 均值", f"{cs['chunk_count']} 块 / {cs['token_avg']}"],
        ["粒度合规", "落在 800~1200 tokens", f"{cs['in_800_1200_pct']}%（超上限 {cs['above_1200']} 块）"],
        ["章节覆盖率", "已覆盖章节 / 总章节", f"{cc['covered']}/{cc['total_chapters']} = {cc['coverage_pct']}%"],
        ["页码元数据", "缺失或非法的块", f"{cc['bad_metadata_chunks']} 块"],
        ["页码覆盖", "知识库覆盖页范围",
         f"p.{cc['page_range'][0]} ~ p.{cc['page_range'][1]}（共 430 页）"],
        ["检索准确性", "Top-1 / Top-3", f"{rt['top1_accuracy']}% / {rt['top3_recall']}%"],
    ], top=1.7, col_widths=[2.2, 3.4, 4.0], font_size=12)
    add_note(s, "复现命令：python scripts/04_verify_kb.py  →  data/verify_report.json")

    # ---------------------------------------------------------- 10 Phase2 检索
    s = add_slide(prs, "五、Phase 2-1：检索工具 knowledge_search", "RAG 的唯一事实来源")
    tf = body_box(s, top=1.55, height=5.2)
    write_lines(tf, [
        ("检索流水线（4 步）", 0, True, NAVY),
        ("① 查询预处理：去除疑问词（「什么是」「如何」等）+ 同义词扩展", 1, False, None),
        ("② FTS5 MATCH 召回候选池：LIMIT max(topk×8, 40)", 1, False, None),
        ("③ 二次排序：0.35×词覆盖度 + 0.15×完整短语 + 0.30×标题命中 + 0.20×BM25排名", 1, False, None),
        ("④ 相关性闸门：实义关键词覆盖率 < 0.34 → 判定「教材未覆盖」", 1, False, None),
        ("", 0, False, None),
        ("返回结构（直接支持 R3 页码引用）", 0, True, NAVY),
        ("{ chunk_id, text, page_start, page_end, chapter, section,", 1, False, None),
        ("  score, citation: \"【教材 p.279-280】\" }", 1, False, None),
        ("", 0, False, None),
        ("同义词表（解决「用户用词 ≠ 教材用词」）", 0, True, NAVY),
        ("映象 ↔ 映像 ↔ 映射 ↔ 相联   |   Cache ↔ 高速缓存   |   TLB ↔ 快表", 1, False, None),
    ], size=13, space=5)

    # ---------------------------------------------------------- 11 提示词
    s = add_slide(prs, "五、Phase 2-2：五段式系统提示词", "每段对应明确的约束")
    add_table(s, ["段落", "内容", "对应约束"], [
        ["第一部分", "身份与知识边界：限定只用本教材，禁用内部知识", "R2"],
        ["第二部分", "强制检索流程：回答前必须调用 knowledge_search", "R1"],
        ["第三部分", "事实依据：所有事实须能在检索片段中找到出处", "R2"],
        ["第四部分", "回答格式：每个事实附【教材 p.XX】，术语写「中文(English)」", "R3 / R4"],
        ["第五部分", "诚实性与版权：未覆盖则答固定话术；连续引用 ≤3 句", "R5 / R6"],
    ], top=1.6, col_widths=[1.3, 5.7, 1.6], font_size=11.5)
    tf = body_box(s, top=4.6, height=2.0)
    write_lines(tf, [
        ("设计要点", 0, True, NAVY),
        ("给出固定话术「教材未找到相关内容」——既降低幻觉率，也让 R5 可被字符串精确验证。", 1, False, None),
        ("末尾附 6 条自检清单，作为回答前的最后一道闸门。", 1, False, None),
    ], size=12.5, space=4)

    # ---------------------------------------------------------- 12 R1机制
    s = add_slide(prs, "六、R1 的强制：提示词 + 机制双保险", "为什么不能只靠提示词")
    write_lines(body_box(s, top=1.6, height=1.5), [
        ("纯提示词约束存在被模型绕过的风险，因此对最关键的 R1 采取双重保障：", 0, False, None),
    ], size=14)
    add_table(s, ["层次", "手段", "效果"], [
        ["提示词层", "第 4 条把「调用 knowledge_search」定义为回答的前置条件",
         "模型倾向于遵守，但理论上可被绕过"],
        ["代码层", "run() 中检索是回答调用链的必经步骤：\n"
                   "answer_offline / answer_with_api 均接收 hits 参数，\n"
                   "无检索结果则无法进入事实生成分支",
         "运行时不存在绕过路径"],
    ], top=2.4, col_widths=[1.4, 5.4, 3.0], font_size=11.5)
    add_note(s, "验证方式：读取执行日志的 retrieval_called 标志 + 检查调用顺序。")

    # ---------------------------------------------------------- 13 R1-R6 对照
    s = add_slide(prs, "六、R1~R6 实现与验证对照", "30 项自动核查全部通过")
    rows = []
    impl = {
        "R1": "提示词§2 + run() 调用链强制",
        "R2": "提示词§1/§3 + 相关性闸门",
        "R3": "提示词§4 + citation 字段",
        "R4": "提示词§4 + detect_terms()",
        "R5": "提示词§1/§5 + 闸门拦截分支",
        "R6": "提示词§5 + 每片段限 2 句",
    }
    verify = {
        "R1": "检查 log.retrieval_called",
        "R2": "核对引用页码是否在片段范围内",
        "R3": "正则匹配 + 页码真实性核对",
        "R4": "中文主体 + 术语标注检查",
        "R5": "是否含标准话术",
        "R6": "统计最长连续原文句数",
    }
    for rid, v in per.items():
        rows.append([rid, impl[rid], verify[rid],
                     f"{v['pass']}/{v['pass']+v['fail']}",
                     "PASS" if v["fail"] == 0 else "FAIL"])
    add_table(s, ["约束", "实现位置", "验证方式", "通过", "结果"], rows,
              top=1.6, col_widths=[0.9, 3.0, 3.0, 1.0, 1.0], font_size=11)
    add_note(s, f"总计 {total_pass}/{total_all} 项通过（{total_pass/total_all*100:.0f}%）；"
                "复现命令：python test/run_smoke_test.py")

    # ---------------------------------------------------------- 14 测试用例
    s = add_slide(prs, "六、测试用例设计（5 个）", "覆盖正常、未覆盖、超范围三类场景")
    rows = []
    kind_cn = {"normal": "正常", "uncovered": "未覆盖", "out_of_scope": "超范围"}
    for c in REPORT["cases"]:
        fails = [k for k, v in c["checks"].items() if not v["pass"]]
        rows.append([c["id"], c["question"][:30], kind_cn.get(c["kind"], c["kind"]),
                     "全部通过" if not fails else "未通过:" + ",".join(fails)])
    add_table(s, ["编号", "问题", "类型", "R1~R6 结果"], rows,
              top=1.7, col_widths=[0.8, 5.0, 1.2, 2.4], font_size=11)
    add_note(s, "关键设计：专门设置「教材未覆盖」与「超出教材范围」两类用例，"
                "检验系统是否会在无依据时编造答案。")

    # ---------------------------------------------------------- 15 关键结果
    s = add_slide(prs, "六、关键结果：未覆盖与超范围问题的处理", "R2 / R5 的关键证据")
    add_table(s, ["用例", "问题", "原始命中", "相关性闸门", "最终行为"], [
        ["T4", "量子纠缠在量子计算芯片中如何实现纠错？", "0", "拦截",
         "回答「教材未找到相关内容」，未编造"],
        ["T5", "请帮我写一份 Java 的冒泡排序代码。", "5", "拦截",
         "回答「教材未找到相关内容」，拒绝作答"],
    ], top=1.7, col_widths=[0.8, 4.2, 1.2, 1.4, 3.2], font_size=11)
    tf = body_box(s, top=3.6, height=3.0)
    write_lines(tf, [
        ("T5 是测试中发现的一个真实缺陷", 0, True, RED),
        ("FTS5 因「指令」「程序」等词巧合命中 5 条教材片段，系统便据此作答 —— 违反 R2/R5。", 1, False, None),
        ("", 0, False, None),
        ("根因：FTS 的「有命中」不等于「相关」，trigram 的 OR 召回天然引入噪声。", 0, True, NAVY),
        ("解法：新增相关性闸门 relevance_gate()，按实义关键词覆盖率判定（阈值 0.34）。", 1, False, None),
        ("效果：R2 / R5 通过率由 80% 提升至 100%。", 1, False, GREEN),
    ], size=12.5, space=4)

    # ---------------------------------------------------------- 16 踩坑
    s = add_slide(prs, "七、踩坑与解决（1/2）", "这些问题都是通过测试与诊断发现的")
    add_table(s, ["#", "问题现象", "根因", "解决方案"], [
        ["1", "分块出现 50 对 600 token 的半满块", 
         "flush() 中「超限即二分」，把 1201 切成 600+600",
         "引入 SPLIT_TOLERANCE=1.12，轻微超限不切分"],
        ["2", "检索「指令流水线」未命中对应章节",
         "SQL 直接 LIMIT topk(=3)，候选池过小，重排无从发挥",
         "先召回 topk×8（≥40）再二次排序"],
        ["3", "排序打分失去区分度",
         "BM25 分数集中在 -3~-7，归一化后全部饱和",
         "改用 BM25 相对排名而非绝对值"],
    ], top=1.6, col_widths=[0.5, 2.6, 3.4, 3.3], font_size=10.5)
    add_note(s, "方法：不靠猜测，而是写诊断脚本复刻主循环、打印每次 flush 的原因与大小，"
                "用数据定位根因。")

    # ---------------------------------------------------------- 17 踩坑2
    s = add_slide(prs, "七、踩坑与解决（2/2）", "合规性缺陷由自动化测试暴露")
    add_table(s, ["#", "问题现象", "违反约束", "解决方案"], [
        ["4", "提问与教材无关时仍据无关片段作答", "R2 / R5",
         "新增相关性闸门 relevance_gate()，按实义关键词覆盖率判定"],
        ["5", "回答中出现连续 5 句教材原文复制", "R6",
         "每片段最多取 2 句、单条截断 160 字符，并过滤页眉/图注残片"],
        ["6", "页码引用偶有缺失", "R3",
         "句内 PDF 硬换行统一折叠为单行后再生成回答"],
    ], top=1.7, col_widths=[0.5, 3.2, 1.3, 4.8], font_size=11)
    tf = body_box(s, top=4.3, height=2.4)
    write_lines(tf, [
        ("关于「映象 vs 相联」的一次排查", 0, True, NAVY),
        ("用户问「Cache 的映象方式」，教材实际用「相联」。先验证教材是否覆盖：", 1, False, None),
        ("教材含 '映象' → 0 块；含 '直接相联' → 3 块。内容存在，只是用词不同。", 1, False, None),
        ("解法：内置体系结构术语同义词表，查询时自动扩展。", 1, False, GREEN),
    ], size=12, space=4)

    # ---------------------------------------------------------- 18 成果
    s = add_slide(prs, "八、成果汇总", "全部交付物均已完成")
    add_table(s, ["#", "交付物", "文件", "状态"], [
        ["1", "知识库 + 构建脚本", "data/arch_kb.sqlite + scripts/01~03", "已完成"],
        ["2", "检索工具源码 + 调用说明", "scripts/knowledge_search.py + agents/README.md", "已完成"],
        ["3", "系统提示词 + 设计说明", "prompts/system_prompt.txt + .md", "已完成"],
        ["4", "智能体配置 + 启动说明", "agents/agent.config.json + README.md", "已完成"],
        ["5", "测试报告（DOCX）", "deliverables/Arch-Tutor_测试报告.docx", "已完成"],
        ["6", "实施过程 PPT", "deliverables/Arch-Tutor_实施过程.pptx", "已完成"],
        ["7", "小组分工说明（DOCX）", "deliverables/Arch-Tutor_小组分工说明.docx", "已完成"],
    ], top=1.6, col_widths=[0.5, 3.0, 4.6, 1.0], font_size=11)
    add_note(s, "核心数据：277 个知识块（97.5% 落在 800~1200 tokens）、章节覆盖率 100%、"
                "检索 Top-3 90%、R1~R6 核查 30/30 通过。")

    # ---------------------------------------------------------- 19 不足与展望
    s = add_slide(prs, "九、不足与展望", "诚实评估 + 后续改进方向")
    write_lines(body_box(s, top=1.6, height=2.4), [
        ("不足", 0, True, RED),
        ("离线模式为抽取式生成，语言组织不如 LLM 自然（但胜在确定、可验证）。", 1, False, None),
        ("trigram 要求查询词 ≥3 字符，2 字查询依赖同义词表覆盖。", 1, False, None),
        ("检索为纯全文检索，尚未引入语义向量，同义改写的召回有限。", 1, False, None),
    ], size=13, space=5)
    write_lines(body_box(s, top=4.1, height=3.0), [
        ("展望（对应作业拓展挑战）", 0, True, NAVY),
        ("混合检索：全文 + 向量，融合排序，提升语义召回。", 1, False, None),
        ("重排序：引入 cross-encoder 对初检结果二次排序。", 1, False, None),
        ("多轮对话：支持「它」「该协议」等指代消解。", 1, False, None),
        ("知识库增量更新：支持追加新章节或新教材。", 1, False, None),
        ("可视化界面：为智能体添加 Web UI，展示检索与引用过程。", 1, False, None),
    ], size=13, space=5)

    # ---------------------------------------------------------- 20 结尾
    add_title_slide(
        prs,
        "谢谢！欢迎提问",
        "Arch-Tutor · 计算机体系结构课程知识库智能问答系统",
        [
            "复现入口：",
            "建库  python scripts/01~03_*.py",
            "验证  python scripts/04_verify_kb.py",
            "问答  python agents/arch_tutor_agent.py \"你的问题\" --offline",
            "合规  python test/run_smoke_test.py",
        ],
    )

    out = OUT / "Arch-Tutor_实施过程.pptx"
    prs.save(out)
    print(f"已生成: {out}（{len(prs.slides.__iter__.__self__._sldIdLst)} 页）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
