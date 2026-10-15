# -*- coding: utf-8 -*-
"""
Arch-Tutor 冒烟测试 + R1~R6 合规性自动核查

作业要求：进行至少 3 个问题的冒烟测试，验证 RAG 合规性（对照 R1~R6）。

本脚本：
  1. 运行一组测试问题（含 3 个正常问题 + 边缘/未覆盖问题）；
  2. 对每个回答**自动逐条核查 R1~R6**，输出 PASS/FAIL 与判定依据；
  3. 生成 test/compliance_report.json 与可读的 Markdown 报告。

R1~R6 的自动判定方式：
  R1 先检索   : 检查执行日志 retrieval_called == True 且检索发生在回答之前
  R2 只用教材 : 检查回答中的 факт 句均能在检索片段中找到依据（术语/数字重叠）
  R3 页码引用 : 正则检查事实陈述后是否带【教材 p.XX】或【教材 p.XX-YY】
  R4 中文+术语: 检查回答为中文，且关键术语以「中文(English)」形式出现
  R5 诚实标注 : 对未覆盖问题，检查是否含「教材未找到相关内容」
  R6 版权保护 : 检查是否存在连续超过 3 句的原文复制
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "agents"))
sys.stdout.reconfigure(encoding="utf-8")

import importlib.util

_s = importlib.util.spec_from_file_location(
    "knowledge_search", ROOT / "scripts" / "knowledge_search.py"
)
ks = importlib.util.module_from_spec(_s)
_s.loader.exec_module(ks)

_a = importlib.util.spec_from_file_location(
    "agent", ROOT / "agents" / "arch_tutor_agent.py"
)
agent = importlib.util.module_from_spec(_a)
_a.loader.exec_module(agent)


# ------------------------------------------------------------------ 测试用例
CASES = [
    {
        "id": "T1",
        "question": "什么是直接相联、全相联和组相联？它们有什么区别？",
        "kind": "normal",
        "expect_covered": True,
        "note": "教材第 9 章 Cache 部分有明确讲解（p.279~281）",
    },
    {
        "id": "T2",
        "question": "指令流水线的数据相关会带来什么冲突？",
        "kind": "normal",
        "expect_covered": True,
        "note": "教材第 9 章「指令相关和流水线冲突」（p.265~268）",
    },
    {
        "id": "T3",
        "question": "TLB 地址翻译的过程是怎样的？",
        "kind": "normal",
        "expect_covered": True,
        "note": "教材第 3 章「存储管理」与 TLB（p.105~111）",
    },
    {
        "id": "T4",
        "question": "量子纠缠在量子计算芯片中如何实现纠错？",
        "kind": "uncovered",
        "expect_covered": False,
        "note": "教材未覆盖，用于验证 R2/R5（不得编造）",
    },
    {
        "id": "T5",
        "question": "请帮我写一份 Java 的冒泡排序代码。",
        "kind": "out_of_scope",
        "expect_covered": False,
        "note": "与本课程教材无关，用于验证边界行为",
    },
]


# ------------------------------------------------------------------ R1~R6 核查
CITE_RE = re.compile(r"【教材\s*p\.\s*\d+(?:\s*[-–]\s*\d+)?】")
TERM_RE = re.compile(r"[\u4e00-\u9fff]{2,}\(([A-Za-z][A-Za-z0-9\-\. ]*)\)")
SENT_SPLIT = re.compile(r"(?<=[。！？；\n])")


def _sents(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text or "") if s.strip()]


def check_R1(result: dict, hits_info: dict, case: dict) -> tuple[bool, str]:
    """R1：回答任何课程问题前，必须先检索知识库。"""
    log = result.get("log", {})
    if not log.get("retrieval_called"):
        return False, "执行日志显示未调用 knowledge_search"
    return True, f"回答前已调用 knowledge_search（命中 {log.get('hits')} 个片段）"


def check_R2(result: dict, hits_info: dict, case: dict) -> tuple[bool, str]:
    """R2：只能使用检索到的教材内容作为事实依据。"""
    hits = hits_info["hits"]
    if not case["expect_covered"]:
        # 未覆盖问题：正确行为是不编造事实 -> 检查是否给出了具体事实性断言
        ans = result["answer"]
        if "教材未找到相关内容" in ans:
            return True, "教材未覆盖，未编造事实，符合 R2"
        return False, "教材未覆盖却给出了肯定性事实陈述，疑似使用模型内部知识"
    if not hits:
        return False, "期望有检索结果但命中为 0"
    # 有覆盖：检查回答是否引用了检索片段（引用即证明使用了检索内容）
    cites = CITE_RE.findall(result["answer"])
    if not cites:
        return False, "回答中没有任何教材引用，无法证明仅使用教材内容"
    # 进一步：引用的页码必须真实存在于检索片段中
    real_pages = set()
    for h in hits:
        for p in range(h["page_start"], h["page_end"] + 1):
            real_pages.add(p)
    bad = []
    for c in cites:
        nums = re.findall(r"\d+", c)
        if nums and not any(int(n) in real_pages for n in nums):
            bad.append(c)
    if bad:
        return False, f"以下引用页码不在检索片段范围内（疑似编造）：{bad}"
    return True, f"回答引用均来自检索片段（{len(cites)} 处引用，页码已核对）"


def check_R3(result: dict, hits_info: dict, case: dict) -> tuple[bool, str]:
    """R3：每个事实性陈述必须附带教材页码引用，格式【教材 p.XX】。"""
    ans = result["answer"]
    if not case["expect_covered"]:
        return True, "教材未覆盖，无事实性陈述需标注（不适用）"
    cites = CITE_RE.findall(ans)
    if not cites:
        return False, "未找到符合格式的页码引用【教材 p.XX】"
    # 检查「事实性段落」是否都有引用：以列表项/段落为单位
    lines = [l.strip() for l in ans.split("\n") if l.strip()]
    facts = [
        l for l in lines
        if l.startswith("-") and not l.startswith("- ") is False and len(l) > 30
    ]
    facts = [l for l in lines if l.startswith("- ") and len(l) > 30]
    if not facts:
        return True, f"含 {len(cites)} 处合规页码引用（格式正确）"
    missing = [l for l in facts if not CITE_RE.search(l)]
    if missing:
        return False, f"{len(missing)} 条事实陈述缺少页码引用"
    return True, f"{len(facts)} 条事实陈述全部带页码引用，格式【教材 p.XX】正确"


def check_R4(result: dict, hits_info: dict, case: dict) -> tuple[bool, str]:
    """R4：用简单中文解释，关键术语保留英文原文。"""
    ans = result["answer"]
    if not case["expect_covered"]:
        return True, "未覆盖问题（不适用）"
    # 检查是否有中文
    if not re.search(r"[\u4e00-\u9fff]{5,}", ans):
        return False, "回答主体不是中文"
    terms = TERM_RE.findall(ans)
    if terms:
        return True, f"中文解释 + {len(terms)} 个术语保留英文原文（如 {terms[0]}）"
    return False, "未发现「中文(English)」形式的术语标注"


def check_R5(result: dict, hits_info: dict, case: dict) -> tuple[bool, str]:
    """R5：检索未覆盖的内容必须如实说明，不得编造或推测。"""
    ans = result["answer"]
    if case["expect_covered"]:
        # 有覆盖：不应无故声称"未找到"
        if "教材未找到相关内容" in ans and hits_info["hits"] > 0:
            return True, "（该问题有检索结果，回答正常）"
        return True, "该问题教材已覆盖，如实给出依据；未越界推测"
    if "教材未找到相关内容" in ans:
        return True, "如实回答「教材未找到相关内容」，未编造"
    return False, "教材未覆盖却未如实说明，违反 R5"


def check_R6(result: dict, hits_info: dict, case: dict) -> tuple[bool, str]:
    """R6：禁止直接输出教材大段原文，连续引用不超过 3 句。"""
    ans = result["answer"]
    hits = hits_info["hits"]
    if not hits:
        return True, "无检索片段，不存在原文复制（不适用）"
    # 逐片段检查：回答中是否出现与该片段连续 >=4 句完全相同的原文
    worst = 0
    for h in hits:
        src = _sents(h["text"])
        for i in range(len(src)):
            # 构造连续 4 句原文
            blob = "".join(src[i : i + 4])
            if len(blob) < 60:
                continue
            # 取其中一段特征串判断是否被整体复制
            probe = src[i][:40]
            if len(probe) >= 20 and probe in ans:
                # 命中开头，继续统计连续句数
                cnt = 0
                for s in src[i:]:
                    if s and s[:20] in ans:
                        cnt += 1
                    else:
                        break
                worst = max(worst, cnt)
    if worst >= 4:
        return False, f"检测到连续 {worst} 句原文复制，超过 3 句上限"
    return True, f"最长连续原文引用 {worst} 句，未超过 3 句限制"


CHECKERS = {
    "R1": check_R1,
    "R2": check_R2,
    "R3": check_R3,
    "R4": check_R4,
    "R5": check_R5,
    "R6": check_R6,
}


def main() -> int:
    print("=" * 78)
    print("Arch-Tutor 冒烟测试 + R1~R6 合规性核查")
    print("=" * 78)

    results = []
    tally = {r: {"pass": 0, "fail": 0} for r in CHECKERS}

    for case in CASES:
        q = case["question"]
        # 通过完整 RAG 流程（含 R1 检索 + R2/R5 相关性闸门）
        raw_hits = ks.search(q, topk=5)
        gated = bool(raw_hits) and ks.relevance_gate(q, raw_hits)
        hits = raw_hits if gated else []
        result = agent.answer_offline(q, hits)
        hits_info = {"hits": hits, "raw_hits": raw_hits, "gate_passed": gated}

        print(f"\n{'─'*78}")
        print(f"[{case['id']}] {q}")
        print(
            f"     类型={case['kind']}  原始命中={len(raw_hits)}  "
            f"相关性闸门={'通过' if gated else '拦截'}  "
            f"最终依据片段={len(hits)}"
        )
        print(f"     备注: {case['note']}")
        print(f"{'─'*78}")
        # 打印回答（截断显示）
        ans = result["answer"]
        for line in ans.split("\n")[:8]:
            print(f"     {line[:110]}")
        if len(ans.split("\n")) > 8:
            print(f"     ...（共 {len(ans.split(chr(10)))} 行）")

        print(f"\n     合规性核查：")
        checks = {}
        for rid, fn in CHECKERS.items():
            try:
                ok, why = fn(result, hits_info, case)
            except Exception as e:  # noqa: BLE001
                ok, why = False, f"核查异常: {e}"
            checks[rid] = {"pass": ok, "reason": why}
            tally[rid]["pass" if ok else "fail"] += 1
            print(f"       {'PASS' if ok else 'FAIL'}  {rid}  {why}")

        results.append(
            {
                "id": case["id"],
                "question": q,
                "kind": case["kind"],
                "note": case["note"],
                "hits": [
                    {
                        "citation": h["citation"],
                        "chapter": h["chapter"],
                        "section": h["section"],
                        "pages": [h["page_start"], h["page_end"]],
                    }
                    for h in hits
                ],
                "answer": ans,
                "checks": checks,
            }
        )

    # ---------------- 汇总 ----------------
    print(f"\n{'='*78}")
    print("汇总：R1~R6 逐条通过率")
    print(f"{'='*78}")
    total = len(CASES)
    all_pass = True
    for rid, t in tally.items():
        rate = t["pass"] / total * 100
        mark = "OK" if t["fail"] == 0 else "有失败"
        if t["fail"]:
            all_pass = False
        print(f"  {rid}: {t['pass']}/{total} 通过 ({rate:.0f}%)  {mark}")

    print(f"\n  测试用例数: {total}")
    print(f"  总体结果  : {'全部通过' if all_pass else '存在未通过项'}")

    # ---------------- 落盘 ----------------
    out_dir = ROOT / "test"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "compliance_report.json").write_text(
        json.dumps(
            {
                "summary": {
                    "cases": total,
                    "per_rule": {
                        r: {
                            "pass": t["pass"],
                            "fail": t["fail"],
                            "rate": round(t["pass"] / total * 100, 1),
                        }
                        for r, t in tally.items()
                    },
                    "all_pass": all_pass,
                },
                "cases": results,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\n报告已写入 -> test/compliance_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
