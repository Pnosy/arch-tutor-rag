# -*- coding: utf-8 -*-
"""
Phase 1 / Step 1 —— PDF 逐页文本提取 + 章节边界检测

教材：《计算机体系结构基础》(胡伟武 等, 2024-09-20)
输入：PDF 文件路径
输出：
  - data/pages.jsonl    每页一条记录 {page, text, chars}
  - data/toc.json       PDF 书签目录（章节边界来源）
  - data/chapters.json  规范化后的章节树 + 每章起始/结束页

设计说明见 docs/DESIGN.md。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pymupdf  # PyMuPDF >= 1.24

# ---------------------------------------------------------------- 路径配置
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

# 教材 PDF 需由使用者自行提供（受版权保护，不随仓库分发）。
# 解析顺序：命令行参数 > 环境变量 ARCH_TUTOR_PDF > 以下约定位置。
PDF_CANDIDATES = [
    ROOT / "计算机体系结构基础.pdf",       # 放在项目根目录
    ROOT / "data" / "计算机体系结构基础.pdf",
    Path.cwd() / "计算机体系结构基础.pdf",
]

ENV_PDF = "ARCH_TUTOR_PDF"


def resolve_pdf(cli_arg: str | None = None) -> Path | None:
    """按优先级定位教材 PDF，找不到返回 None。"""
    if cli_arg:
        p = Path(cli_arg)
        return p if p.exists() else None
    env = os.environ.get(ENV_PDF)
    if env:
        p = Path(env)
        if p.exists():
            return p
    for c in PDF_CANDIDATES:
        if c.exists():
            return c
    return None


# ---------------------------------------------------------------- 文本清洗
def clean_text(raw: str) -> str:
    """清洗 PDF 提取出的原始文本。

    处理 LaTeX(xdvipdfmx) 生成 PDF 的常见噪声：
      1. 断字连字符：行尾 "-\n" 拼接成词
      2. 软换行：中文行内换行直接拼接（中文无空格需求），英文补空格
      3. 页眉页脚残留、多余空白行折叠
    """
    if not raw:
        return ""

    # 统一换行符
    t = raw.replace("\r\n", "\n").replace("\r", "\n")
    # 去除零宽字符与 BOM
    t = t.replace("\u200b", "").replace("\ufeff", "")

    lines = [ln.rstrip() for ln in t.split("\n")]
    out: list[str] = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            out.append("")  # 保留段落空行信号
            continue
        out.append(stripped)

    # 合并断行：上一行以 '-' 结尾且下一行以小写字母开头 -> 英文断词
    merged: list[str] = []
    i = 0
    while i < len(out):
        cur = out[i]
        nxt = out[i + 1] if i + 1 < len(out) else None
        if cur.endswith("-") and nxt and re.match(r"^[a-z]", nxt):
            out[i + 1] = cur[:-1] + nxt
            i += 1
            continue
        merged.append(cur)
        i += 1

    # 行拼接：非空行之间，若前一行末尾是中文/字母且后一行开头也是同类，且前一行未以句末标点结束
    #   -> 视为同一段落被 PDF 硬换行切断
    joiner: list[str] = []
    for ln in merged:
        if not ln:
            joiner.append("")
            continue
        if joiner:
            prev = joiner[-1]
            if prev and not prev.endswith(("。", "！", "？", "；", "：", ".", "!", "?", ";", ":", "）", ")", "】")):
                # 中文直接连；英文/数字之间补空格
                if re.search(r"[\u4e00-\u9fff]$", prev) or re.match(r"^[\u4e00-\u9fff]", ln):
                    joiner[-1] = prev + ln
                else:
                    joiner[-1] = prev + " " + ln
                continue
        joiner.append(ln)

    # 折叠 3 个以上连续空行
    text = "\n".join(joiner)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------- 章节检测
def load_toc(doc: "pymupdf.Document") -> list[list]:
    """读取 PDF 书签目录，返回 [[level, title, page1based], ...]。"""
    return [list(item) for item in doc.get_toc(simple=True)]


def build_chapters(toc: list[list], page_count: int) -> list[dict]:
    """由书签目录构建「章(chapter)」级边界。

    本教材结构：level1=部分(6) / level2=章(12) / level3=节 / level4=小节
    我们以 level<=2 作为「章」边界；同时保留 part 归属。
    每章 page_start = 该书签页(1-based)，page_end = 下一章起始页 - 1。
    """
    parts = [t for t in toc if t[0] == 1]
    chapters = [t for t in toc if t[0] == 2]

    def part_of(page: int) -> str:
        cur = ""
        for lv, title, p in parts:
            if p <= page:
                cur = title
            else:
                break
        return cur

    result: list[dict] = []
    for idx, (lv, title, start) in enumerate(chapters):
        if idx + 1 < len(chapters):
            end = chapters[idx + 1][2] - 1
        else:
            end = page_count
        # 章内节标题（level 3），用于章节覆盖率与小节定位
        sections = [
            {"title": t[1], "page": t[2]}
            for t in toc
            if t[0] == 3 and start <= t[2] <= end
        ]
        result.append(
            {
                "chapter_id": idx + 1,
                "title": title,
                "part": part_of(start),
                "page_start": start,
                "page_end": end,
                "sections": sections,
            }
        )
    return result


# ---------------------------------------------------------------- 主流程
def main() -> int:
    pdf_path = resolve_pdf(sys.argv[1] if len(sys.argv) > 1 else None)
    if pdf_path is None:
        print(
            "[错误] 未找到教材 PDF。\n\n"
            "本仓库不包含教材原文（版权原因），请自行准备 PDF 后按以下任一方式指定：\n"
            "  1) 命令行参数： python scripts/01_extract_pages.py \"路径/教材.pdf\"\n"
            f"  2) 环境变量：   $env:{ENV_PDF} = \"路径/教材.pdf\"\n"
            "  3) 放到约定位置：项目根目录下 计算机体系结构基础.pdf\n\n"
            "注意：教材应为合法获取的电子版，仅用于课程学习。",
            file=sys.stderr,
        )
        return 1

    print(f"[1/4] 打开 PDF: {pdf_path}")
    doc = pymupdf.open(pdf_path)
    print(f"      页数={doc.page_count}  标题={doc.metadata.get('title')!r}")

    # ---- 逐页提取
    print("[2/4] 逐页提取文本 ...")
    pages_path = DATA / "pages.jsonl"
    total_chars = 0
    low_density = []
    with pages_path.open("w", encoding="utf-8") as f:
        for i in range(doc.page_count):
            raw = doc[i].get_text("text")
            txt = clean_text(raw)
            total_chars += len(txt)
            if len(txt) < 50:
                low_density.append(i + 1)
            rec = {
                "page": i + 1,  # 1-based PDF 物理页码
                "text": txt,
                "chars": len(txt),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"      写出 {pages_path.name}  总字符={total_chars}")
    print(f"      低密度页(<50字符, 多为封面/插页/纯图页): {len(low_density)} 页")

    # ---- 目录与章节
    print("[3/4] 检测章节边界 ...")
    toc = load_toc(doc)
    chapters = build_chapters(toc, doc.page_count)
    (DATA / "toc.json").write_text(
        json.dumps(toc, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (DATA / "chapters.json").write_text(
        json.dumps(chapters, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"      TOC 条目={len(toc)}  识别章节={len(chapters)}")
    for c in chapters:
        print(
            f"        ch{c['chapter_id']:02d} {c['title'][:24]:<26} "
            f"p.{c['page_start']:>3}-{c['page_end']:>3}  ({c['part']})"
        )

    # ---- 统计报告
    print("[4/4] 生成提取统计 ...")
    stats = {
        # 只记录文件名，不记录绝对路径（避免把本机目录结构写进公开仓库）
        "pdf_name": pdf_path.name,
        "page_count": doc.page_count,
        "total_chars": total_chars,
        "avg_chars_per_page": round(total_chars / doc.page_count, 1),
        "low_density_pages": low_density,
        "toc_entries": len(toc),
        "chapter_count": len(chapters),
        "part_count": len([t for t in toc if t[0] == 1]),
    }
    (DATA / "extract_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("      完成 -> data/extract_stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
