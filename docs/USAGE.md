# 使用指南（从 GitHub 下载后如何跑起来）

> 本文件面向**从 GitHub 克隆本项目的人**。
> 项目地址：https://github.com/Pnosy/arch-tutor-rag
> 如果你是项目作者本人，日常使用见 [README](../README.md)。

---

## 一、先明白一件事：刚下载时系统还跑不了问答

本仓库**不包含**教材 PDF 和教材正文，原因是教材受版权保护：

| 文件 | 是否在仓库 | 说明 |
|---|:---:|---|
| `教材.pdf` | ❌ | 需你自行合法获取 |
| `data/pages.jsonl`（逐页原文） | ❌ | 建库时生成 |
| `data/chunks.jsonl`（分块原文） | ❌ | 建库时生成 |
| `data/arch_kb.sqlite`（知识库） | ❌ | 建库时生成 |
| `data/kb_meta.json`（结构元数据） | ✅ | 仅章节名/页码/统计，无正文 |
| 全部代码、文档、PPT、测试报告 | ✅ | 完整可看 |

所以流程是：**下载 → 准备 PDF → 建库（1 分钟）→ 使用**。

---

## 二、完整步骤

### 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows / Linux / macOS（命令以 PowerShell 为例） |
| Python | 3.10 或更高 |
| 第三方库 | 仅 `pymupdf`，且只在建库时用到 |
| SQLite | Python 自带；需支持 FTS5（官方发行版默认支持） |
| 网络 | 仅在接入 LLM API 时需要；离线模式完全不需要 |

### 第 1 步 · 下载项目

```powershell
git clone https://github.com/Pnosy/arch-tutor-rag.git
cd arch-tutor-rag
```

> 没有装 Git？在 GitHub 页面点 **Code → Download ZIP** 解压也可以。

### 第 2 步 · 安装依赖

```powershell
python -m pip install pymupdf
```

> 只有 `scripts/01_extract_pages.py` 需要它。如果你已经拿到了
> 别人分享的 `arch_kb.sqlite`，这步可以跳过。

### 第 3 步 · 准备教材 PDF

《计算机体系结构基础》（胡伟武 等）的**合法电子版**，自行获取。

PDF 路径有三种指定方式，任选其一：

```powershell
# ① 命令行参数（最直接）
python scripts/01_extract_pages.py "D:\教材\计算机体系结构基础.pdf"

# ② 环境变量
$env:ARCH_TUTOR_PDF = "D:\教材\计算机体系结构基础.pdf"
python scripts/01_extract_pages.py

# ③ 放到项目根目录并命名为「计算机体系结构基础.pdf」，直接运行
python scripts/01_extract_pages.py
```

### 第 4 步 · 建库（三行命令，约 1 分钟）

```powershell
python scripts/01_extract_pages.py "你的教材.pdf"
python scripts/02_chunk.py
python scripts/03_build_kb.py
```

**成功时会看到：**

```
[1/4] 打开 PDF: ...
      页数=430  标题='计算机体系结构基础'
[3/4] 检测章节边界 ...
      TOC 条目=210  识别章节=12
        ch01 引言                p. 37- 64  (第一部分 引言)
        ...
[2/3] 写出 chunks.jsonl: 共 277 块
      token 均值=1082 最小=344 最大=1199
      落在 800~1200 目标区间的块: 270 (97.5%)
[4/4] 自检 ...
      chunks=277  fts行数=277  章节=12  页覆盖=37-429
```

### 第 5 步 · 开始使用

```powershell
# ★ 一键演示（6 幕，第一次强烈建议跑这个）
python demo.py

# 单次提问（离线，无需 API Key）
python agents/arch_tutor_agent.py "什么是直接相联和组相联？" --offline

# 合规性测试（5 用例 × 6 约束 = 30 项自动核查）
python test/run_smoke_test.py
```

---

## 三、常用命令速查

| 我想… | 命令 |
|---|---|
| 完整演示 | `python demo.py` |
| 只看诚实性验证 | `python demo.py --scene 4` |
| 录屏（不停顿） | `python demo.py --no-pause` |
| 问一个问题 | `python agents/arch_tutor_agent.py "问题" --offline` |
| 接入大模型 | 设 `ARCH_TUTOR_API_KEY` 后加 `--api` |
| 单独检索 | `python scripts/knowledge_search.py "关键词" --topk 5` |
| 看知识库信息 | `python scripts/knowledge_search.py "" --info` |
| 验证知识库质量 | `python scripts/04_verify_kb.py` |
| 跑合规性测试 | `python test/run_smoke_test.py` |

---

## 四、你会得到什么

建库完成后，各环节的实际指标（与作者实测一致，已验证可复现）：

| 指标 | 结果 |
|---|---|
| 教材页数 | 430 页 |
| 识别章节 | 12 章（PDF 书签检测） |
| 知识块数 | 277 块 |
| 块粒度达标率 | 97.5%（270 块落在 800~1200 tokens） |
| 章节覆盖率 | 100%（12/12） |
| 检索 Top-1 / Top-3 | 80% / 90% |
| R1~R6 合规性 | 30/30 全部通过 |

---

## 五、常见问题

**Q1：报错「未找到教材 PDF」**

说明脚本没找到 PDF。用第 3 步的三种方式之一显式指定路径。
注意中文路径要用引号包住。

**Q2：报错「缺少依赖库 PyMuPDF」**

```powershell
python -m pip install pymupdf
```

**Q3：报错「no such module: fts5」**

当前 Python 的 SQLite 没编译 FTS5。解决：改用 python.org 官方发行版
（默认已启用），或 Anaconda 的 Python。

**Q4：报错「未找到知识库 data/arch_kb.sqlite」**

还没建库。先跑第 4 步的三条命令。

**Q5：我的教材页数 / 分块数和你说的不一样**

正常。`README` 里的数字基于作者使用的那个 PDF 版本。
脚本按 **PDF 书签**识别章节，只要书签结构在，页数略有差异不影响使用；
分块数和页码区间会相应变化。

**Q6：我想用另一本教材**

可以，整套流程是通用的：

1. 把 PDF 路径换掉；
2. 若新教材没有 PDF 书签，`01_extract_pages.py` 会识别不到章节，
   需要改用正则匹配章节标题（修改 `build_chapters()`）；
3. 同义词表 `scripts/knowledge_search.py` 的 `SYNONYMS` 可按新领域术语扩充。

**Q7：能离线用吗？**

能。`--offline` 模式完全不调用任何外部服务，且通过全部 R1~R6 约束。
只是回答偏"抽取式"（直接引用教材短句），不如大模型组织得自然。

**Q8：演示脚本跑起来中文乱码**

Windows 终端编码问题：

```powershell
chcp 65001
$env:PYTHONIOENCODING = "utf-8"
```

`demo.py` 已内置 UTF-8 设置，通常不会乱码；`arch_tutor_agent.py` 若乱码可用上述方法。

**Q9：怎么确认我建的知识库是对的？**

```powershell
python scripts/04_verify_kb.py
```

会输出块数统计、章节覆盖率、检索准确率，并写入 `data/verify_report.json`。
若章节覆盖率为 100%、块数在 270~280 附近，说明建库正常。

**Q10：我改动了代码，怎么再打包给别人？**

```powershell
git add -A
git commit -m "说明改了什么"
git push
```

⚠️ 推送前务必确认没有把教材原文带上去：

```powershell
git ls-files | Select-String "pages.jsonl|chunks.jsonl|arch_kb.sqlite|\.pdf$"
```

**应当没有任何输出**。有输出说明版权文件被误纳入，需 `git rm --cached <文件>`。

---

## 六、目录速览

```
arch-tutor-rag/
├── demo.py                 一键演示（6 幕）
├── data/                   知识库与产物（建库后生成带原文的文件）
│   └── kb_meta.json        结构元数据（仓库自带，无正文）
├── scripts/
│   ├── 01_extract_pages.py 提取文本 + 检测章节  ← 需要 pymupdf
│   ├── 02_chunk.py         语义分块
│   ├── 03_build_kb.py      建 SQLite FTS5 库
│   ├── 04_verify_kb.py     验证知识库质量
│   ├── 05_export_meta.py   导出可公开的元数据
│   └── knowledge_search.py 检索工具
├── prompts/
│   └── system_prompt.txt   系统提示词（约束 R1~R6）
├── agents/
│   ├── arch_tutor_agent.py 智能体实现（完整 RAG 流程）
│   ├── agent.config.json   配置文件
│   └── README.md           启动说明
├── test/
│   └── run_smoke_test.py   合规性自动核查
├── docs/
│   ├── DESIGN.md           设计与实施文档
│   ├── DEMO_SCRIPT.md      课堂演示讲解稿
│   └── USAGE.md            本文件
└── deliverables/           测试报告 / PPT / 分工说明
```
