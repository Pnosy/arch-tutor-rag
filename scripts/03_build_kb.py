# -*- coding: utf-8 -*-
"""
Phase 1 / Step 3 —— 构建 SQLite FTS5 全文检索知识库

教材：《计算机体系结构基础》（中文，430 页，12 章）
输入：data/chunks.jsonl
输出：data/arch_kb.sqlite

【为什么用 trigram tokenizer】
  中文没有空格分词，FTS5 默认的 `unicode61` 会把整句中文当作一个 token，
  导致「CACHE」这类查询无法命中。trigram 分词器把文本切成 3 字符滑窗，
  对中文子串匹配效果好，且原生支持 BM25 排序。
  英文/数字同样受益（"pipeline" 会被切成 "pip","ipe","pel"...）。

【表结构】
  chunks        块正文与元数据（page_start / page_end / chapter / section）
  chunks_fts    FTS5 外部内容索引，trigram 分词 + BM25
  检索时用 bm25() 排序，并把 page 信息一并返回，满足 R3 页码引用要求。

运行：python scripts/03_build_kb.py
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CHUNKS = DATA / "chunks.jsonl"
DB = DATA / "arch_kb.sqlite"

DDL = """
PRAGMA journal_mode = WAL;

DROP TABLE IF EXISTS chunks_fts;
DROP TABLE IF EXISTS chunks;

CREATE TABLE chunks (
    chunk_id     INTEGER PRIMARY KEY,
    text         TEXT    NOT NULL,
    page_start   INTEGER NOT NULL,
    page_end     INTEGER NOT NULL,
    chapter      TEXT    NOT NULL,
    chapter_id   INTEGER NOT NULL,
    part         TEXT,
    section      TEXT,
    n_chars      INTEGER,
    n_tokens_est INTEGER
);

CREATE INDEX idx_chunks_chapter ON chunks(chapter_id);
CREATE INDEX idx_chunks_pages   ON chunks(page_start, page_end);

-- FTS5 外部内容表：索引列 = text + chapter + section（章节名可被检索到）
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    text,
    chapter,
    section,
    content='chunks',
    content_rowid='chunk_id',
    tokenize='trigram'
);

CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def main() -> int:
    if not CHUNKS.exists():
        print(f"[ERROR] 未找到 {CHUNKS}，请先运行 02_chunk.py", file=sys.stderr)
        return 1

    chunks = [
        json.loads(l)
        for l in CHUNKS.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    print(f"[1/4] 读取 {len(chunks)} 个块")

    if DB.exists():
        DB.unlink()
    for suffix in ("-wal", "-shm"):
        p = Path(str(DB) + suffix)
        if p.exists():
            p.unlink()

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    print(f"[2/4] 建表 (trigram 分词 + BM25) -> {DB.name}")
    cur.executescript(DDL)

    print("[3/4] 写入块与索引 ...")
    cur.executemany(
        """INSERT INTO chunks
           (chunk_id, text, page_start, page_end, chapter, chapter_id,
            part, section, n_chars, n_tokens_est)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [
            (
                c["chunk_id"], c["text"], c["page_start"], c["page_end"],
                c["chapter"], c["chapter_id"], c.get("part", ""),
                c.get("section", ""), c["n_chars"], c["n_tokens_est"],
            )
            for c in chunks
        ],
    )
    # 外部内容表需显式重建索引
    cur.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")

    # ---- 元信息
    meta = {
        "source_pdf": "计算机体系结构基础.pdf",
        "book_title": "计算机体系结构基础",
        "authors": "胡伟武 汪文祥 苏孟豪 张福新 王焕东 章隆兵 肖俊华 刘苏 陈新科 吴瑞阳 李晓钰 高燕萍",
        "page_count": "430",
        "tokenizer": "trigram",
        "ranking": "bm25",
        "chunk_count": str(len(chunks)),
        "chapter_count": str(len({c["chapter_id"] for c in chunks})),
        "token_estimate_note": "中文1字≈1token，英文/数字4字符≈1token",
    }
    cur.executemany("INSERT INTO meta(key,value) VALUES(?,?)", list(meta.items()))
    conn.commit()

    # ---- 自检
    print("[4/4] 自检 ...")
    cur.execute("SELECT COUNT(*) FROM chunks")
    n_chunks = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM chunks_fts")
    n_fts = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT chapter_id) FROM chunks")
    n_ch = cur.fetchone()[0]
    cur.execute("SELECT MIN(page_start), MAX(page_end) FROM chunks")
    pmin, pmax = cur.fetchone()
    print(f"      chunks={n_chunks}  fts行数={n_fts}  章节={n_ch}  页覆盖={pmin}-{pmax}")

    # 检索冒烟
    for q in ("Cache", "流水线", "TLB"):
        rows = cur.execute(
            """SELECT c.chunk_id, c.chapter, c.page_start, c.page_end,
                      bm25(chunks_fts) AS score
               FROM chunks_fts f JOIN chunks c ON c.chunk_id = f.rowid
               WHERE chunks_fts MATCH ?
               ORDER BY score LIMIT 3""",
            (q,),
        ).fetchall()
        print(f"      查询 {q!r} -> {len(rows)} 命中; 首条: "
              f"{rows[0][1] if rows else '-'} p.{rows[0][2] if rows else '-'}")

    conn.close()
    print(f"\n完成 -> {DB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
