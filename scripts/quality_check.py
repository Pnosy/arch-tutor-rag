# -*- coding: utf-8 -*-
"""回答质量评估：用不同难度的问题检验离线回答的实际效果。"""
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
kb = Path(__file__).resolve().parents[1]


def load(name, p):
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ks = load("ks", kb / "scripts" / "knowledge_search.py")
agent = load("ag", kb / "agents" / "arch_tutor_agent.py")

QUESTIONS = [
    ("概念定义", "什么是局部性原理"),
    ("对比区分", "异常和中断有什么区别"),
    ("计算公式", "CPI 和 CPU 时间怎么计算"),
    ("机制过程", "TLB 地址翻译的过程是怎样的"),
    ("原因分析", "为什么要采用流水线技术"),
]

for kind, q in QUESTIONS:
    print("=" * 78)
    print(f"[{kind}] 问：{q}")
    print("=" * 78)
    hits = ks.search(q, topk=3)
    gated = bool(hits) and ks.relevance_gate(q, hits)
    res = agent.answer_offline(q, hits if gated else [])
    print(res["answer"])
    print()
