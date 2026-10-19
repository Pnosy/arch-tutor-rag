# -*- coding: utf-8 -*-
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
root = Path(__file__).resolve().parents[1]
print('=' * 50)
print('  Arch-Tutor 演示环境自检')
print('=' * 50)
print()
print('[1] Python 版本')
print('    ' + sys.version.split()[0])
print()
print('[2] 知识库')
kb = root / 'data' / 'arch_kb.sqlite'
if kb.exists():
    print('    OK  知识库存在 (%.1f MB)' % (kb.stat().st_size / 1048576))
else:
    print('    缺失！需先运行 scripts/01~03 建库')
print()
print('[3] 关键文件')
files = [
    ('scripts/knowledge_search.py', '检索工具'),
    ('agents/arch_tutor_agent.py', '智能体'),
    ('test/run_smoke_test.py', '合规性测试'),
    ('demo.py', '一键演示'),
    ('prompts/system_prompt.txt', '系统提示词'),
    ('data/chapters.json', '章节数据'),
]
missing = 0
for f, desc in files:
    if (root / f).exists():
        print('    OK  %s (%s)' % (f, desc))
    else:
        missing += 1
        print('    缺失 %s (%s)' % (f, desc))
print()
print('[4] 演示脚本试运行')
import subprocess
try:
    r = subprocess.run([sys.executable, str(root / 'demo.py'), '--fast'],
                       capture_output=True, timeout=120)
    if r.returncode == 0:
        print('    OK  demo.py 可正常运行')
    else:
        print('    异常：demo.py 退出码 %d' % r.returncode)
        print('    ' + (r.stderr.decode('utf-8', 'ignore')[:300]))
except Exception as e:
    print('    异常：%s' % e)
print()
print('=' * 50)
if kb.exists() and missing == 0:
    print('  自检通过，可以开始演示')
    print('  建议命令：python demo.py --slow')
else:
    print('  存在问题，请按上面提示处理')
print('=' * 50)
