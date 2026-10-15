# Arch-Tutor 实施说明（启动指南）

> 《某课程知识库的智能问答系统》分组作业 · 交付物 №4：智能体配置 + 启动说明
> 教材：《计算机体系结构基础》胡伟武 等，430 页，12 章
> 技术栈：**方案 C** —— SQLite FTS5 + 直接调用 LLM API + 自定义检索逻辑

---

## 一、环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows / Linux / macOS |
| Python | 3.10+ |
| 依赖库 | `pymupdf`（仅建库阶段需要） |
| 数据库 | SQLite（Python 内置，需编译时启用 FTS5；官方发行版默认已启用） |
| LLM API | 可选。离线模式无需任何 API Key |

安装依赖：

```powershell
python -m pip install pymupdf
```

> **说明**：检索与问答阶段**不需要**任何第三方库——FTS5、BM25 均由 SQLite 内置，
> HTTP 调用使用标准库 `urllib`。`pymupdf` 只在从 PDF 建库时使用。

---

## 二、目录结构

```
arch-rag-kb/
├── data/                          # 知识库与中间产物
│   ├── arch_kb.sqlite             # ★ 知识库（SQLite + FTS5）
│   ├── chunks.jsonl               # 分块结果（277 块）
│   ├── chapters.json              # 章节边界
│   ├── pages.jsonl                # 逐页文本
│   ├── toc.json                   # PDF 书签目录
│   └── verify_report.json         # 知识库验证报告
├── scripts/
│   ├── 01_extract_pages.py        # 步骤1 提取文本 + 章节检测
│   ├── 02_chunk.py                # 步骤2 语义分块
│   ├── 03_build_kb.py             # 步骤3 建库（FTS5）
│   ├── 04_verify_kb.py            # 步骤4 验证知识库
│   ├── knowledge_search.py        # ★ 检索工具
│   └── eval_retrieval.py          # 检索质量评估
├── prompts/
│   ├── system_prompt.txt          # ★ 系统提示词（可直接使用）
│   └── system_prompt.md           # 提示词 + 设计说明
├── agents/
│   ├── arch_tutor_agent.py        # ★ 智能体参考实现（完整 RAG 流程）
│   ├── arch-tutor-plugin.js       # DSH 插件实现
│   ├── agent.config.json          # ★ 智能体配置
│   └── README.md                  # 本文件
├── test/
│   ├── run_smoke_test.py          # ★ 冒烟测试 + R1~R6 自动核查
│   └── compliance_report.json     # 合规性报告
└── docs/
    └── DESIGN.md                  # 设计与实施文档
```

★ = 关键交付物

---

## 三、快速启动

### 3.1 重建知识库（可选，仓库内已含成品）

```powershell
cd arch-rag-kb
python scripts/01_extract_pages.py     # 提取 430 页 + 检测 12 章
python scripts/02_chunk.py             # 分块 -> 277 块
python scripts/03_build_kb.py          # 建 FTS5 库
python scripts/04_verify_kb.py         # 验证（覆盖率/检索准确率）
```

### 3.2 检索工具自测

```powershell
# 命令行检索
python scripts/knowledge_search.py "什么是直接相联和组相联" --topk 5

# 查看知识库信息
python scripts/knowledge_search.py "" --info

# JSON 输出（便于程序调用）
python scripts/knowledge_search.py "指令流水线冲突" --topk 3 --json
```

### 3.3 启动问答系统

**方式一：离线模式（推荐用于验证与演示，无需 API Key）**

```powershell
python agents/arch_tutor_agent.py "什么是直接相联和组相联？" --offline
```

**方式二：接入 LLM API**

```powershell
# 1. 设置 API Key（只放环境变量，不要写进代码/文档）
$env:ARCH_TUTOR_API_KEY = "sk-你的密钥"

# 2. 可选：自定义 API 地址（默认 https://api.deepseek.com/v1）
$env:ARCH_TUTOR_BASE_URL = "https://api.deepseek.com/v1"

# 3. 提问
python agents/arch_tutor_agent.py "讲解指令流水线的数据相关" --api --model deepseek-chat
```

> ⚠️ **安全要求**（作业注意事项第 7 条）：API Key 仅从环境变量读取。
> 本项目的所有代码与配置文件中**均不含任何密钥**，`ARCH_TUTOR_API_KEY`
> 由使用者在本地会话中设置。

### 3.4 运行合规性测试

```powershell
python test/run_smoke_test.py
```

输出 R1~R6 逐条 PASS/FAIL 判定与依据，并生成
`test/compliance_report.json`。

---

## 四、接入 DSH（可选）

若使用 DSH（DeepSeek Harness）作为智能体框架，插件
`agents/arch-tutor-plugin.js` 已实现：

- 注册 `knowledge_search` 工具（`ctx.tools.register`）
- 注入五段式系统提示词（`ctx.systemPrompt.section`）
- 通过 `tools/pre-execute` 钩子记录检索调用日志，供 R1 核查

插件通过 Host Service 契约编写，依赖：

```js
ctx.tools.register({ name, description, parameters, output, execute })
ctx.systemPrompt.section({ name, order, content })
ctx.on('tools/pre-execute', handler)
```

安装步骤：

1. 将 `agents/arch-tutor-plugin.js` 放入 profile 的插件目录；
2. 在 profile 的 `cordis.patch.yml` 中声明该插件入口；
3. 在插件配置中指定 `pythonPath` 与 `topk`（见 `agent.config.json`）。

> **注**：本作业的核心交付不依赖 DSH —— 3.3 节的 Python 实现即可完整
> 独立运行并满足全部 R1~R6 约束。DSH 插件作为「方案 A 兼容」的附加实现提供。

---

## 五、配置项说明

完整配置见 `agents/agent.config.json`，关键字段：

| 字段 | 含义 | 取值 |
|---|---|---|
| `knowledgeBase.type` | 知识库类型 | `sqlite-fts5` |
| `knowledgeBase.tokenizer` | 分词器 | `trigram`（适配中文） |
| `knowledgeBase.ranking` | 排序算法 | `bm25` |
| `tools[0].required` | 是否强制调用 | `true`（对应 R1） |
| `tools[0].relevanceGate.threshold` | 相关性阈值 | `0.34` |
| `prompt.order` | 提示词优先级 | `-100`（最前） |
| `ragFlow.citationFormat` | 引用格式 | `【教材 p.XX】`（对应 R3） |
| `ragFlow.maxConsecutiveQuoteSentences` | 最大连续引用句数 | `3`（对应 R6） |
| `ragFlow.notFoundMessage` | 未覆盖话术 | `教材未找到相关内容`（对应 R5） |

---

## 六、常见问题

**Q1：报错「知识库不存在」**
先运行 `python scripts/03_build_kb.py` 生成 `data/arch_kb.sqlite`。

**Q2：报错「no such module: fts5」**
当前 Python 的 SQLite 未启用 FTS5。解决：改用官方 Python 发行版
（python.org 版本默认启用 FTS5）。

**Q3：检索结果不相关**
1. 确认提问使用了教材术语（对照 `data/chapters.json` 的章节名）；
2. 尝试 `--topk 8` 扩大返回；
3. 运行 `python scripts/eval_retrieval.py` 查看检索质量。

**Q4：中文检索命中率低**
本方案使用 `trigram` 分词器（对中文子串匹配友好），并内置了体系结构
术语同义词表（如「映象/映像/映射/相联」互通，见
`scripts/knowledge_search.py` 的 `SYNONYMS`）。可按需扩充该表。

**Q5：没有 API Key 能否演示？**
可以。`--offline` 模式完全离线运行，且通过全部 R1~R6 合规性检查，
适合课堂演示与自动化验证。
