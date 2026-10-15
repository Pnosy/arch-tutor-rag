# -*- coding: utf-8 -*-
"""
构建「可公开分发」的知识库元数据（不含教材正文）

【为什么需要这个脚本】
  完整知识库 data/arch_kb.sqlite 内含教材全文，受版权保护，不适合公开上传。
  但仓库又需要一份可运行的演示数据。本脚本生成一个**只含结构信息、
  不含任何教材原文**的元数据集：

    data/kb_meta.json      章节结构、块数、页码区间、token 统计（无正文）

  以及一个**含极少片段**的演示库（每个 chunk 仅保留前 N 字符用于检索演示，
  默认 N=0 即完全不含正文）。

【用法】
    python scripts/05_export_meta.py                    # 仅导出结构元数据
    python scripts/05_export_meta.py --preview-chars 60 # 每块保留 60 字预览
                                                        # （仅建议用于内部演示）

公开仓库建议使用默认值（不含正文）。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = DATA / "arch_kb.sqlite"
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="导出知识库元数据（不含教材正文）")
    ap.add_argument(
        "--preview-chars",
        type=int,
        default=0,
        help="每个块保留的预览字符数，0 表示完全不含正文（默认，用于公开仓库）",
    )
    args = ap.parse_args()

    if not DB.exists():
        print(f"[错误] 未找到知识库 {DB}，请先运行 scripts/03_build_kb.py",
              file=sys.stderr)
        return 1

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    meta = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM meta")}

    # 章节级结构信息
    chapters = [
        dict(r)
        for r in conn.execute(
            """SELECT chapter_id, chapter, part,
                      MIN(page_start) AS page_start,
                      MAX(page_end)   AS page_end,
                      COUNT(*)        AS chunk_count,
                      SUM(n_tokens_est) AS total_tokens,
                      ROUND(AVG(n_tokens_est),1) AS avg_tokens,
                      MIN(n_tokens_est) AS min_tokens,
                      MAX(n_tokens_est) AS max_tokens
               FROM chunks GROUP BY chapter_id ORDER BY chapter_id"""
        )
    ]

    # 分块级结构信息（不含正文；可选保留极短预览）
    chunks = []
    for r in conn.execute(
        """SELECT chunk_id, page_start, page_end, chapter, chapter_id,
                  part, section, n_chars, n_tokens_est, text
           FROM chunks ORDER BY chunk_id"""
    ):
        item = {
            "chunk_id": r["chunk_id"],
            "page_start": r["page_start"],
            "page_end": r["page_end"],
            "chapter": r["chapter"],
            "chapter_id": r["chapter_id"],
            "part": r["part"],
            "section": r["section"],
            "n_chars": r["n_chars"],
            "n_tokens_est": r["n_tokens_est"],
        }
        if args.preview_chars > 0:
            item["preview"] = r["text"][: args.preview_chars]
        chunks.append(item)

    toks = [c["n_tokens_est"] for c in chunks]
    n = len(toks)
    payload = {
        "_comment": (
            "本文件仅含知识库的结构元数据，不含教材正文。"
            "教材 PDF 受版权保护，不随仓库分发；"
            "请自行准备后运行 scripts/01~03 重建完整知识库。"
        ),
        "book": {
            "title": meta.get("book_title"),
            "authors": meta.get("authors"),
            "page_count": int(meta.get("page_count", 0)),
            "source_pdf": meta.get("source_pdf"),
        },
        "config": {
            "tokenizer": meta.get("tokenizer"),
            "ranking": meta.get("ranking"),
            "token_estimate_note": meta.get("token_estimate_note"),
        },
        "stats": {
            "chunk_count": n,
            "chapter_count": len(chapters),
            "token_min": min(toks),
            "token_max": max(toks),
            "token_avg": round(sum(toks) / n, 1),
            "in_800_1200": sum(1 for t in toks if 800 <= t <= 1200),
            "in_800_1200_pct": round(
                sum(1 for t in toks if 800 <= t <= 1200) / n * 100, 1
            ),
            "total_chars": sum(c["n_chars"] for c in chunks),
        },
        "chapters": chapters,
        "chunks": chunks,
    }

    out = DATA / "kb_meta.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    conn.close()

    size_kb = out.stat().st_size / 1024
    print(f"已导出: {out.name}  ({size_kb:.1f} KB)")
    print(f"  块数={n}  章节={len(chapters)}  "
          f"token={min(toks)}~{max(toks)} (均值 {payload['stats']['token_avg']})")
    print(f"  含正文预览: {'是（' + str(args.preview_chars) + ' 字符/块）' if args.preview_chars else '否（仅结构元数据）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
