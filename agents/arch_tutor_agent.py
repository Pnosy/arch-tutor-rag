# -*- coding: utf-8 -*-
"""
Arch-Tutor —— 教材知识库智能问答系统（参考实现 / 可独立运行）

本脚本是一个**不依赖任何 Agent 框架**的最小 RAG 智能体，用于：
  1. 演示 R1~R6 六条约束如何落地；
  2. 作为冒烟测试的可执行载体（test/ 目录复用其函数）；
  3. 在没有 DSH / LangChain 等框架时也能完整跑通全流程。

【RAG 流程（严格先检索后回答）】
  问题 --> [R1] 调 knowledge_search 检索 --> 得到带页码片段
        --> [R2] 只用片段内容作为事实依据
        --> [R3] 生成【教材 p.XX】引用
        --> [R4] 中文解释 + 保留英文术语
        --> [R5] 未覆盖则答「教材未找到相关内容」
        --> [R6] 转述为主，连续引用不超过 3 句

【两种运行模式】
  --offline  不调用 LLM，用模板 + 检索结果生成「抽取式」回答。
             优点：完全离线、结果确定、便于自动验证 R1~R6。
  --api      调用 OpenAI 兼容的 LLM API（需设置环境变量 ARCH_TUTOR_API_KEY）。
             API Key 只从环境变量读取，绝不写入代码或提交物（作业注意事项第 7 条）。

用法：
    python agents/arch_tutor_agent.py "什么是直接相联和组相联？" --offline
    python agents/arch_tutor_agent.py "讲解指令流水线" --api --model deepseek-chat
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.stdout.reconfigure(encoding="utf-8")

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "knowledge_search", ROOT / "scripts" / "knowledge_search.py"
)
ks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ks)

PROMPT_FILE = ROOT / "prompts" / "system_prompt.txt"


def load_system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8")


# ----------------------------------------------------------------- 术语抽取
# R4 要求「关键术语保留英文原文」。这里从教材片段中识别常见英文术语，
# 用于离线模式生成「中文(English)」形式；API 模式则由 LLM 自行完成。
TERM_MAP = {
    "Cache": "高速缓存",
    "TLB": "快表",
    "CPI": "每条指令的时钟周期数",
    "IPC": "每周期指令数",
    "RISC": "精简指令集",
    "CISC": "复杂指令集",
    "SIMD": "单指令多数据",
    "TLB": "快表",
    "DMA": "直接存储器访问",
    "BIOS": "基本输入输出系统",
    "FIFO": "先进先出",
    "LRU": "最近最少使用",
    "Offset": "偏移",
    "Index": "索引",
    "Tag": "标签",
    # 教材高频术语补充（便于 R4 术语对照与课堂讲解）
    "pipeline": "流水线",
    "instruction": "指令",
    "processor": "处理器",
    "memory": "存储器",
    "register": "寄存器",
    "interrupt": "中断",
    "exception": "异常",
    "virtual memory": "虚拟存储",
    "locality": "局部性",
    "adder": "加法器",
    "bandwidth": "带宽",
    "latency": "延迟",
    "throughput": "吞吐率",
    "coherence": "一致性",
    "multicore": "多核",
    "superscalar": "超标量",
}


def detect_terms(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for en, zh in TERM_MAP.items():
        if en in text and (en, zh) not in found:
            found.append((en, zh))
    return found


# 疑问句式中的虚词，不参与「句子相关度」打分
_Q_STOP = re.compile(
    r"什么是|是什么|请问|如何|怎么|怎样|为什么|介绍一下|解释|说明|请|"
    r"的|了|吗|呢|和|与|或|以及|区别|关系|有什么|哪些|一下|讲|说说"
)


def _question_terms(question: str) -> list[str]:
    """从问题中抽取用于给句子打分的实义词（不含疑问虚词）。

    注意：不要生成「跨词」的 n-gram 片段（如「相联全相」「全相联组」），
    这类伪词在教材里不存在，却会稀释真实词的权重。
    只保留按标点/空格切出的自然词，以及 4 字以上的整块术语。
    """
    q = _Q_STOP.sub(" ", question or "")
    q = re.sub(r"[^\w\u4e00-\u9fff\s]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    terms: list[str] = [w for w in q.split(" ") if len(w) >= 2]
    # 「直接相联、全相联和组相联」这类顿号/连接词结构，已在上一步切成多个词；
    # 这里只补充整块 4 字术语（不含跨词滑窗），且要求它确实是原串的一部分。
    flat = q.replace(" ", "")
    for chunk in re.findall(r"[\u4e00-\u9fff]{4,}", flat):
        if chunk not in terms:
            terms.append(chunk)
    return terms


# ----------------------------------------------------------------- 离线回答
def answer_offline(question: str, hits: list[dict]) -> dict:
    """基于检索结果生成抽取式回答（不调用 LLM）。

    这是一个「可验证的确定性基线」：所有句子都能追溯到检索片段，
    因此天然满足 R2；页码直接取自片段元数据，因此满足 R3。
    """
    log: dict = {"retrieval_called": True, "query": question, "hits": len(hits)}

    # ---- R5：无检索结果或相关性不足 -> 如实说明未覆盖
    if not hits:
        return {
            "answer": (
                "教材未找到相关内容。\n\n"
                f"我检索的关键词是：{question}\n"
                "该问题在《计算机体系结构基础》教材知识库中没有匹配到相关内容，"
                "因此无法基于教材作答。\n\n"
                "说明：本助教只能依据《计算机体系结构基础》教材内容回答问题。"
                "若该问题不属于本教材范围（例如与他人课程、编程作业或其它学科相关），"
                "请咨询相应渠道。你可以换用教材中的术语再试一次。"
            ),
            "citations": [],
            "log": log,
        }

    # ---- R6：按句切分检索片段，只做转述与短引用（每段最多引用 2 句）
    body_lines: list[str] = []

    # R4：识别并标注关键英文术语。
    # 只取与问题相关的术语——早期版本会把片段里出现的所有术语都列出来，
    # 导致问「流水线」却列出 FIFO/LRU 等无关条目，反而干扰理解。
    hits_blob = " ".join(h["text"] for h in hits[:3])
    q_flat = re.sub(r"[^\w\u4e00-\u9fff]", "", question)
    terms: list[tuple[str, str]] = []
    for en, zh in TERM_MAP.items():
        # 保留条件：英文出现在问题里，或中文对照词出现在问题里，
        # 或该术语在命中片段中确实是高频出现的（>=2 次）
        relevant = (
            (en and en.lower() in question.lower())
            or (zh and zh in q_flat)
            or hits_blob.count(en) >= 2
        )
        if relevant and (en, zh) not in terms:
            terms.append((en, zh))
    # 兜底：若一个都没筛出来，仍给前两个（保证 R4 有输出）
    if not terms:
        terms = detect_terms(hits_blob)[:2]
    if terms:
        body_lines.append("**关键术语**（保留英文原文）：")
        for en, zh in terms[:4]:
            body_lines.append(f"- {zh}({en})")
        body_lines.append("")

    # ---- 从检索片段中挑选「最能回答该问题」的句子
    # 早期版本直接取每块前 2 句，导致：
    #   ① 句子从中间开始（前一句被切掉），读起来像残片；
    #   ② 混入「习题」「图 9.4」等无回答价值的内容；
    #   ③ 抓不到重点（问「局部性原理」，给出的是"修马路"比喻）。
    # 现改为按「与问题的相关度」给每句打分后挑选。
    EXERCISE = re.compile(r"习题|练习|请给出|请说明|试求|答案见|思考题")
    FIGCAP = re.compile(r"^[\d\s\.\-～~]*[图表]\s*\d")
    # PDF 提取常把「图9.24:」变成「图9 24:」，点号丢失，需单独识别
    FIGCAP_INLINE = re.compile(r"图\s*\d+\s*\d*\s*[:：]|表\s*\d+\s*\d*\s*[:：]")
    HEADER = re.compile(r"^\d{1,3}第[一二三四五六七八九十]+章|^第[一二三四五六七八九十]+章")
    # 「如图 9.24 所示」「见表 3.1」这类纯交叉引用的句子信息量极低，
    # 命中关键词时得分却很高，会把真正有解释力的句子挤掉。
    XREF = re.compile(
        r"如图\s*\d|见图\s*\d|表\s*\d+(?:\.\d+)?\s*(?:所示|中)|图\s*\d+(?:\.\d+)?\s*:|所示[。；]?$"
    )
    # 页眉/页码混入句中的形态，如「如 4.2 六种常见的上下文切换场景97 Linux 内核…」
    # 特征：小节号(4.2) + 中文标题 + 紧跟页码数字。直接删掉这一段，句子才通顺。
    INLINE_HEADER = re.compile(
        r"\d+\.\d+\s*[\u4e00-\u9fff、（）\w]{2,30}?\s*\d{1,3}\s*"
    )

    def clean_inline(s: str) -> str:
        """清除句中混入的页眉/小节标题残留。"""
        out = INLINE_HEADER.sub("", s)
        # 句首的小节编号残留，如「3.3.2.3 TLB 虚实地址翻译过程用TLB …」
        out = re.sub(r"^\s*\d+(?:\.\d+)+\s*", "", out)
        out = re.sub(r"\s{2,}", " ", out).strip()
        return out or s

    def score_sentence(s: str) -> float:
        """给句子打相关度分。

        关键：用「命中词数 / 问题词数」的**覆盖率**作为主信号，而不是
        把每个命中词的权重累加。原因是累加会让「直接把三个名词罗列一遍」
        的句子（如「直接相联、全相联和组相联Cache 的结构如图…」）得到
        虚高分数，反而压过真正解释原理的句子。
        """
        qterms = [t for t in _question_terms(question) if t]
        if not qterms:
            return 0.0
        hit = [t for t in qterms if t in s]
        cover = len(hit) / len(qterms)  # 0~1
        sc = cover * 6.0
        # 命中较长（更具体）的术语，额外加权
        if hit:
            sc += min(max(len(t) for t in hit), 6) * 0.5
        # 含定义/解释性标记的句子更可能是答案
        if re.search(r"是指|指的是|称为|定义为|也就是说|即|换句话说|包括|分为|只能|仅需要|需要和", s):
            sc += 2.0
        # 纯交叉引用（如图 X.Y 所示）信息量低，显著降权
        if XREF.search(s):
            sc -= 4.0
        # 含图注/表注（如「图9 24: 直接相联…」）的句子是图题碎片，重罚
        if FIGCAP_INLINE.search(s):
            sc -= 8.0
        # 过短或过长都不理想
        if len(s) < 15:
            sc -= 2.0
        if len(s) > 200:
            sc -= 1.0
        return sc

    candidates: list[tuple[float, str, str]] = []  # (得分, 句子, 引用)
    for h in hits[:4]:
        # 按句切分；句内 PDF 硬换行折叠为单行，避免产生无引用的孤立片段
        sents = [s.strip() for s in re.split(r"(?<=[。！？；])", h["text"]) if s.strip()]
        sents = [re.sub(r"\s*\n\s*", " ", s).strip() for s in sents]
        for s in sents:
            # 过滤无回答价值的内容
            if FIGCAP.match(s) or HEADER.match(s):
                continue
            if EXERCISE.search(s):
                continue
            # 图注/表注碎片：必须在 clean_inline 之前判断，
            # 否则「图9.24:」字样会被清理掉，导致漏判
            if FIGCAP_INLINE.search(s):
                continue
            # 清除句中混入的页眉/页码残留
            s = clean_inline(s)
            if len(s) < 15:
                continue
            # 去掉句子开头的孤立标点与残片
            s = re.sub(r"^[。，、；：\s]+", "", s)
            # 句子以「的」「和」等连接词开头 -> 多半是上一句被切断的残片
            if re.match(r"^(的|和|与|或|并且|而且|但是|但|则|所以|因此|此外|另外)", s):
                continue
            if len(s) < 15:
                continue
            candidates.append((score_sentence(s), s, h["citation"]))

    # 按得分排序，同一引用内最多取 2 句，总条数 <=3
    candidates.sort(key=lambda x: -x[0])
    per_cite: dict[str, int] = {}
    picked: list[tuple[str, str]] = []

    def _too_similar(a: str, b: str) -> bool:
        """判断两句是否高度重复（避免回答里出现两条几乎一样的内容）。"""
        # 取较长句的前 40 字作指纹；若包含于另一句则视为重复
        sa, sb = a[:40], b[:40]
        if not sa or not sb:
            return False
        return sa in b or sb in a or a[:25] == b[:25]

    for sc, s, cite in candidates:
        if per_cite.get(cite, 0) >= 2:
            continue
        if any(_too_similar(s, p[0]) for p in picked):  # 去重
            continue
        # 截断过长句子
        if len(s) > 150:
            s = s[:150].rstrip() + "……"
        picked.append((s, cite))
        per_cite[cite] = per_cite.get(cite, 0) + 1
        if len(picked) >= 3:
            break

    # 若筛选后为空（极端情况），回退到原逻辑
    if not picked:
        for h in hits[:3]:
            sents = [s.strip() for s in re.split(r"(?<=[。！？；])", h["text"]) if s.strip()]
            sents = [s for s in sents if len(s) >= 12]
            if sents:
                s = sents[0]
                if len(s) > 150:
                    s = s[:150].rstrip() + "……"
                picked.append((s, h["citation"]))
                if len(picked) >= 3:
                    break

    body_lines.append("**教材中的相关说明**：")
    for s, cite in picked:
        body_lines.append(f"- {s} {cite}")

    body_lines.append("")
    # 引用来源只列正文实际用到的页码，保持前后一致（避免列了却没用到）
    used_cites: list[str] = []
    for _, cite in picked:
        if cite not in used_cites:
            used_cites.append(cite)
    body_lines.append("**引用来源**：" + "、".join(used_cites))

    return {
        "answer": "\n".join(body_lines),
        "citations": [h["citation"] for h in hits[:3]],
        "log": log,
    }


# ----------------------------------------------------------------- API 回答
def answer_with_api(question: str, hits: list[dict], model: str) -> dict:
    """调用 OpenAI 兼容 API，把检索结果作为上下文交给 LLM 生成回答。

    环境变量：
      ARCH_TUTOR_API_KEY   —— 必需，API 密钥（绝不硬编码）
      ARCH_TUTOR_BASE_URL  —— 可选，默认 https://api.deepseek.com/v1
    """
    api_key = os.environ.get("ARCH_TUTOR_API_KEY")
    if not api_key:
        raise RuntimeError(
            "未设置环境变量 ARCH_TUTOR_API_KEY。\n"
            "请先设置：$env:ARCH_TUTOR_API_KEY='sk-...'（PowerShell）\n"
            "注意：不要把密钥写入代码或提交物。"
        )
    base_url = os.environ.get("ARCH_TUTOR_BASE_URL", "https://api.deepseek.com/v1")

    context = (
        "\n\n".join(
            f"[片段{i}] {h['citation']} 章节：{h['chapter']}"
            + (f" / {h['section']}" if h.get("section") else "")
            + f"\n{h['text']}"
            for i, h in enumerate(hits, 1)
        )
        if hits
        else "（无检索结果）"
    )

    user_msg = (
        f"用户问题：{question}\n\n"
        f"以下是 knowledge_search 返回的教材片段，请**只**依据它们作答：\n{context}"
    )

    import urllib.request

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": load_system_prompt()},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = data["choices"][0]["message"]["content"]
    return {
        "answer": text,
        "citations": re.findall(r"【教材 p\.[\d\-]+】", text),
        "log": {"retrieval_called": True, "query": question, "hits": len(hits)},
    }


# ----------------------------------------------------------------- 主流程
def run(question: str, mode: str = "offline", model: str = "deepseek-chat",
        topk: int = 5) -> dict:
    """完整 RAG 流程：**先检索（R1），后回答**。"""
    # ---- R1：回答任何课程问题前，必须先检索知识库
    hits = ks.search(question, topk=topk)

    # ---- R2/R5 前置闸门：检索结果若与问题实质无关，视为「教材未覆盖」。
    # 避免把仅因个别词巧合命中的无关片段当作事实依据。
    if hits and not ks.relevance_gate(question, hits):
        hits = []

    if mode == "api":
        return answer_with_api(question, hits, model)
    return answer_offline(question, hits)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Arch-Tutor 教材知识库智能问答系统（参考实现）"
    )
    ap.add_argument("question", help="用户问题")
    ap.add_argument("--api", action="store_true", help="调用 LLM API（默认离线模板模式）")
    ap.add_argument("--offline", action="store_true", help="强制离线模式")
    ap.add_argument("--model", default="deepseek-chat")
    ap.add_argument("--topk", type=int, default=5)
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    mode = "api" if (args.api and not args.offline) else "offline"
    try:
        result = run(args.question, mode=mode, model=args.model, topk=args.topk)
    except Exception as e:  # noqa: BLE001
        print(f"[错误] {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print("=" * 70)
        print(f"问题：{args.question}")
        print(f"模式：{mode}   检索命中：{result['log']['hits']}")
        print("=" * 70)
        print(result["answer"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
