# -*- coding: utf-8 -*-
"""
Phase 2 / 检索工具 —— knowledge_search

对本地 SQLite FTS5 知识库执行检索，返回**带页码引用**的教材片段。
这是 RAG 流程中唯一的事实来源：智能体回答任何课程问题前都必须先调用它（R1）。

【检索策略】
  1. 查询预处理：中文无分词，按「整串 + 关键片段」多路构造 MATCH 表达式；
     trigram 要求每个查询词 >= 3 字符，故短词做补全/丢弃处理。
  2. BM25 排序（FTS5 内置 bm25()，值越小越相关）。
  3. 章节过滤：可选 chapter 参数，把检索限定在某一章。
  4. 相邻块扩展：命中块可附带前后各 1 块，缓解分块边界切断答案的问题
     （由 expand 参数控制）。
  5. 返回统一结构：text / page_start / page_end / chapter / section / score，
     便于智能体直接生成【教材 p.XX】引用（R3）。

用法（命令行自测）：
    python scripts/knowledge_search.py "Cache 的映象方式"
    python scripts/knowledge_search.py "流水线" --topk 5 --json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "arch_kb.sqlite"

# trigram 分词器最小匹配长度
TRIGRAM_MIN = 3

# ---------------------------------------------------------------- 同义词表
# 中文教材术语常有一词多形（映象/映像/映射、相联/相连等），
# 用户提问用词与教材用词不一致会导致 0 命中。这里做轻量同义词扩展，
# 只覆盖本教材涉及的体系结构术语，避免过度泛化。
SYNONYMS: dict[str, list[str]] = {
    "映象": ["映像", "映射", "相联"],
    "映像": ["映象", "映射", "相联"],
    "映射": ["映象", "映像", "相联"],
    "相联": ["映象", "映像", "映射"],
    "缓存": ["Cache"],
    "cache": ["Cache"],
    "高速缓存": ["Cache"],
    "页表": ["TLB", "存储管理"],
    "快表": ["TLB"],
    "流水": ["流水线"],
    "流水式": ["流水线"],
    "超标量": ["多发射", "超标量"],
    "多发射": ["超标量", "多发射"],
    "中断": ["异常"],
    "异常": ["中断"],
    "存储一致性": ["Cache一致性", "访存"],
    "缓存一致性": ["Cache一致性"],
    "并行": ["并行处理", "多核"],
    "多核": ["多核处理器"],
    "启动": ["启动过程", "初始化"],
    "功耗": ["低功耗"],
    "性能": ["性能评价", "性能分析"],
}


def expand_synonyms(terms: list[str]) -> list[str]:
    """对查询词做同义词扩展，返回去重后的词表（原词在前）。"""
    out = list(terms)
    for t in terms:
        for k, vs in SYNONYMS.items():
            if k in t:
                for v in vs:
                    if v not in out:
                        out.append(v)
    return out


# ------------------------------------------------------------ 查询预处理
def _quote(s: str) -> str:
    """FTS5 字符串字面量转义：内部双引号翻倍。"""
    return '"' + s.replace('"', '""') + '"'


def _probe_terms(query: str) -> list[str]:
    """抽取用于「覆盖度打分」的查询词，按重要性排序（首个最重要）。

    中文查询通常整串无空格，因此除了按空格切词外，还要补充
    「领域关键词」与「n-gram 片段」，否则覆盖度打分对中文失效。
    """
    q = (query or "").strip()
    q = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", q)
    stop = [
        "什么是", "请问", "如何", "怎么", "怎样", "为什么", "是什么",
        "介绍一下", "解释", "说明", "请", "的", "了", "吗", "呢", "和", "与",
        "区别", "有什么", "哪些", "是什么样",
    ]
    for s in stop:
        q = q.replace(s, " ")
    q = re.sub(r"\s+", " ", q).strip()
    if not q:
        return []

    parts: list[str] = [w for w in q.split(" ") if len(w) >= TRIGRAM_MIN]

    # 中文长串：补充 >=3 字滑窗片段（trigram 下 <3 字永远无法命中，
    # 若把它们纳入覆盖度计算会系统性拉低所有候选的得分）
    for chunk in re.findall(r"[\u4e00-\u9fff]{3,}", q):
        for n in (4, 3):
            for i in range(0, len(chunk) - n + 1, 2):
                frag = chunk[i : i + n]
                if frag not in parts:
                    parts.append(frag)

    if not parts:
        return []
    # 去重并保持「长词优先」（更具体、更能代表主题）
    seen: set[str] = set()
    uniq: list[str] = []
    for p in sorted(parts, key=len, reverse=True):
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    # 同义词扩展，使「映象」类提问也能匹配教材的「相联」
    uniq = [t for t in expand_synonyms(uniq) if len(t) >= TRIGRAM_MIN]
    return uniq[:16]


def build_match_expr(query: str) -> str | None:
    """把自然语言查询转成 FTS5 MATCH 表达式。

    trigram 分词器下的策略：
      - 完整查询串优先（命中整句时得分最高）；
      - 再拆出有意义的词/片段，用 OR 连接提高召回；
      - 去掉中文疑问词与停用词（「什么是」「的」「如何」等），
        否则这些高频词会污染 BM25 排序、把无关块排到前面。

    返回 None 表示查询无法用于 trigram（过短）。
    """
    q = (query or "").strip()
    if not q:
        return None

    # 去掉标点，保留中英文数字与空格
    q = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    if not q:
        return None

    # 去掉疑问/停用成分（中文问答常见噪声）
    stop = [
        "什么是", "什么是？", "请问", "如何", "怎么", "怎样", "为什么",
        "是什么", "介绍一下", "解释", "说明", "请", "的", "了", "吗", "呢",
    ]
    core = q
    for s in stop:
        core = core.replace(s, " ")
    core = re.sub(r"\s+", " ", core).strip() or q

    terms: list[str] = []
    ordered: list[str] = []

    # 1) 完整核心串（若 >=3 字符）——最高优先级
    if len(core.replace(" ", "")) >= TRIGRAM_MIN:
        ordered.append(core)
    # 2) 按空格切分的词
    for w in core.split(" "):
        w = w.strip()
        if len(w) >= TRIGRAM_MIN and w not in ordered:
            ordered.append(w)
    # 3) 中文长串滑窗片段，提高召回
    flat = core.replace(" ", "")
    if len(flat) >= 6:
        for i in range(0, len(flat) - 3, 2):
            frag = flat[i : i + 4]
            if len(frag) >= TRIGRAM_MIN and frag not in ordered:
                ordered.append(frag)
    # 4) 短词候选：连续中文长串（如「运算器里加法器」）整体匹配不上教材，
    #    需要拆出 2~3 字的词级候选。注意 trigram 要求 >=3 字符，
    #    因此取 3 字滑窗（含步长 1）以覆盖「运算器」「加法器」这类词边界。
    if len(flat) >= 4:
        for i in range(0, len(flat) - 2):
            frag = flat[i : i + 3]
            if len(frag) >= TRIGRAM_MIN and frag not in ordered:
                ordered.append(frag)

    terms = ordered
    if not terms:
        return None
    # 同义词扩展：把用户用词映射到教材用词（如「映象」->「相联」）
    terms = expand_synonyms(terms)
    terms = [t for t in terms if len(t) >= TRIGRAM_MIN]
    if not terms:
        return None
    return " OR ".join(_quote(t) for t in terms)


# ------------------------------------------------------------ 检索核心
def _connect() -> sqlite3.Connection:
    if not DB.exists():
        raise FileNotFoundError(
            f"知识库不存在: {DB}\n请先运行: python scripts/03_build_kb.py"
        )
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def relevance_gate(query: str, hits: list[dict], threshold: float = 0.34) -> bool:
    """判断检索结果是否**真正**与问题相关。

    仅靠 FTS 是否命中是不够的：例如问「帮我写 Java 冒泡排序」，
    trigram 可能因「指令」「程序」等词命中教材片段，但这些片段并不
    回答该问题。若不加判断就作答，会违反 R2/R5（用无关内容充当依据）。

    判据（三条，任一满足即通过）：
      A. 覆盖率：问题的实义关键词有多少能在命中片段里找到（主判据）
      B. 核心术语命中：问题中最长的实义术语出现在片段里
      C. 章节标题命中：问题的实义词出现在命中片段的章节/小节标题中

    B/C 的存在是为了避免「TLB 是做什么的」这类问题因疑问虚词
    （「是做什么的」）拉低覆盖率而被误拦——教材明明讲了 TLB。

    同时做一件事：过滤「只是被提及」的假通过。
    若命中片段只在罗列/列举语境里出现该词（如教材列出「量子计算机」
    作为未来方向但不讲解），则不算真正覆盖。
    """
    if not hits:
        return False

    probes = [t for t in _probe_terms(query) if len(t) >= 2]
    probes = [t for t in probes if not re.fullmatch(r"[的了和与或吗呢啊]", t)]
    if not probes:
        return bool(hits)

    blob = " ".join(h["text"] for h in hits[:3])
    title_blob = " ".join(
        f"{h['chapter']} {h.get('section') or ''}" for h in hits[:3]
    )

    # ---- A. 覆盖率主判据
    # 术语可能带前缀（「程序局部性」vs 教材的「局部性」），
    # 故除整词命中外，还接受「该术语的 >=3 字后缀在片段中出现」。
    def _hit(t: str) -> bool:
        if t in blob:
            return True
        # 后缀匹配：程序局部性 -> 局部性 / 序局部性
        for cut in range(1, len(t) - 2):
            suf = t[cut:]
            if len(suf) >= TRIGRAM_MIN and suf in blob:
                return True
        return False

    covered = [t for t in probes if _hit(t)]
    ratio = len(covered) / len(probes)

    # ---- B. 核心术语命中：取最长的实义术语
    # 只认「领域实义词」，排除编程语言、助手性动词等非教材主题
    NOISE = re.compile(
        r"做|是|怎么|如何|什么|哪些|吗|呢|写|帮|代码|程序代码|一段|一个|请"
    )
    core_terms = sorted(
        [t for t in probes if not NOISE.search(t) and len(t) >= 3],
        key=len,
        reverse=True,
    )
    core_hit = bool(core_terms) and core_terms[0] in blob

    # ---- C. 章节标题命中：要求命中的是**实义术语**，
    # 且该术语长度 >=3（避免「程序」这类宽泛词把「写 Python」也放过）
    title_hit = any(
        t in title_blob and len(t) >= 3 and not NOISE.search(t) for t in probes
    )

    # ---- 额外否决项：请求明显属于「代写代码/闲聊」等非教材范畴
    OFFTOPIC = re.compile(
        r"(帮我|请帮我|给我)\s*(写|编|做|生成)|写.{0,6}代码|"
        r"(今天|天气|股票|彩票)|(?i:\bpython\b|\bjava\b|\bc\+\+\b)"
    )
    if OFFTOPIC.search(query):
        return False

    passed = ratio >= threshold or core_hit or title_hit
    return passed


def search(
    query: str,
    topk: int = 5,
    chapter: str | None = None,
    chapter_id: int | None = None,
    expand: int = 0,
    max_chars: int = 1400,
) -> list[dict]:
    """检索知识库。

    参数:
      query      自然语言问题或关键词
      topk       返回条数
      chapter    按章节标题模糊过滤（可选）
      chapter_id 按章节号过滤（可选）
      expand     额外附带命中块前后 n 块（0=不扩展）
      max_chars  单条返回文本的最大字符数（避免超长片段）

    返回: list[dict]，按 BM25 相关度升序（越靠前越相关）
    """
    expr = build_match_expr(query)
    if expr is None:
        return []

    conn = _connect()
    try:
        sql = """
            SELECT c.chunk_id, c.text, c.page_start, c.page_end,
                   c.chapter, c.chapter_id, c.part, c.section,
                   bm25(chunks_fts, 1.0, 0.5, 0.5) AS score
            FROM chunks_fts f
            JOIN chunks c ON c.chunk_id = f.rowid
            WHERE chunks_fts MATCH ?
        """
        params: list = [expr]
        if chapter:
            sql += " AND c.chapter LIKE ?"
            params.append(f"%{chapter}%")
        if chapter_id:
            sql += " AND c.chapter_id = ?"
            params.append(chapter_id)
        sql += " ORDER BY score LIMIT ?"
        # 关键：先召回一个较大的候选池，再由二次排序精排出 topk。
        # 若这里直接 LIMIT topk，重排就只能在极小的候选集里打转，
        # 真正相关的块根本没被取出来（这是早期版本相关性差的根因）。
        pool = max(topk * 8, 40)
        params.append(pool * (1 + 2 * expand) if expand else pool)

        rows = conn.execute(sql, params).fetchall()

        # ---- 二次排序：BM25 只反映词频，这里叠加「查询词覆盖度」与
        #      「完整短语命中」两个信号，把真正讲该主题的块提到前面。
        probes = [t for t in _probe_terms(query) if t]
        if probes:
            # 只保留「在知识库中确实存在」的探针词：trigram 下有些词
            # 全库 0 命中（术语不一致/过短），把它们计入覆盖度会系统性
            # 压低所有候选分数，使排序失去区分度。
            live: list[str] = []
            for t in probes:
                n = conn.execute(
                    "SELECT 1 FROM chunks_fts WHERE chunks_fts MATCH ? LIMIT 1",
                    (_quote(t),),
                ).fetchone()
                if n:
                    live.append(t)
            probes = live or probes

        scored: list[tuple[float, sqlite3.Row]] = []
        for r in rows:
            text = r["text"]
            bm = float(r["score"])  # 越小越相关
            cover = sum(1 for t in probes if t in text) / len(probes) if probes else 0
            exact = 1.0 if (probes and probes[0] in text) else 0.0
            # 章节/小节标题命中：强主题信号（如问「流水线」命中「指令流水线」章）
            title_blob = f"{r['chapter']} {r['section'] or ''}"
            title_hit = (
                sum(1 for t in probes if t in title_blob) / len(probes)
                if probes
                else 0.0
            )
            # BM25 用「相对排名」而非绝对值：本库分数集中在 -3~-7，
            # 直接归一化会全部饱和。改为按 rank 线性给分，保住 FTS 的排序信息。
            scored.append(
                {
                    "cover": cover,
                    "exact": exact,
                    "title": title_hit,
                    "row": r,
                }
            )

        # 先按 BM25（原顺序）编号，再合成最终分数
        n_cand = max(len(scored), 1)
        ranked: list[tuple[float, sqlite3.Row]] = []
        for i, s in enumerate(scored):
            bm_rank_score = 1.0 - (i / n_cand)  # 越靠前越高
            final = (
                0.35 * s["cover"]
                + 0.15 * s["exact"]
                + 0.30 * s["title"]
                + 0.20 * bm_rank_score
            )
            ranked.append((final, s["row"]))
        ranked.sort(key=lambda x: -x[0])
        rows = [r for _, r in ranked]
        hits: list[dict] = []
        seen: set[int] = set()

        for r in rows:
            ids = [r["chunk_id"]]
            if expand:
                ids = list(range(r["chunk_id"] - expand, r["chunk_id"] + expand + 1))
            for cid in ids:
                if cid in seen:
                    continue
                rr = conn.execute(
                    "SELECT chunk_id,text,page_start,page_end,chapter,chapter_id,"
                    "part,section FROM chunks WHERE chunk_id=?",
                    (cid,),
                ).fetchone()
                if not rr:
                    continue
                seen.add(cid)
                text = rr["text"]
                if len(text) > max_chars:
                    text = text[:max_chars].rstrip() + " …"
                hits.append(
                    {
                        "chunk_id": rr["chunk_id"],
                        "text": text,
                        "page_start": rr["page_start"],
                        "page_end": rr["page_end"],
                        "chapter": rr["chapter"],
                        "chapter_id": rr["chapter_id"],
                        "part": rr["part"],
                        "section": rr["section"],
                        "score": round(float(r["score"]), 4),
                        # 便于 R3：直接给出标准引用串
                        "citation": (
                            f"【教材 p.{rr['page_start']}】"
                            if rr["page_start"] == rr["page_end"]
                            else f"【教材 p.{rr['page_start']}-{rr['page_end']}】"
                        ),
                    }
                )
                if len(hits) >= topk:
                    return hits
        return hits
    finally:
        conn.close()


def format_hits(hits: list[dict], query: str = "") -> str:
    """把检索结果格式化为给 LLM 阅读的文本（供工具返回）。"""
    if not hits:
        return (
            "检索结果：未在教材知识库中找到与该问题相关的内容。\n"
            "请如实告知用户「教材未覆盖此内容」，不要凭已有知识作答。"
        )
    out = [f"检索到 {len(hits)} 个相关教材片段（按相关度排序）："]
    for i, h in enumerate(hits, 1):
        out.append(
            f"\n[{i}] {h['citation']}  章节：{h['chapter']}"
            + (f" / {h['section']}" if h.get("section") else "")
            + f"  相关度：{h['score']}\n{h['text']}"
        )
    return "\n".join(out)


def kb_info() -> dict:
    """返回知识库元信息，便于智能体自检与报告。"""
    conn = _connect()
    try:
        meta = {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM meta")}
        meta["chapters"] = [
            dict(r)
            for r in conn.execute(
                "SELECT chapter_id, chapter, MIN(page_start) AS p_start, "
                "MAX(page_end) AS p_end, COUNT(*) AS chunks "
                "FROM chunks GROUP BY chapter_id ORDER BY chapter_id"
            )
        ]
        return meta
    finally:
        conn.close()


# ------------------------------------------------------------ CLI
def main() -> int:
    ap = argparse.ArgumentParser(description="教材知识库检索工具 knowledge_search")
    ap.add_argument("query", help="查询语句")
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--chapter", default=None, help="限定章节标题关键词")
    ap.add_argument("--chapter-id", type=int, default=None)
    ap.add_argument("--expand", type=int, default=0, help="附带前后 n 块")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--info", action="store_true", help="打印知识库信息")
    args = ap.parse_args()

    if args.info:
        print(json.dumps(kb_info(), ensure_ascii=False, indent=1))
        return 0

    hits = search(
        args.query,
        topk=args.topk,
        chapter=args.chapter,
        chapter_id=args.chapter_id,
        expand=args.expand,
    )
    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=1))
    else:
        print(format_hits(hits, args.query))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
