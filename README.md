# Arch-Tutor · 计算机体系结构课程知识库智能问答系统

> 《某课程知识库的智能问答系统》分组实践作业
> 教材：**《计算机体系结构基础》** 胡伟武 汪文祥 苏孟豪 张福新 王焕东 章隆兵 肖俊华 刘苏 陈新科 吴瑞阳 李晓钰 高燕萍（430 页，12 章）
> 技术栈：**方案 C** —— SQLite FTS5(trigram) + BM25 + 自研检索逻辑 + 直接调用 LLM API

---

## 一、成果速览

| 指标 | 结果 |
|---|---|
| 教材页数 / 章节数 | 430 页 / 12 章（+6 个部分） |
| 知识块数 | **277** |
| 块粒度（800~1200 tokens） | **270 块达标（97.5%）**，超上限 **0** 块 |
| 章节覆盖率 | **100%（12/12）** |
| 页码元数据完整率 | **100%**（0 块缺失或非法） |
| 检索 Top-1 / Top-3 准确率 | **80% / 90%** |
| **R1~R6 合规性核查** | **30/30 项全部通过** ✅ |

---

## 二、快速开始

> **⚠️ 第一次使用请先读这一段**
>
> 由于教材受版权保护，本仓库**不包含**教材 PDF 和正文数据
> （`pages.jsonl` / `chunks.jsonl` / `arch_kb.sqlite` 均未上传）。
> 这意味着：**刚 clone 下来时系统还不能直接问答**，需要你先准备教材 PDF
> 并运行一次建库脚本（约 1 分钟）。
>
> 仓库里已包含 `data/kb_meta.json`（仅结构元数据：章节名、页码区间、统计数字），
> 可用来看数据，但不含任何教材正文。

### 第 1 步：克隆并安装依赖

```powershell
git clone https://github.com/Pnosy/arch-tutor-rag.git
cd arch-tutor-rag
python -m pip install pymupdf
```

> `pymupdf` **只有建库这一步需要**。之后的检索、问答、演示、测试
> 都只用 Python 标准库，不需要任何第三方包。

### 第 2 步：准备教材并建库

自行合法获取《计算机体系结构基础》电子版（PDF），然后：

```powershell
python scripts/01_extract_pages.py "你的教材路径.pdf"   # 提取 + 检测 12 章
python scripts/02_chunk.py                              # 分块 -> 277 块
python scripts/03_build_kb.py                           # 建 FTS5 知识库
python scripts/04_verify_kb.py                           # 验证（可选）
```

**PDF 路径有三种写法，任选其一：**

```powershell
# ① 直接作为参数（推荐）
python scripts/01_extract_pages.py "D:\教材\计算机体系结构基础.pdf"

# ② 用环境变量
$env:ARCH_TUTOR_PDF = "D:\教材\计算机体系结构基础.pdf"
python scripts/01_extract_pages.py

# ③ 放到项目根目录并改名为「计算机体系结构基础.pdf」，然后直接运行
python scripts/01_extract_pages.py
```

> **关于不同版本的 PDF**：脚本按 PDF 书签识别章节（level≤2 即「章」）。
> 只要该书签结构存在，页数略有差异也能正常建库；分块数与页码区间可能
> 略有不同，属正常现象。若你的教材是别的书，把 `data/chapters.json` 或
> PDF 路径换掉即可复用整套流程。

### 第 3 步：开始使用

```powershell
# 一键演示（6 幕，推荐第一次跑这个）
python demo.py

# 单次问答（无需 API Key）
python agents/arch_tutor_agent.py "什么是直接相联和组相联？" --offline

# 合规性测试
python test/run_smoke_test.py
```

---

### 接入 LLM API（可选）

离线模式已能满足全部 R1~R6 约束，只是语言组织偏"抽取式"。
想要更自然的表达，可接入任意 OpenAI 兼容 API：

```powershell
$env:ARCH_TUTOR_API_KEY = "sk-你的密钥"     # 只放环境变量，切勿写进代码
python agents/arch_tutor_agent.py "讲解指令流水线的数据相关" --api
```

---

## 三、一键演示

```powershell
python demo.py                  # 完整演示（6 幕）
python demo.py --fast           # 精简版
python demo.py --scene 4        # 只演示第 4 幕（诚实性验证）
python demo.py --no-pause       # 录屏模式，不停顿
```

演示分 6 幕：知识库概览 → 检索演示 → 页码引用 → **诚实性验证** →
R1~R6 合规性总览 → 总结。

配套讲解稿见 [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)，含每幕的
操作、预期输出、讲解词与可能的追问。

---

## 三、目录结构

```
arch-rag-kb/
├── demo.py                     ★ 一键演示脚本
├── data/                       # 知识库与中间产物
│   ├── kb_meta.json            # 结构元数据（不含正文，可公开）
│   ├── arch_kb.sqlite          # 知识库（含原文，已 gitignore）
│   ├── chunks.jsonl            # 分块（含原文，已 gitignore）
│   ├── pages.jsonl             # 逐页文本（含原文，已 gitignore）
│   ├── chapters.json           # 12 章边界
│   ├── toc.json                # PDF 书签（210 条）
│   ├── chunk_stats.json        # 分块统计
│   ├── extract_stats.json      # 提取统计
│   └── verify_report.json      # 知识库验证报告
├── scripts/
│   ├── 01_extract_pages.py     # 提取 + 章节检测
│   ├── 02_chunk.py             # 语义分块
│   ├── 03_build_kb.py          # 建 FTS5 库
│   ├── 04_verify_kb.py         # 知识库验证
│   ├── 05_export_meta.py       # 导出可公开的结构元数据
│   ├── knowledge_search.py     ★ 检索工具
│   ├── eval_retrieval.py       # 检索质量评估
│   └── make_*.py               # 交付物生成脚本
├── prompts/
│   ├── system_prompt.txt       ★ 系统提示词
│   └── system_prompt.md        # 提示词 + 设计说明
├── agents/
│   ├── arch_tutor_agent.py     ★ 智能体参考实现
│   ├── arch-tutor-plugin.js    # DSH 插件实现
│   ├── agent.config.json       ★ 智能体配置
│   └── README.md               ★ 启动说明
├── test/
│   ├── run_smoke_test.py       ★ 冒烟测试 + R1~R6 自动核查
│   └── compliance_report.json  # 合规性报告
├── docs/
│   ├── DESIGN.md               # 设计与实施文档
│   ├── DEMO_SCRIPT.md          ★ 课堂演示讲解稿
│   ├── USAGE.md                ★ 使用指南（下载后如何跑起来）
│   └── GITHUB_GUIDE.md         ★ GitHub 上传指南
└── deliverables/               ★ 正式交付物
    ├── Arch-Tutor_测试报告.docx
    ├── Arch-Tutor_实施过程.pptx
    └── Arch-Tutor_小组分工说明.docx
```

---

## 四、交付物对照（作业第七节）

| # | 作业要求 | 本项目文件 | 状态 |
|---|---|---|---|
| 1 | 知识库 + 构建脚本 | `data/arch_kb.sqlite` + `scripts/01~03_*.py` | ✅ |
| 2 | 检索工具 + 调用说明 | `scripts/knowledge_search.py` + `agents/README.md` | ✅ |
| 3 | 系统提示词 + 设计说明 | `prompts/system_prompt.txt` + `system_prompt.md` | ✅ |
| 4 | 智能体配置 + 启动说明 | `agents/agent.config.json` + `agents/README.md` | ✅ |
| 5 | 测试报告（DOCX/PDF） | `deliverables/Arch-Tutor_测试报告.docx` | ✅ |
| 6 | 实施过程 PPT（15~20 页） | `deliverables/Arch-Tutor_实施过程.pptx`（20 页） | ✅ |
| 7 | 小组分工说明 | `deliverables/Arch-Tutor_小组分工说明.docx` | ✅ |

---

## 五、R1~R6 合规性

| 约束 | 要求 | 实现位置 | 验证 | 结果 |
|---|---|---|---|---|
| R1 | 回答前必须先检索 | 提示词§2 + `run()` 调用链强制 | 检查执行日志 | ✅ 5/5 |
| R2 | 只用教材内容 | 提示词§1/§3 + 相关性闸门 | 核对引用页码真实性 | ✅ 5/5 |
| R3 | 附【教材 p.XX】引用 | 提示词§4 + `citation` 字段 | 正则匹配 + 页码核对 | ✅ 5/5 |
| R4 | 中文解释+英文术语 | 提示词§4 + `detect_terms()` | 中文主体 + 术语标注 | ✅ 5/5 |
| R5 | 未覆盖要诚实说明 | 提示词§1/§5 + 闸门拦截 | 是否含标准话术 | ✅ 5/5 |
| R6 | 禁止复制大段原文 | 提示词§5 + 每片段限 2 句 | 统计最长连续引用句数 | ✅ 5/5 |

测试用例覆盖三类场景：**正常问题**（3 个）、**教材未覆盖**（1 个）、**超出教材范围**（1 个）。

---

## 六、技术要点

1. **章节检测用 PDF 书签**：教材由 LaTeX/hyperref 生成，自带 210 条书签，
   层级为「部分/章/节/小节」。直接读取书签零误判，优于正则匹配。

2. **中文检索用 trigram 分词器**：FTS5 默认 `unicode61` 会把整句中文当作
   单一 token，导致中文查询 0 命中；`trigram`（3 字符滑窗）可良好匹配中文子串。

3. **二次排序**：先召回 `topk×8`（≥40）候选池，再用
   「词覆盖度 0.35 + 完整短语 0.15 + 标题命中 0.30 + BM25 相对排名 0.20」
   合成打分——单纯 `LIMIT topk` 会让重排无从发挥。

4. **相关性闸门**：FTS「有命中」≠「相关」。用实义关键词覆盖率（阈值 0.34）
   判定，不达标即走「教材未找到相关内容」分支，这是 R2/R5 的关键保障。

5. **同义词扩展**：内置体系结构术语表（映象↔映像↔映射↔相联、Cache↔高速缓存、
   TLB↔快表 等），解决「用户用词 ≠ 教材用词」导致的漏检。

详见 [docs/DESIGN.md](docs/DESIGN.md)。

---

## 七、注意事项

- **API Key 安全**：所有代码与配置文件均不含任何密钥，`ARCH_TUTOR_API_KEY`
  仅从环境变量读取（作业注意事项第 7 条）。
- **版权**：系统被约束为「连续引用不超过 3 句」，仅做短句引用与转述
  （作业注意事项第 5 条）。
- **教材来源**：使用合法获取的电子版教材，仅用于课程学习（作业注意事项第 1 条）。
