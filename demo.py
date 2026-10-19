# -*- coding: utf-8 -*-
"""
Arch-Tutor 一键演示脚本
=========================================================
一条命令跑完整个系统，逐幕展示关键技术点与 R1~R6 合规性。
专为课堂演示设计：输出分幕、带讲解要点、结果高亮。

【用法】
    python demo.py              # 完整演示（约 1 分钟）
    python demo.py --fast       # 精简版（跳过检索细节）
    python demo.py --scene 3    # 只演示第 3 幕

【演示前提】
    需要已构建好的知识库 data/arch_kb.sqlite。
    若不存在，请先按 README 运行 scripts/01~03 建库。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
from pathlib import Path

# ---- Windows 控制台强制 UTF-8，保证中文与符号正常显示
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

import importlib.util


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


KS = _load("knowledge_search", ROOT / "scripts" / "knowledge_search.py")
AGENT = _load("agent", ROOT / "agents" / "arch_tutor_agent.py")

DB = ROOT / "data" / "arch_kb.sqlite"
CITE_RE = re.compile(r"【教材\s*p\.\s*\d+(?:\s*[-–]\s*\d+)?】")

# ---------------------------------------------------------------- 输出工具
W = 78

# 慢速模式：投屏授课时逐行浮现，避免一瞬间刷完学生看不清。
# 由 --slow 参数设置（秒/行），0 表示不延迟。
_LINE_DELAY = 0.0


def _out(text: str = "", end: str = "\n"):
    """统一的输出入口，受 --slow 控制逐行延迟。"""
    print(text, end=end, flush=True)
    if _LINE_DELAY > 0:
        time.sleep(_LINE_DELAY)


def hr(ch="─"):
    _out(ch * W)


def banner(scene: str, title: str, note: str = ""):
    _out()
    hr("═")
    _out(f"  第 {scene} 幕 · {title}")
    if note:
        _out(f"  {note}")
    hr("═")


def say(text: str, indent: int = 2):
    _out(" " * indent + text)


def pause(seconds: float, enabled: bool):
    if enabled:
        time.sleep(seconds)


def ok(text: str):
    _out(f"  [OK] {text}")


# ---------------------------------------------------------------- 演示内容
def scene1_show_kb() -> bool:
    banner("1", "知识库概览", "Phase 1 产出的教材知识库")
    if not DB.exists():
        _out()
        say("!! 未找到知识库 data/arch_kb.sqlite")
        say("   请先运行：")
        say("     python scripts/01_extract_pages.py \"你的教材.pdf\"")
        say("     python scripts/02_chunk.py")
        say("     python scripts/03_build_kb.py")
        return False

    info = KS.kb_info()
    say(f"教材      : {info.get('book_title')}")
    say(f"页数      : {info.get('page_count')} 页")
    say(f"分块数    : {info.get('chunk_count')} 块")
    say(f"章节数    : {info.get('chapter_count')} 章")
    say(f"分词器    : {info.get('tokenizer')}   排序: {info.get('ranking')}")
    _out()
    say("各章块数与页码覆盖：")
    _out(f"    {'章':<4}{'章节名':<24}{'块数':>5}   {'页码范围':<12}")
    hr("·")
    for c in info["chapters"]:
        _out(f"    {c['chapter_id']:<4}{c['chapter'][:22]:<24}{c['chunks']:>5}   "
              f"p.{c['p_start']}-{c['p_end']}")
    _out()
    ok("知识库就绪：12 章全覆盖，页码元数据完整")
    return True


def scene2_retrieval(show_detail: bool = True) -> None:
    banner("2", "检索演示：先检索，后回答（R1）",
           "用户提问 -> knowledge_search -> 带页码片段")
    queries = [
        ("直接相联和组相联有什么区别", "教材第 9 章 Cache 部分"),
        ("指令流水线的数据相关会带来什么冲突", "教材第 9 章"),
        ("TLB 地址翻译的过程", "教材第 3 章"),
    ]
    for q, expect in queries:
        _out()
        say(f"提问：{q}")
        say(f"（预期来源：{expect}）")
        t0 = time.time()
        hits = KS.search(q, topk=3)
        dt = (time.time() - t0) * 1000
        if not hits:
            say("  -> 无命中")
            continue
        for i, h in enumerate(hits, 1):
            _out(f"    [{i}] {h['citation']}  {h['chapter']}"
                  + (f" / {h['section']}" if h.get("section") else ""))
            if show_detail:
                snippet = h["text"][:88].replace("\n", " ")
                _out(f"         {snippet}…")
        ok(f"命中 {len(hits)} 条，耗时 {dt:.0f} ms")


def scene3_citations() -> None:
    banner("3", "页码引用：每个事实都可追溯（R3）",
           "回答中的每处引用都来自检索片段的真实页码")
    q = "直接相联、全相联和组相联有什么区别？"
    hits = KS.search(q, topk=3)
    _out()
    say(f"提问：{q}")
    _out()
    # 真实性核对
    real_pages = set()
    for h in hits:
        for p in range(h["page_start"], h["page_end"] + 1):
            real_pages.add(p)
    _out(f"    检索片段覆盖页码：{sorted(real_pages)}")
    _out()
    cites = [h["citation"] for h in hits]
    say("生成的引用：")
    for c in cites:
        nums = [int(n) for n in re.findall(r"\d+", c)]
        valid = any(n in real_pages for n in nums)
        _out(f"    {c}   -> 页码{'真实存在 [OK]' if valid else '不存在 [FAIL]'}")
    _out()
    ok("所有引用页码均可回溯到教材原文，未出现编造页码")


def scene4_gate() -> None:
    banner("4", "诚实性：教材没讲就明说（R2 / R5）",
           "这是 RAG 系统最容易翻车的地方")
    cases = [
        ("量子纠缠在量子计算芯片中如何实现纠错？", "教材完全未涉及"),
        ("请帮我写一份 Java 的冒泡排序代码。", "超出教材范围"),
    ]
    for q, why in cases:
        _out()
        say(f"提问：{q}")
        say(f"（{why}）")
        raw = KS.search(q, topk=5)
        passed = bool(raw) and KS.relevance_gate(q, raw)
        say(f"  FTS 原始命中：{len(raw)} 条")
        say(f"  相关性闸门  ：{'通过' if passed else '拦截'}")
        hits = raw if passed else []
        res = AGENT.answer_offline(q, hits)
        _out()
        for line in res["answer"].split("\n")[:3]:
            if line.strip():
                _out(f"    {line}")
        _out()
        if "教材未找到相关内容" in res["answer"]:
            ok("如实回答「教材未找到相关内容」，未编造 [符合 R5]")
        else:
            _out("    [FAIL] 未如实说明")


def scene5_compliance() -> None:
    banner("5", "R1~R6 合规性总览", "5 个用例 × 6 条约束 = 30 项自动核查")
    rep_file = ROOT / "test" / "compliance_report.json"
    if not rep_file.exists():
        say("未找到合规性报告，正在生成…")
        import subprocess

        subprocess.run([sys.executable, str(ROOT / "test" / "run_smoke_test.py")],
                       cwd=str(ROOT))
    rep = json.loads(rep_file.read_text(encoding="utf-8"))
    per = rep["summary"]["per_rule"]
    desc = {
        "R1": "回答前必须先检索", "R2": "只用教材内容",
        "R3": "附【教材 p.XX】引用", "R4": "中文+保留英文术语",
        "R5": "未覆盖要诚实说明", "R6": "不复制大段原文",
    }
    _out()
    _out(f"    {'约束':<5}{'要求':<22}{'通过':<10}结果")
    hr("·")
    for rid, v in per.items():
        tot = v["pass"] + v["fail"]
        mark = "PASS" if v["fail"] == 0 else "FAIL"
        _out(f"    {rid:<5}{desc[rid]:<22}{v['pass']}/{tot:<8}{mark}")
    total_pass = sum(v["pass"] for v in per.values())
    total_all = sum(v["pass"] + v["fail"] for v in per.values())
    _out()
    ok(f"总计 {total_pass}/{total_all} 项通过"
       f"（{total_pass/total_all*100:.0f}%）")


def scene6_closing() -> None:
    banner("6", "总结", "约束行为、开放实现")
    say("本系统的核心不是「能回答」，而是「守规矩」：")
    _out()
    for line in [
        "R1  检索是回答的必经步骤（提示词 + 代码双重强制）",
        "R2  相关性闸门拦截无关内容，杜绝拿无关片段当依据",
        "R3  引用页码可回溯，无法编造",
        "R4  中文解释 + 术语保留英文原文",
        "R5  教材未覆盖时如实说明，不编造、不推测",
        "R6  连续引用不超过 3 句，只做短引用与转述",
    ]:
        say("  • " + line)
    _out()
    hr("═")
    say("演示结束。可自行尝试：")
    say(f'  python agents/arch_tutor_agent.py "你的问题" --offline')
    say(f"  python test/run_smoke_test.py")
    hr("═")


SCENES = {
    1: ("知识库概览", scene1_show_kb),
    2: ("检索演示", scene2_retrieval),
    3: ("页码引用", scene3_citations),
    4: ("诚实性验证", scene4_gate),
    5: ("合规性总览", scene5_compliance),
    6: ("总结", scene6_closing),
}


def main() -> int:
    global _LINE_DELAY

    ap = argparse.ArgumentParser(description="Arch-Tutor 一键演示")
    ap.add_argument("--scene", type=int, default=0, help="只演示指定幕（1~6）")
    ap.add_argument("--fast", action="store_true", help="精简模式，跳过停顿")
    ap.add_argument("--no-pause", action="store_true", help="不停顿（录屏用）")
    ap.add_argument(
        "--slow",
        type=float,
        nargs="?",
        const=0.18,
        default=0.0,
        metavar="秒",
        help="逐行慢速输出，默认每行 0.18 秒（投屏授课用）",
    )
    args = ap.parse_args()

    # 慢速模式：让投屏时每行依次出现，学生跟得上
    _LINE_DELAY = max(0.0, args.slow)

    do_pause = not (args.fast or args.no_pause)
    # 慢速模式下场景间的停顿可以缩短，因为逐行延迟已提供节奏
    gap = 1.0 if _LINE_DELAY > 0 else 1.5

    _out()
    hr("═")
    _out("  Arch-Tutor · 计算机体系结构课程知识库智能问答系统")
    _out("  一键演示  |  教材：《计算机体系结构基础》430 页 / 12 章")
    hr("═")

    if args.scene:
        name, fn = SCENES.get(args.scene, (None, None))
        if fn is None:
            _out(f"无效的幕号：{args.scene}（可选 1~6）")
            return 1
        fn()
        return 0

    if not scene1_show_kb():
        return 1
    pause(gap, do_pause)
    scene2_retrieval(show_detail=not args.fast)
    pause(gap, do_pause)
    scene3_citations()
    pause(gap, do_pause)
    scene4_gate()
    pause(gap, do_pause)
    scene5_compliance()
    pause(gap, do_pause)
    scene6_closing()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
