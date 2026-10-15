/**
 * Arch-Tutor · DSH 插件（知识库检索工具 + 系统提示词注入）
 * ---------------------------------------------------------------
 * 本插件把 Phase 1 构建的 SQLite FTS5 知识库接入 DSH 智能体：
 *   1. 注册 knowledge_search 工具 —— 智能体唯一的事实来源（R1）
 *   2. 注入五段式系统提示词 —— 约束 R1~R6 行为
 *   3. 通过 tools/pre-execute 钩子记录调用日志 —— 供 R1 合规性核查
 *
 * 依赖的 Host Service（均来自 DSH 官方契约）：
 *   ctx.tools.register(definition)        —— 注册工具
 *   ctx.systemPrompt.section(section)     —— 注入提示词段落
 *   ctx.on('tools/pre-execute', handler)  —— 工具调用前置钩子
 *
 * 安装方式见 agents/README.md
 */
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const PROJECT_ROOT = resolve(HERE, '..', '..')
const KB_PATH = join(PROJECT_ROOT, 'data', 'arch_kb.sqlite')
const PROMPT_PATH = join(PROJECT_ROOT, 'prompts', 'system_prompt.txt')
const SEARCH_PY = join(PROJECT_ROOT, 'scripts', 'knowledge_search.py')

/** 工具调用审计日志（内存态；同时可由宿主落盘） */
const callLog = []

/**
 * DSH 插件入口。DSH 以 `apply(ctx, config)` 形式加载插件。
 */
export function apply(ctx, config = {}) {
  const pythonPath = config.pythonPath ?? 'python'
  const topkDefault = config.topk ?? 5

  // ---------------------------------------------------------------- 启动自检
  if (!existsSync(KB_PATH)) {
    ctx.logger?.warn?.(
      `[arch-tutor] 未找到知识库 ${KB_PATH}，请先运行 scripts/03_build_kb.py`,
    )
  }

  // ---------------------------------------------------------------- 系统提示词
  // 五段式提示词注入到 system 段的靠前位置，确保约束先于其他上下文被模型读到。
  const promptText = existsSync(PROMPT_PATH)
    ? readFileSync(PROMPT_PATH, 'utf8')
    : '你是《计算机体系结构基础》课程助教，回答前必须先调用 knowledge_search。'

  ctx.systemPrompt.section({
    name: 'arch-tutor-rag',
    order: -100, // 负数=靠前，保证约束优先级
    content: () => promptText,
  })

  // ---------------------------------------------------------------- 检索工具
  ctx.tools.register({
    name: 'knowledge_search',
    description:
      '在《计算机体系结构基础》教材知识库中检索与问题相关的片段。' +
      '这是回答任何课程问题的**必需**第一步：禁止在没有检索结果的情况下作答。' +
      '返回内容包含片段正文、所属章节与页码（page_start/page_end），' +
      '用于生成【教材 p.XX】格式的引用。',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description:
            '检索关键词或问题。建议使用教材术语（如「指令流水线」「Cache 一致性协议」）。',
        },
        topk: {
          type: 'integer',
          description: `返回片段条数，默认 ${topkDefault}。`,
          minimum: 1,
          maximum: 10,
        },
        chapter: {
          type: 'string',
          description: '可选：限定在某章节内检索（章节标题关键词）。',
        },
      },
      required: ['query'],
      additionalProperties: false,
    },

    output: {
      schema: {
        type: 'object',
        properties: {
          hits: { type: 'array', items: { type: 'object' } },
          count: { type: 'integer' },
          formatted: { type: 'string' },
        },
        required: ['hits', 'count', 'formatted'],
        additionalProperties: false,
      },
      render(_args, value) {
        return [{ type: 'text', text: String(value?.formatted ?? '') }]
      },
    },

    async execute(args, exec) {
      const query = String(args?.query ?? '').trim()
      if (!query) {
        return { hits: [], count: 0, formatted: '错误：query 不能为空。' }
      }
      const topk = Math.min(Math.max(Number(args?.topk) || topkDefault, 1), 10)

      // 调用 Python 检索脚本（Phase 1 的知识库以 SQLite 形式存在，
      // Python 侧已完成 FTS5 + BM25 + 同义词扩展 + 二次排序）
      const cli = [SEARCH_PY, query, '--topk', String(topk), '--json']
      if (args?.chapter) cli.push('--chapter', String(args.chapter))

      const proc = spawnSync(pythonPath, cli, {
        encoding: 'utf8',
        timeout: 30_000,
        maxBuffer: 8 * 1024 * 1024,
        windowsHide: true,
      })

      if (proc.error || proc.status !== 0) {
        const msg =
          proc.error?.message ??
          (proc.stderr || '').toString().trim() ??
          `退出码 ${proc.status}`
        ctx.logger?.warn?.(`[arch-tutor] knowledge_search 失败: ${msg}`)
        return {
          hits: [],
          count: 0,
          formatted:
            '知识库检索失败：' + msg + '\n请如实告知用户当前无法检索，不要凭记忆作答。',
        }
      }

      let hits = []
      try {
        hits = JSON.parse(proc.stdout || '[]')
      } catch {
        hits = []
      }

      // ---- 审计日志：记录「检索先于回答」，供 R1 验证
      callLog.push({
        at: new Date().toISOString(),
        query,
        topk,
        chapter: args?.chapter ?? null,
        hits: hits.length,
        sessionId: exec?.agent?.id ?? null,
      })

      const formatted = hits.length
        ? hits
            .map(
              (h, i) =>
                `[${i + 1}] ${h.citation}  章节：${h.chapter}` +
                (h.section ? ` / ${h.section}` : '') +
                `\n${h.text}`,
            )
            .join('\n\n')
        : '检索结果：未在教材知识库中找到与该问题相关的内容。\n' +
          '请如实告知用户「教材未找到相关内容」，不要凭已有知识作答。'

      return { hits, count: hits.length, formatted }
    },

    isConcurrencySafe: () => true,
  })

  // ---------------------------------------------------------------- R1 强制
  // 通过 tools/pre-execute 钩子审计：当模型试图在未检索的情况下直接回答
  // 课程问题时，提示词约束已在 system 段生效；此处补充调用日志便于核查。
  ctx.on?.('tools/pre-execute', async (exec, next) => {
    if (exec?.name === 'knowledge_search') {
      ctx.logger?.info?.(
        `[arch-tutor] R1 检索调用: ${JSON.stringify(exec.arguments)}`,
      )
    }
    return next()
  })

  ctx.logger?.info?.(
    `[arch-tutor] 已加载：知识库=${KB_PATH}  topk默认=${topkDefault}`,
  )

  // 暴露日志查询，便于测试报告取证
  return {
    getCallLog: () => [...callLog],
  }
}
