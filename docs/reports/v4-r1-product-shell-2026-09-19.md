# V4.1 更新解读与 V4-R1 交付

## 更新判断与任务选择

本轮读取 `CODEX_REFACTOR_MASTER_PLAN_V4.1.md`，对照上一轮 V4 阅读记录与 R0 报告。旧 V4 文件原为未跟踪文件，现已被用户替换，因此这里是内容核对，不宣称有完整 Git 逐字 diff。

主要新增内容：

- 视觉资产正式链路：清单 → 单资产 Design/Contract → Prompt Spec → 编译快照 → Generation → Media Variants。
- Prompting 成为独立领域：仓库版本化 Blueprint/Preset、七层 AST、确定性 Compiler、不可变 compilation；设计事实、工作流状态、Findings 与 Prompt 分离。
- 三视图/表情/细节默认是同一输出图的 Sheet panels；不是默认拆成多次生成任务。
- 一个资产一个 HTML 工作页，结构化字段编辑后编译；不从旧 Markdown/HTML 反向猜字段。
- R3 扩展并拆成 A（Design/Manifest）、B（Prompting/Compiler/工作区）、C（Media）。批量 Skill 修订另行开展，真实 Provider 仍属 R8。

选择先执行 R1：它是已完成 R0 的直接后继，能呈现已有领域能力，也为视觉资产入口提供位置。直接跳到 Prompting 会跨越 R2 的 lifecycle/lineage 前置。Agent G 仍独立，不在本轮顺带实施。

## 已交付行为

项目进入、新建、切换都落到 `overview`。一级导航为概览/创作/剧集/资料；保留 graph、资产层级、agent 及会话深链，继续提供 Agent Dock。窄屏浮钮位于底部，避免顶栏遮挡。

概览可浏览当前项目真实系列，进入系列后浏览有序剧集，再通过 URL 深链进入剧集工作区。Scope Bar 显示项目/系列/剧集，制作流程默认折叠；刷新、返回、项目切换均保留正确范围。列表分页、空态、错误重试可用，前项目迟到响应不会写入新页面。

后端新增五个只读 GET 操作：Series 列表/详情、Episode 列表/详情、按 Episode 查询 Production 文档。列表参数有界，详情校验项目及系列归属；沿现有 service/repository 边界，不加表、不迁移。已导出 OpenAPI 并重新生成前端类型；`backend/openapi.json` 是 Git 忽略的本地生成产物，前端 schema 类型被跟踪。

切项目清理由 Workbench 承担，不再依赖 GraphView 恰好挂载：旧查看器、视角、选中、实体索引和 Agent 状态清理，全局参考资料缓存保留。

## 能力边界

R1 交付的是导航与浏览壳层。当前阶段展示已有规划草稿信息，并明确生产阶段尚未权威判定；下一动作是可用导航动作，阻断区说明尚未开放的编辑/放行能力。文档存在不等于批准。没有伪造 production gate、stale/review 总数或下一生产决策。

生产页面目前只读文档记录，不是正文编辑器；新建系列/剧集的 UI、视觉资产合同/Prompt 工作区、可播放时间轴、Director 和 Generation 均未实现。视觉入口明确标为待开放。未进入 R2/R3，未修订 Skill，未实施 Agent G/H。

## 验证

- 后端导航/Workflow/Production API：5 项通过；架构测试：15 项通过。
- Backend Ruff check/format、Workflow/Production mypy：通过。
- 前端新工作区/Projects/AssetLibrary/AgentHome：35 项通过；既有 Workbench 图谱：15 项通过。
- 独立 Playwright 验收：3 项通过，覆盖新建项目、实体、项目切换、删除测试项目、旧入口，以及真实 Series/Episode/Production 数据、刷新/返回、窄屏与项目隔离。
- TypeScript、修改文件 ESLint、Vite production build：通过。桌面与 390px 截图已人工检查，窄屏无横向溢出、Agent 按钮可见。
- `git diff --check` 通过。构建有 >500kB chunk 提示；既有图谱测试有未匹配图片请求的 MSW stderr；后端有 Starlette 弃用/pytest cache 权限提示，均未导致测试失败，未扩展到无关优化。

运行方式：backend 已有 `.venv/Scripts/python.exe` 调用 pytest/Ruff/mypy；frontend 直接 `node node_modules/...` 调用 tsc/eslint/vitest/Vite，因为当前 pnpm 会尝试自动重装 modules。未重装依赖。浏览器通过 `node node_modules/@playwright/test/cli.js test --config playwright.workspace.config.ts`，使用全新临时双库与独立端口 8017/5187，未使用全局 taskkill，未触碰开发库或调用模型。

## 停止点

R1 完成并停在下一阶段边界。Feature 验收状态未修改：本轮不把 F16 或 F21 的历史状态当成 V4 新能力验收。代码/文档尚未提交 Git，用户 V4.1 文件与上一轮 R0 成果保留。后续适合继续 R2 的 lifecycle/lineage 数据契约；需 Skill/聊天接入前仍应单独收口 G。
