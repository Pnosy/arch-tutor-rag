# -*- coding: utf-8 -*-
"""
Phase 1 / Step 2 —— 章节内语义分块

目标粒度：每块 800~1200 tokens（中文按「等效 token」估算），块间保留重叠。
输出：data/chunks.jsonl，每条记录包含：
    chunk_id, text, page_start, page_end, chapter, chapter_id, part,
    section(最接近的小节标题), n_chars, n_tokens_est, ordinal

分块策略（结构优先 + 长度约束）：
  1. 以「章」为边界，章内按段落聚合；
  2. 每累计到目标 token 数就落一块；优先在小节标题(section)边界处断开，
     使一个块尽量不跨小节，语义更内聚；
  3. 块尾与下一块块首保留 overlap 个字符的重叠，避免答案被切断；
  4. 记录块覆盖的物理页码区间 page_start~page_end。

token 估算：中文 1 字 ≈ 1 token；连续 ASCII(英文单词/数字) 按 4 字符 ≈ 1 token。
不引入外部 tokenizer 依赖，保证脚本可独立运行；同时记录估算口径。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

# ---- 目标粒度参数（作业要求 800~1200 tokens）----
TARGET_TOKENS = 1000      # 目标块大小
MIN_TOKENS = 800          # 低于此值视为过小，与相邻块合并（贴近作业 800~1200 下限）
MAX_TOKENS = 1200         # 超过则强制切分（作业上限）
OVERLAP_CHARS = 180       # 块间重叠字符数（约 120~150 token）
SPLIT_TOLERANCE = 1.12    # 超过 MAX*该系数才真正切分，容忍轻微超限

CJK = r"\u4e00-\u9fff\u3000-\u303f\uff00-\uffef"


def est_tokens(s: str) -> int:
    """估算 token 数：中文 1 字=1 token，英文/数字 4 字符=1 token。"""
    if not s:
        return 0
    cjk = len(re.findall(f"[{CJK}]", s))
    other = len(s) - cjk
    return int(cjk + other / 4)


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def split_paragraphs(text: str) -> list[str]:
    """按空行切段；PDF 常无空行，则退化为按句号切分再聚合。"""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(parts) > 1:
        return parts
    # 无空行：按中文句末标点切句
    sents = re.split(r"(?<=[。！？；])", text)
    return [s.strip() for s in sents if s.strip()]


def split_balanced(text: str, max_tokens: int, min_tokens: int) -> list[str]:
    """把超长文本按句切分为若干大小均衡的片段。

    仅在「确实需要」时切分：
      - 总长超过 max_tokens * SPLIT_TOLERANCE 才动手，避免把一个刚好略超上限的
        块硬切成两个半满块（例如 1201 -> 600+600，反而破坏语义完整性）；
      - 片段数按 max_tokens 向上取整，使每片尽量接近但不超过上限；
      - 若切分后有片段小于 min_tokens，则说明切分不划算，放弃切分。
    """
    total = est_tokens(text)
    if total <= max_tokens * SPLIT_TOLERANCE:
        return [text]
    n = max(2, (total + max_tokens - 1) // max_tokens)
    target = total / n
    sents = [s for s in re.split(r"(?<=[。！？；\n])", text) if s]
    if len(sents) < n:
        return [text]  # 句太少，无法均衡切分
    out: list[str] = []
    cur = ""
    for s in sents:
        if cur and est_tokens(cur + s) > target and len(out) < n - 1:
            out.append(cur)
            cur = s
        else:
            cur += s
    if cur:
        out.append(cur)
    # 切分不划算（出现过小片段）则回退为不切分
    if any(est_tokens(p) < min_tokens for p in out):
        return [text]
    return out or [text]


def split_oversized(para: str, max_tokens: int) -> list[str]:
    """把超长段落（如整页表格/长列表）按句切分到逼近上限的若干子段。

    保证不会因单个巨型段落而产生远超 1200 token 的块。
    """
    if est_tokens(para) <= max_tokens:
        return [para]
    sents = re.split(r"(?<=[。！？；])", para)
    out: list[str] = []
    cur = ""
    for s in sents:
        if not s:
            continue
        if cur and est_tokens(cur + s) > max_tokens:
            out.append(cur)
            cur = s
        else:
            cur += s
    if cur:
        out.append(cur)
    return out or [para]


def build_section_index(chapter: dict) -> list[tuple[int, str]]:
    """返回 [(page, section_title), ...]，用于给块打小节标签。"""
    return [(s["page"], s["title"]) for s in chapter.get("sections", [])]


def section_of(sections: list[tuple[int, str]], page: int) -> str:
    cur = ""
    for p, title in sections:
        if p <= page:
            cur = title
        else:
            break
    return cur


def chunk_chapter(
    chapter: dict, pages: dict[int, str], start_id: int
) -> tuple[list[dict], int]:
    """对单个章节做分块，返回 (chunks, next_id)。"""
    ps, pe = chapter["page_start"], chapter["page_end"]
    sections = build_section_index(chapter)
    sec_pages = {p for p, _ in sections}

    # 收集章内 (page, paragraph) 序列
    units: list[tuple[int, str]] = []
    for p in range(ps, pe + 1):
        txt = pages.get(p, "")
        if not txt or len(txt) < 30:
            continue  # 跳过插页/纯图页
        for para in split_paragraphs(txt):
            if para:
                units.append((p, para))

    chunks: list[dict] = []
    buf: list[tuple[int, str]] = []
    buf_tok = 0
    cid = start_id

    def flush():
        nonlocal buf, buf_tok, cid
        if not buf:
            return
        text = "\n".join(t for _, t in buf).strip()
        if not text:
            buf, buf_tok = [], 0
            return
        # 若整块超出上限（章末残余等），在句边界处再切分为多个均衡子块
        if est_tokens(text) > MAX_TOKENS and len(buf) > 1:
            pieces = split_balanced(text, MAX_TOKENS, MIN_TOKENS)
            if len(pieces) > 1:
                for piece in pieces:
                    emit(text=piece, pages=list(buf))
                buf, buf_tok = [], 0
                return
        emit(text=text, pages=list(buf))
        p_last = buf[-1][0]
        tail = text[-OVERLAP_CHARS:] if len(text) > OVERLAP_CHARS else text
        buf = [(p_last, tail)] if tail else []
        buf_tok = est_tokens(tail)

    def emit(text: str, pages: list[tuple[int, str]]):
        """写入一个块。"""
        nonlocal cid
        p_first, p_last = pages[0][0], pages[-1][0]
        chunks.append(
            {
                "chunk_id": cid,
                "text": text,
                "page_start": p_first,
                "page_end": p_last,
                "chapter": chapter["title"],
                "chapter_id": chapter["chapter_id"],
                "part": chapter["part"],
                "section": section_of(sections, p_first),
                "n_chars": len(text),
                "n_tokens_est": est_tokens(text),
            }
        )
        cid += 1

    for page, para in units:
        ptok = est_tokens(para)
        # 断块判定（在 append 之前）。buf_tok 已含上一块带入的重叠量，
        # 因此这里的数值即为「本块最终大小」的准确预估。
        #
        # 硬约束：加入本段会超过 MAX_TOKENS 且缓冲已达到下限 -> 必须断开。
        # 说明：soft 分支断开时缓冲里含上一块带入的重叠尾部，而 flush 后
        # 该尾部又会去掉，因此这里预留 OVERLAP 的安全余量，确保最终块 <= MAX。
        safety = est_tokens("x" * OVERLAP_CHARS) // 2
        overflow = (buf_tok + ptok) > (MAX_TOKENS - safety) and buf_tok >= MIN_TOKENS
        # 软偏好：遇到小节起点，且缓冲已接近目标大小 -> 在此断开使块语义内聚。
        # 阈值用 TARGET_TOKENS*0.85 而非 MIN_TOKENS，避免过早断块产生小碎片。
        soft_section = page in sec_pages and buf_tok >= TARGET_TOKENS * 0.85
        if overflow or soft_section:
            flush()
        buf.append((page, para))
        buf_tok += ptok

    # 收尾：章末残余。优先并入上一块（若合并后不超过上限），
    # 否则单独成块 —— 章末（小结/习题）是自然的语义边界，允许略小于下限。
    if buf:
        tail_text = "\n".join(t for _, t in buf).strip()
        # 去掉与上一块重复的重叠部分
        if chunks:
            overlap = chunks[-1]["text"][-OVERLAP_CHARS:]
            if tail_text.startswith(overlap):
                tail_text = tail_text[len(overlap):].lstrip()
        rem_tok = est_tokens(tail_text)
        combined = (chunks[-1]["n_tokens_est"] + rem_tok) if chunks else 0
        if tail_text and chunks and combined <= MAX_TOKENS:
            prev = chunks[-1]
            prev["text"] = (prev["text"] + "\n" + tail_text).strip()
            prev["page_end"] = max(prev["page_end"], buf[-1][0])
            prev["n_chars"] = len(prev["text"])
            prev["n_tokens_est"] = est_tokens(prev["text"])
        elif tail_text:
            emit(text=tail_text, pages=list(buf))

    return chunks, cid


def main() -> int:
    pages_recs = load_jsonl(DATA / "pages.jsonl")
    pages = {r["page"]: r["text"] for r in pages_recs}
    chapters = json.loads((DATA / "chapters.json").read_text(encoding="utf-8"))

    print(f"[1/3] 载入 {len(pages)} 页, {len(chapters)} 章")
    all_chunks: list[dict] = []
    cid = 1
    for ch in chapters:
        chunks, cid = chunk_chapter(ch, pages, cid)
        all_chunks.extend(chunks)
        toks = [c["n_tokens_est"] for c in chunks]
        print(
            f"      ch{ch['chapter_id']:02d} {ch['title'][:22]:<24} "
            f"块数={len(chunks):>3}  token范围=[{min(toks) if toks else 0}, {max(toks) if toks else 0}]"
        )

    out = DATA / "chunks.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    toks = [c["n_tokens_est"] for c in all_chunks]
    in_range = sum(1 for t in toks if 800 <= t <= 1200)
    print(f"\n[2/3] 写出 {out.name}: 共 {len(all_chunks)} 块")
    print(f"      token 均值={sum(toks)/len(toks):.0f} 最小={min(toks)} 最大={max(toks)}")
    print(f"      落在 800~1200 目标区间的块: {in_range} ({in_range/len(toks)*100:.1f}%)")

    stats = {
        "chunk_count": len(all_chunks),
        "token_min": min(toks),
        "token_max": max(toks),
        "token_avg": round(sum(toks) / len(toks), 1),
        "in_target_range": in_range,
        "in_target_range_pct": round(in_range / len(toks) * 100, 1),
        "total_chars": sum(c["n_chars"] for c in all_chunks),
        "chapters_covered": len({c["chapter_id"] for c in all_chunks}),
        "params": {
            "TARGET_TOKENS": TARGET_TOKENS,
            "MIN_TOKENS": MIN_TOKENS,
            "MAX_TOKENS": MAX_TOKENS,
            "OVERLAP_CHARS": OVERLAP_CHARS,
        },
    }
    (DATA / "chunk_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("[3/3] 完成 -> data/chunk_stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
