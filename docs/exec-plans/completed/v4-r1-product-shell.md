# V4-R1 Frontend Product Shell

## Purpose and scope

用户于 2026-09-19 授权阅读 V4.1、选择最建议的下一项任务并直接实施。本任务选择 V4-R1：让项目默认进入概览，提供真实 Series/Episode 导航、Scope Bar、一级信息架构与 Production Rail 壳层。纳入 R0 已证实缺失的最小只读领域 API，不引入迁移。不实施 R2/R3、Prompting、Provider 或 Agent G/H。

基线 HEAD `764db247628153434f247548baf017c4856584e7`；已有用户未跟踪 `CODEX_REFACTOR_MASTER_PLAN_V4.1.md`，以及上一轮 R0 报告/归档和 Agent plan 事实修正，保留不动。旧 V4 文件已被用户替换，无法做逐字 Git diff；更新判断依据上一轮读取与 R0 报告。

权威来源：V4.1 §7.4–7.17、§38–44、§52、§69；AGENTS.md、docs/PLANS.md、ARCHITECTURE.md；creative-workflow 产品文档、workflow-core 与 projects-assets-and-workspace 设计。

## Progress

- [x] 2026-09-19 14:21–14:22 (+08:00) 阅读 V4.1 增量并选择 R1；新增 Prompting/资产流水线属于后续 R3，不改变 R1/R2 先行边界。
- [x] 2026-09-19 14:22–14:28 (+08:00) 补充带项目校验、分页的只读导航 API 与跨层测试；5 项 API、15 项架构测试通过，Ruff/mypy 通过。
- [x] 2026-09-19 14:28–14:41 (+08:00) 前端导航实现收口与验证（初始实现与上一切片交叠）：概览、Scope、折叠生产入口与旧深链兼容完成；前端集成共 50 项、隔离浏览器 3 项通过。
- [x] 完成于 2026-09-19 14:42 (+08:00) 更新设计/产品 owner、完成构建/静态验证与交付报告；文档更新与前一切片交叠，未另记起始时间。

## Surprises / Discoveries

- R0 的读 API 缺口仍在；不能用虚构数据满足 R1。
- 新增 V4.1 视觉资产入口放在创作/视觉下，R1 仅明确待开放，不创建 Prompting 数据。
- 现有全局 Playwright 配置会 taskkill 全部 uvicorn；本任务不用该启动方式，避免影响用户服务。
- 当前 pnpm 会先尝试自动重装 modules 并因无 TTY 拒绝；不重装依赖，改用 node 直接调用现有本地 CLI。新路由测试使用仓库既有 MemoryRouter 方式，避免 data-router 在 jsdom/MSW 下的 AbortSignal 类型冲突。
- 概览替代图谱成为默认入口后，共享状态清理必须由 Workbench 承担；已保留旧 Graph 行为并补充壳层 project change reset。
- 首次浏览器运行受沙箱权限限制，取消该测试后端口释放；获准提升权限后隔离测试通过，未使用全局 process kill。浏览器测试服务已随验收结束退出。
- `backend/openapi.json` 是 ignored 生成文件，前端 schema.d.ts 是跟踪产物；两者均已重新生成。

## Decision Log

- 使用已有 Workflow/Production service 边界提供只读列表与 scope 读取；不新增跨域巨型 overview 或持久状态表。
- 页面区分已有规划/文档记录与尚未接入的生产 Gate；不把 draft 或文档存在当成批准完成。
- URL 持有 project/series/episode scope；请求结果按 scope 失效，禁止前一项目的迟到数据污染。

## Validation and acceptance

后端定向 API 集成：真实数据库项目隔离、scope 不匹配、分页/排序/空态；前端路由集成：默认跳转、深链、系列剧集、返回/切项目、加载失败与旧 graph/assets/agent。运行相关 Ruff/mypy/架构检查、TypeScript/ESLint 与受影响测试。更新 OpenAPI/生成类型。必要时独立临时服务进行浏览器 smoke，不运行历史 full suite/mutation/benchmark 或真实模型。

实际完成：API 5、架构 15；前端 ProductionWorkspace/Projects/AssetLibrary/AgentHome 35、Workbench 15；独立 Playwright workspace/projects 3。Ruff/format、mypy、TypeScript、修改文件 ESLint、Vite build、git diff --check 通过。命令/警告/截图检查范围见交付报告。未变更 feature acceptance，无生产迁移；测试只在新建临时库运行既有迁移。

## Outcomes / Retrospective

R1 完成，见 [V4.1 解读与 R1 交付](../../reports/v4-r1-product-shell-2026-09-19.md)。新增 5 个只读操作、真实分页导航与生产浏览壳层；将默认入口变更后的项目状态清理责任放回 Workbench。Durable owner 已更新到 frontend-production-workspace/workflow-core 及项目、工作流 product specs。制作流程保持折叠，尚未实现能力不伪装成可用编辑器或权威 Gate。

## Recovery / restart point

本任务无未完成操作。代码/文档未提交 Git，用户 V4.1 与上一轮 R0 成果保留。当前只有 Agent 计划继续 Active，G/H 未被吸收。后续可在独立授权任务中进入 R2；本轮停止，不启动 Lineage/Prompting/Provider。临时数据库、构建和截图均不入库。
