# -*- coding: utf-8 -*-
"""检索质量快速评估：对若干问题打印 Top-K 命中，人工判断相关性。"""
import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ks", ROOT / "scripts/knowledge_search.py")
ks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ks)

QUERIES = [
    "什么是Cache的映象方式",
    "Cache一致性协议是怎么工作的",
    "指令流水线的基本原理",
    "龙芯处理器的发展",
    "TLB地址翻译的过程",
    "异常和中断有什么区别",
    "多核处理器如何保证存储一致性",
    "量子计算在体系结构中的应用",   # 教材不应覆盖 -> 验证诚实性
]

for q in QUERIES:
    hits = ks.search(q, topk=3)
    print(f"\n########## {q}   (命中 {len(hits)})")
    for i, h in enumerate(hits, 1):
        print(
            f"  [{i}] {h['citation']}  {h['chapter']} / {h['section'][:26]}"
            f"   score={h['score']}"
        )
