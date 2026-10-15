# -*- coding: utf-8 -*-
"""
Phase 1 验证脚本 —— 知识库质量检验

作业要求「验证知识库：检索测试、块数统计、章节覆盖率检查」。
本脚本输出三项验证结果并落盘 data/verify_report.json：
  1. 块数统计  : 总块数、块大小分布、是否满足 800~1200 token 粒度
  2. 章节覆盖率: 每章块数、页码覆盖、是否存在空章
  3. 检索测试  : 一组有标准答案的问题，检验 Top-K 是否命中预期章节
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = DATA / "arch_kb.sqlite"
sys.path.insert(0, str(ROOT / "scripts"))

sys.stdout.reconfigure(encoding="utf-8")
import importlib.util

spec = importlib.util.spec_from_file_location("ks", ROOT / "scripts/knowledge_search.py")
ks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ks)

# 检索测试用例：(问题, 期望命中的章节名)
CASES = [
    ("Cache 的直接相联、全相联和组相联有什么区别", "指令流水线"),
    ("指令流水线中数据相关会带来什么冲突", "指令流水线"),
    ("TLB 地址翻译的过程是怎样的", "特权指令系统"),
    ("异常和中断分别指什么", "特权指令系统"),
    ("多核处理器之间如何保证存储一致性", "多核处理结构"),
    ("CPI 和 CPU 时间怎么计算", "计算机系统性能评价与性能分析"),
    ("指令系统设计有哪些基本原则", "指令系统"),
    ("计算机启动时处理器核如何初始化", "计算机启动过程分析"),
    ("程序局部性原理是什么", "引言"),
    ("运算器的加法器如何设计", "运算器设计"),
]


def main() -> int:
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    # ---------- 1. 块数统计 ----------
    print("=" * 74)
    print("【验证 1】知识库块数统计")
    print("=" * 74)
    rows = conn.execute(
        "SELECT n_tokens_est, n_chars FROM chunks ORDER BY chunk_id"
    ).fetchall()
    toks = [r["n_tokens_est"] for r in rows]
    n = len(toks)
    in_band = sum(1 for t in toks if 800 <= t <= 1200)
    print(f"  总块数           : {n}")
    print(f"  token 最小/最大  : {min(toks)} / {max(toks)}")
    print(f"  token 均值       : {sum(toks)/n:.1f}")
    print(f"  落在 800~1200    : {in_band} ({in_band/n*100:.1f}%)")
    below = sum(1 for t in toks if t < 800)
    above = sum(1 for t in toks if t > 1200)
    print(f"  <800 (章末块)    : {below}")
    print(f"  >1200 (超出上限) : {above}")
    print(f"  总字符数         : {sum(r['n_chars'] for r in rows)}")

    # ---------- 2. 章节覆盖率 ----------
    print()
    print("=" * 74)
    print("【验证 2】章节覆盖率")
    print("=" * 74)
    chapters = json.loads((DATA / "chapters.json").read_text(encoding="utf-8"))
    ch_rows = conn.execute(
        "SELECT chapter_id, chapter, COUNT(*) c, MIN(page_start) ps, MAX(page_end) pe "
        "FROM chunks GROUP BY chapter_id ORDER BY chapter_id"
    ).fetchall()
    got = {r["chapter_id"]: r for r in ch_rows}
    covered = 0
    print(f"  {'章':<4}{'章节名':<26}{'块数':>5}{'页范围':>14}  状态")
    for ch in chapters:
        cid = ch["chapter_id"]
        r = got.get(cid)
        if r:
            covered += 1
            page_range = f"p.{r['ps']}-{r['pe']}"
            print(
                f"  {cid:<4}{ch['title'][:24]:<26}{r['c']:>5}{page_range:>14}  OK"
            )
        else:
            print(f"  {cid:<4}{ch['title'][:24]:<26}{0:>5}{'-':>14}  MISSING")
    print(f"\n  章节覆盖率: {covered}/{len(chapters)} = {covered/len(chapters)*100:.1f}%")
    print(f"  页码覆盖  : p.{min(r['ps'] for r in ch_rows)} - "
          f"p.{max(r['pe'] for r in ch_rows)} (教材共 430 页)")

    # 页码元数据完整性
    bad = conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE page_start IS NULL OR page_end IS NULL "
        "OR page_start<=0 OR page_end<page_start OR chapter IS NULL OR chapter=''"
    ).fetchone()[0]
    print(f"  页码/章节元数据缺失或非法的块: {bad}  {'OK' if bad==0 else 'FAIL'}")

    # ---------- 3. 检索测试 ----------
    print()
    print("=" * 74)
    print("【验证 3】检索准确性测试（Top-3 是否命中期望章节）")
    print("=" * 74)
    hit_top1 = hit_top3 = 0
    details = []
    for q, expect in CASES:
        hits = ks.search(q, topk=3)
        chs = [h["chapter"] for h in hits]
        t1 = bool(chs) and chs[0] == expect
        t3 = expect in chs
        hit_top1 += t1
        hit_top3 += t3
        mark = "T1" if t1 else ("T3" if t3 else "MISS")
        print(f"  [{mark:>4}] {q[:34]:<36} 期望={expect[:12]:<14} 实际={chs[0][:12] if chs else '无'}")
        details.append({"query": q, "expect": expect, "got": chs, "top1": t1, "top3": t3})

    m = len(CASES)
    print(f"\n  Top-1 准确率: {hit_top1}/{m} = {hit_top1/m*100:.1f}%")
    print(f"  Top-3 命中率: {hit_top3}/{m} = {hit_top3/m*100:.1f}%")

    # ---------- 落盘 ----------
    report = {
        "chunk_stats": {
            "chunk_count": n,
            "token_min": min(toks),
            "token_max": max(toks),
            "token_avg": round(sum(toks) / n, 1),
            "in_800_1200": in_band,
            "in_800_1200_pct": round(in_band / n * 100, 1),
            "below_800_chapter_tail": below,
            "above_1200": above,
            "total_chars": sum(r["n_chars"] for r in rows),
        },
        "chapter_coverage": {
            "total_chapters": len(chapters),
            "covered": covered,
            "coverage_pct": round(covered / len(chapters) * 100, 1),
            "page_range": [min(r["ps"] for r in ch_rows), max(r["pe"] for r in ch_rows)],
            "bad_metadata_chunks": bad,
        },
        "retrieval_test": {
            "cases": m,
            "top1_accuracy": round(hit_top1 / m * 100, 1),
            "top3_recall": round(hit_top3 / m * 100, 1),
            "details": details,
        },
    }
    (DATA / "verify_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"\n验证报告已写入 -> data/verify_report.json")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
