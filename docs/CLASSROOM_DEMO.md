# 课堂运行演示教程

> 面向：需要在课堂上现场运行 Arch-Tutor 并演示的人
> 配套：`python demo.py`、`docs/DEMO_SCRIPT.md`（讲解词）
> 本文所有命令、耗时、输出均经过实测

---

## 零、课前 10 分钟检查清单（务必做）

> **最快的做法：双击项目根目录下的 `check.bat`**，10 秒内出结果。
> 看到「自检通过，可以开始演示」就说明一切就绪，可以直接跳到第一节。
> 下面五步是它的详细版，用于排查具体问题。

### 检查 1：Python 能跑吗

```powershell
python --version
```

预期：`Python 3.12.x` 之类。

> 若提示「无法识别 python」，说明 Python 没装或没进 PATH。
> 备用方案见文末「应急预案」。

### 检查 2：知识库在吗

```powershell
cd "D:\deepseek工作区\arch-rag-kb"
Test-Path data\arch_kb.sqlite
```

预期：`True`

> **这是最关键的一项。** 若为 `False`，说明知识库没建，必须先跑建库
> （见文末「应急预案」）。

### 检查 3：演示脚本能跑通

```powershell
python demo.py --fast
```

预期：屏幕快速刷出 6 幕内容，最后显示 `总计 30/30 项通过（100%）`。

> ⚠️ **重要**：这条命令输出很长，如果终端显示不全没关系，
> 只要最后能看到 `30/30` 就说明一切正常。

### 检查 4：终端字体够大吗

投屏时建议字号 **16pt 以上**，否则后排看不清。

- Windows Terminal：`Ctrl + 加号` 放大
- 传统 cmd：标题栏右键 → 属性 → 字体

### 检查 5：终端窗口够宽吗

演示输出是 78 字符宽的排版。窗口太窄会折行错乱。

建议**最大化窗口**，或至少保证一行能放下 78 个字符。

---

## 一、演示前必知：输出太快的问题

这个系统的所有操作都在 **0.1 秒**内完成——检索 7~13 毫秒，整个 demo 也就 0.1 秒。

听起来很棒，但**课堂上是个问题**：144 行输出在一瞬间刷完，学生根本来不及看，你也没法边讲边指。

所以 `demo.py` 提供了几种节奏模式：

| 命令 | 耗时（实测） | 适用场景 |
|---|---|---|
| `python demo.py` | 约 7 秒 | 自己看效果、快速验证 |
| `python demo.py --slow` | 约 26 秒 | **课堂投屏首选**（每行 0.18 秒） |
| `python demo.py --slow 0.3` | 约 43 秒 | 讲得慢、要逐句解释时 |
| `python demo.py --fast` | 0.1 秒 | 课后自己快速自检 |
| `python demo.py --no-pause` | 0.1 秒 | 录屏（不停顿，后期自己配节奏） |

**建议课堂用 `python demo.py --slow`**，配合讲解正好。

---

## 二、完整演示流程（建议 8~10 分钟）

### 开场（30 秒）

先打开项目目录，让学生看到这是一套真实的工程：

```powershell
cd "D:\deepseek工作区\arch-rag-kb"
```

> 讲：「这是一个基于 RAG 的教材问答系统，用的是《计算机体系结构基础》
> 这本教材，430 页、12 章。」

### 第一段：一键跑完全流程（2 分钟）

```powershell
python demo.py --slow
```

输出会逐行浮现 6 幕。**不要催，让它跑**，你配合讲解：

- **第 1 幕**：12 章的块数和页码表 → 「每块都记录了教材页码」
- **第 2 幕**：3 个检索结果 → 「7~13 毫秒返回，每条带页码」
- **第 3 幕**：页码真实性核对 → 「引用不是模型编的，是从检索结果里来的」
- **第 4 幕**：诚实性验证 → **重点，下面单独讲**
- **第 5 幕**：R1~R6 总览 → 「30 项自动核查全过」
- **第 6 幕**：总结

### 第二段：重点讲第 4 幕（2 分钟）

到第 4 幕时按暂停（`Ctrl + C` 或等它跑完再单独重跑）：

```powershell
python demo.py --scene 4 --slow
```

屏幕上会显示：

```
  提问：量子纠缠在量子计算芯片中如何实现纠错？
  （教材完全未涉及）
    FTS 原始命中：0 条
    相关性闸门  ：拦截

    教材未找到相关内容。
    ...

  [OK] 如实回答「教材未找到相关内容」，未编造 [符合 R5]

  提问：请帮我写一份 Java 的冒泡排序代码。
  （超出教材范围）
    FTS 原始命中：5 条          ← 注意这里！
    相关性闸门  ：拦截
```

**这是全场最有说服力的一刻**，你要重点讲：

> 「看第二个例子：全文检索**确实命中了 5 条**——因为它抓到了『指令』『程序』
> 这些词。但这些都是无关内容。
>
> 如果我们直接把检索结果丢给大模型，它就会拿着这些无关材料，
> 一本正经地编出一个答案。这就是 RAG 系统最常见的翻车方式。
>
> 所以我们加了一道**相关性闸门**，判断检索结果跟问题到底相不相关。
> 不相关就老实说『教材没找到』。」

### 第三段：现场互动问答（2~3 分钟）

让学生现场提一个问题，你当场输入：

```powershell
python agents/arch_tutor_agent.py "学生提的问题" --offline
```

**建议引导**：让学生翻教材目录（`data/chapters.json` 里有 12 章），
从章节标题里挑问题，命中率最高。

准备好的安全问题（实测都能答）：

| 问题 | 会命中 |
|---|---|
| 直接相联和组相联有什么区别？ | 第 9 章 p.279-281 |
| 指令流水线的数据相关会带来什么冲突？ | 第 9 章 p.263-268 |
| TLB 地址翻译的过程是怎样的？ | 第 3 章 p.104-109 |
| CPI 和 CPU 时间怎么计算？ | 第 12 章 |

**如果学生故意问教材外的**（比如「量子计算」「怎么写 Python」），
正好借机再演示一次 R5：

```powershell
python agents/arch_tutor_agent.py "量子计算机怎么实现纠错？" --offline
```

### 第四段：展示合规性（1 分钟）

```powershell
python test/run_smoke_test.py
```

会打印 5 个用例 × 6 条约束的逐条判定，最后汇总：

```
  R1: 5/5 通过 (100%)  OK
  R2: 5/5 通过 (100%)  OK
  ...
  总体结果  : 全部通过
```

> 讲：「这不是我们说没问题，是程序逐条判定出来的。」

### 收尾（30 秒）

打开 `deliverables/` 目录，展示三份正式文档和两份 PPT。

---

## 三、演示脚本速查表

```powershell
# 完整演示
python demo.py                     # 约 7 秒，自测用
python demo.py --slow              # 约 26 秒，★课堂首选
python demo.py --slow 0.3          # 约 43 秒，讲得细时用
python demo.py --fast              # 0.1 秒，课前自检

# 单幕演示
python demo.py --scene 1 --slow    # 知识库概览
python demo.py --scene 4 --slow    # ★诚实性验证（最重要）
python demo.py --scene 5 --slow    # 合规性总览

# 直接问答
python agents/arch_tutor_agent.py "你的问题" --offline

# 单次检索（想看检索细节时用）
python scripts/knowledge_search.py "指令流水线" --topk 3

# 合规性测试
python test/run_smoke_test.py
```

---

## 四、常见问题与现场处理

### 现象 1：输出刷太快，看不清

用 `--slow`：

```powershell
python demo.py --slow 0.3
```

### 现象 2：显示 `[exit code: 1]` 但其实成功了

**这是个容易吓到自己的现象。** 如果你用类似下面的命令：

```powershell
python demo.py | Select-Object -First 10
```

PowerShell 在截断管道时会返回 exit code 1，**这不是程序出错**。

判断方法：看输出内容是否正常。内容对就是好的。

**课堂上建议直接 `python demo.py --slow`，不要加管道**，就不会有这个问题。

### 现象 3：中文显示成乱码 `锟斤拷`

先执行：

```powershell
chcp 65001
$env:PYTHONIOENCODING = "utf-8"
```

`demo.py` 已内置 UTF-8 设置，通常不会乱码；
`arch_tutor_agent.py` 若乱码，用上面两条命令。

### 现象 4：提示「未找到知识库 data/arch_kb.sqlite」

知识库不在。两种处理：

**方案 A：从备份恢复**（最快）

如果你提前把整个 `arch-rag-kb` 文件夹拷到了 U 盘，直接用它。

**方案 B：现场重建**（约 1 分钟，需要 PDF 和 pymupdf）

```powershell
python -m pip install pymupdf
python scripts/01_extract_pages.py "教材路径.pdf"
python scripts/02_chunk.py
python scripts/03_build_kb.py
```

### 现象 5：PPT 文件打不开

直接用 `deliverables/` 里的 `.pptx` 即可，与演示系统无关。
演示系统和 PPT 是两回事，PPT 打不开不影响跑系统。

---

## 五、应急预案（重要）

### 最坏情况：教室电脑什么都没装

**准备一个 U 盘 / 网盘备份**，里面放：

1. 整个 `arch-rag-kb` 文件夹（含 `data/arch_kb.sqlite`）
2. 便携版 Python（可选）

到教室后直接复制过去即可用。

### 更保险：录一段屏

提前用 `--no-pause` 录一次完整演示：

```powershell
python demo.py --slow 0.05 --no-pause
```

配合录屏软件（Windows 自带 `Win + G` 也可以），存成视频。
万一现场环境出问题，直接放视频。

### 最少依赖的演示路径

如果连 `python` 命令都没有，就只放 PPT（`系统展示.pptx`），
讲设计思路和截图数据。**PPT 里的数据都来自真实运行结果**，
照样能讲完整。

---

## 六、演示前自检脚本

项目根目录已提供 **`check.bat`**，课前**双击运行**即可完成全部检查：

```
==================================================
  Arch-Tutor 演示环境自检
==================================================

[1] Python 版本
    3.12.10

[2] 知识库
    OK  知识库存在 (4.0 MB)

[3] 关键文件
    OK  scripts/knowledge_search.py (检索工具)
    OK  agents/arch_tutor_agent.py (智能体)
    OK  test/run_smoke_test.py (合规性测试)
    OK  demo.py (一键演示)
    OK  prompts/system_prompt.txt (系统提示词)
    OK  data/chapters.json (章节数据)

[4] 演示脚本试运行
    OK  demo.py 可正常运行

==================================================
  自检通过，可以开始演示
  建议命令：python demo.py --slow
==================================================
```

若不方便双击，也可命令行运行：

```powershell
python scripts/precheck.py
```

**看到「自检通过，可以开始演示」就可以放心讲了。**

---

## 七、推荐的 10 分钟节奏

| 时间 | 内容 | 命令 |
|---|---|---|
| 0:00–0:30 | 开场，介绍项目 | `cd` 到目录 |
| 0:30–2:30 | 一键跑完 6 幕 | `python demo.py --slow` |
| 2:30–4:30 | **重点讲诚实性验证** | `python demo.py --scene 4 --slow` |
| 4:30–7:00 | 现场互动提问 | `python agents/arch_tutor_agent.py "..." --offline` |
| 7:00–8:00 | 合规性 30 项核查 | `python test/run_smoke_test.py` |
| 8:00–10:00 | 展示交付物、答疑 | 打开 `deliverables/` |

---

## 八、讲解词要点（配合 `docs/DEMO_SCRIPT.md`）

详细逐幕讲解词在 `docs/DEMO_SCRIPT.md`，这里只列最关键的三句：

**讲定位**
> 「这个系统只依据这一本教材回答问题，每句话都能翻书核对，教材没讲就明说没讲。」

**讲第 4 幕（最有说服力）**
> 「FTS 明明命中了 5 条，但系统还是说『没找到』——因为命中的都是无关内容。
> 这正是 RAG 最容易翻车的地方，我们用相关性闸门挡住了。」

**讲总结**
> 「这个系统的核心不是『能回答』，而是『守规矩』。
> 用工程手段把幻觉和版权两个风险按住了。」
