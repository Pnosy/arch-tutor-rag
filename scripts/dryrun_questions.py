# -*- coding: utf-8 -*-
"""演示预演：测试学生可能提的问题，确认哪些能答、哪些会触发未覆盖。"""
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
kb = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ks", kb / "scripts" / "knowledge_search.py")
ks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ks)

# 覆盖各章的代表性问题
QUESTIONS = [
    "什么是摩尔定律",
    "指令系统设计有哪些原则",
    "异常和中断有什么区别",
    "多核处理器怎么保证缓存一致性",
    "运算器里加法器怎么设计",
    "程序局部性是什么意思",
    "什么是指令流水线",
    "TLB 是做什么的",
    "CPI 和 CPU 时间怎么计算",
    "龙芯处理器是怎么发展起来的",
    # 故意超出教材范围的
    "量子计算机怎么做",
    "帮我写一段 Python",
    "今天天气怎么样",
]

print(f"{'问题':<32}{'闸门':<6}{'首条引用':<16}章节")
print("-" * 80)
ok = 0
for q in QUESTIONS:
    raw = ks.search(q, topk=3)
    passed = bool(raw) and ks.relevance_gate(q, raw)
    if passed and raw:
        h = raw[0]
        ok += 1
        print(f"{q:<32}{'通过':<6}{h['citation']:<16}{h['chapter']}")
    else:
        print(f"{q:<32}{'拦截':<6}{'—':<16}(视为未覆盖)")
print("-" * 80)
print(f"可答 {ok} / {len(QUESTIONS)}")
