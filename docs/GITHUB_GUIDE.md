# 上传到 GitHub —— 完整操作指南

> 面向本项目（arch-tutor-rag）。按顺序执行即可，每步都给出预期结果。

---

## 零、准备工作（只需一次）

### 0.1 确认 Git 已安装

```powershell
git --version
```

预期输出类似：`git version 2.55.0.windows.5`

若提示「无法识别」，说明 Git 未加入 PATH。**关闭并重新打开 PowerShell** 再试
（安装 Git 后需要重启终端才能刷新 PATH）。

### 0.2 配置提交者身份

提交记录会永久保留作者信息，建议使用 GitHub 账号绑定的邮箱：

```powershell
git config --global user.name "你的名字"
git config --global user.email "你的邮箱@example.com"
```

验证：

```powershell
git config --global user.name
git config --global user.email
```

> **提示**：若不想公开真实邮箱，可在 GitHub 的
> Settings → Emails 中勾选 "Keep my email addresses private"，
> 使用那里提供的 `xxxxx@users.noreply.github.com` 地址。

### 0.3 在 GitHub 上创建仓库

1. 登录 https://github.com
2. 右上角 **+** → **New repository**
3. 填写：
   - **Repository name**: `arch-tutor-rag`
   - **Description**: `基于 RAG 的《计算机体系结构基础》教材智能问答系统`
   - 选择 **Public**（公开）或 **Private**（私有）
   - ⚠️ **不要**勾选 "Add a README file"、"Add .gitignore"、"Choose a license"
     —— 本项目本地已有这些文件，勾选会导致冲突
4. 点击 **Create repository**
5. 记下页面显示的仓库地址，形如：
   `https://github.com/你的用户名/arch-tutor-rag.git`

---

## 一、本地提交

在项目目录下执行：

```powershell
cd "D:\deepseek工作区\arch-rag-kb"

# 确认待提交文件（应为 34 个，且不含教材原文）
git status --short
```

**关键检查**——确认以下文件**不在**列表中：

- ✗ `data/pages.jsonl`（教材逐页原文）
- ✗ `data/chunks.jsonl`（教材分块原文）
- ✗ `data/arch_kb.sqlite`（含教材全文的知识库）
- ✗ 任何 `.pdf` 文件

这些已由 `.gitignore` 排除。**若看到它们，请停止并检查 `.gitignore`。**

用一条命令验证：

```powershell
git ls-files --cached | Select-String "pages.jsonl|chunks.jsonl|arch_kb.sqlite|\.pdf$"
```

预期：**无任何输出**。有输出则说明版权文件被误纳入，需执行
`git rm --cached <文件名>` 移除。

### 提交

```powershell
git add -A
git commit -m "feat: Arch-Tutor 教材知识库智能问答系统

基于《计算机体系结构基础》(430页/12章) 构建 RAG 问答系统。

Phase 1 知识库:
- PDF 书签检测 12 章边界，提取 430 页
- 语义分块 277 块，97.5% 落在 800~1200 tokens
- SQLite FTS5(trigram) + BM25 全文检索
- 章节覆盖率 100%，检索 Top-3 准确率 90%

Phase 2 智能问答:
- knowledge_search 检索工具（同义词扩展 + 二次排序 + 相关性闸门）
- 五段式系统提示词，逐段对应 R1~R6
- 5 个测试用例、30 项自动核查全部通过

说明: 教材受版权保护，不随仓库分发。"
```

预期输出：`34 files changed, ...`

---

## 二、推送到 GitHub

### 2.1 关联远程仓库

```powershell
git remote add origin https://github.com/你的用户名/arch-tutor-rag.git
git remote -v
```

预期：
```
origin  https://github.com/你的用户名/arch-tutor-rag.git (fetch)
origin  https://github.com/你的用户名/arch-tutor-rag.git (push)
```

### 2.2 推送

```powershell
git push -u origin main
```

**首次推送会弹出登录窗口**，二选一：

**方式 A：浏览器登录（推荐，最简单）**
点击弹窗中的 "Sign in with your browser"，浏览器授权即可。

**方式 B：使用 Personal Access Token**
GitHub 已不支持密码推送。需先生成 Token：
1. GitHub → Settings → Developer settings → Personal access tokens
   → Tokens (classic) → Generate new token (classic)
2. 勾选 **repo** 权限，设置有效期
3. 复制生成的 Token（形如 `ghp_xxxxx`，只显示一次）
4. 推送时 **Username** 填 GitHub 用户名，**Password** 粘贴该 Token

> ⚠️ Token 等同密码，**不要**写入任何文件或分享给他人。

预期输出：
```
To https://github.com/你的用户名/arch-tutor-rag.git
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main'.
```

---

## 三、验证上传结果

打开 `https://github.com/你的用户名/arch-tutor-rag`，确认：

- [ ] 首页显示 README 内容（含「成果速览」表格）
- [ ] 文件列表中有 `scripts/`、`agents/`、`prompts/`、`test/`、`deliverables/`
- [ ] **`data/` 目录中没有** `pages.jsonl`、`chunks.jsonl`、`arch_kb.sqlite`
- [ ] `data/kb_meta.json` 存在（78 KB，仅结构元数据）
- [ ] 无 `.pdf` 文件

可选：在仓库页 **About** 处添加描述与 Topics：
`rag` `sqlite-fts5` `bm25` `chinese-nlp` `question-answering`

---

## 四、后续更新的常规流程

修改文件后：

```powershell
git status                    # 查看改动
git add -A
git commit -m "描述这次改了什么"
git push
```

---

## 五、常见问题

**Q1：`git push` 报 `remote origin already exists`**

说明已配置过远程地址，改用：
```powershell
git remote set-url origin https://github.com/你的用户名/arch-tutor-rag.git
```

**Q2：推送被拒绝（rejected / non-fast-forward）**

远程仓库有本地没有的提交（如创建时勾选了 README）。执行：
```powershell
git pull --rebase origin main
git push
```

**Q3：误把教材原文提交了怎么办**

```powershell
# 从 Git 中移除但保留本地文件
git rm --cached data/pages.jsonl data/chunks.jsonl data/arch_kb.sqlite
git commit -m "chore: 移除受版权保护的教材原文"
git push
```

⚠️ **注意**：这样只是在新提交中删除，**历史记录里仍然存在**。
若已推送，需用 `git filter-repo` 或 BFG 清理历史，或直接**删除整个仓库重建**。
预防远胜于补救 —— 提交前务必执行第一节的检查命令。

**Q4：中文文件名在 `git status` 中显示为转义码**

正常现象（Git 默认转义非 ASCII）。如需显示中文：
```powershell
git config --global core.quotepath false
```

**Q5：换行符警告 `LF will be replaced by CRLF`**

Windows 下的正常提示，不影响功能。如需消除警告：
```powershell
git config --global core.autocrlf true
```

**Q6：下载别人 clone 后运行不了**

因为仓库**不含教材原文**（版权原因），这是设计如此。使用者需：
1. 自行合法获取教材 PDF
2. 运行 `python scripts/01_extract_pages.py "教材.pdf"`
3. 依次运行 `02_chunk.py`、`03_build_kb.py`
4. 然后即可用 `demo.py` 演示

这一流程已写入 README，属正常的开源项目做法。
