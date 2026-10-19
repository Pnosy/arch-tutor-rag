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

    # ---- R6：按句切分检索片段，只做转述与短引用（每段最多引用 3 句）
    top = hits[0]
    body_lines: list[str] = []

    # R4：识别并标注关键英文术语。
    # 来源有三处，按优先级：
    #   1) 检索片段中出现的英文术语（最贴合教材原文）
    #   2) 用户问题中提到的英文术语
    #   3) 片段里出现的中文术语，反查英文（如「流水线」-> pipeline）
    # 三者合并，保证即使片段恰好没有英文，也能给出术语对照，
    # 避免 R4「关键术语保留英文原文」因检索内容而随机失效。
    hits_blob = " ".join(h["text"] for h in hits[:3])
    terms = detect_terms(hits_blob)
    for extra in detect_terms(question):
        if extra not in terms:
            terms.append(extra)
    # 反查：片段里出现的中文对照词
    for en, zh in TERM_MAP.items():
        if zh and zh in hits_blob and (en, zh) not in terms:
            terms.append((en, zh))
    if terms:
        body_lines.append("**关键术语**（保留英文原文）：")
        for en, zh in terms[:5]:
            body_lines.append(f"- {zh}({en})")
        body_lines.append("")

    body_lines.append("**教材中的相关说明**：")
    used = 0
    for h in hits[:3]:
        # R6 要求「连续原文引用不超过 3 句」。这里采取更严格的策略：
        #   - 每片段最多取 2 句，且截断到较短长度，避免形成连续原文块；
        #   - 对句子做轻度压缩（去掉图号/公式残片/页眉残留），使其成为转述。
        sents = [s.strip() for s in re.split(r"(?<=[。！？；])", h["text"]) if s.strip()]
        # 句子内部可能残留换行（PDF 提取的硬换行），统一折叠为单行，
        # 否则会在回答里产生「无页码引用的孤立片段」，破坏 R3 的格式一致性。
        sents = [re.sub(r"\s*\n\s*", " ", s).strip() for s in sents]
        # 过滤掉明显是页眉、图注、公式残片的句子（转述价值低且易造成原文复制）
        cleaned = []
        for s in sents:
            if re.match(r"^[\d\s\.\-～~]*[图表]\s*\d", s):
                continue
            if re.match(r"^\d{1,3}第[一二三四五六七八九十]+章", s):
                continue
            if len(s) < 12:
                continue
            cleaned.append(s)
        picked = cleaned[:2]
        if not picked:
            picked = sents[:1]
        if not picked:
            continue
        summary = "".join(picked)
        # 控制单条长度，避免整段搬运
        if len(summary) > 160:
            summary = summary[:160].rstrip() + "……"
        body_lines.append(f"- {summary} {h['citation']}")
        used += 1
        if used >= 3:
            break

    body_lines.append("")
    body_lines.append(
        "**引用来源**：" + "、".join(h["citation"] for h in hits[:3])
    )

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
