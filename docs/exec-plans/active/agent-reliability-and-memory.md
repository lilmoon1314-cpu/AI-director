# Agent 可靠运行、记忆与受控协作 ExecPlan

## Status / authorization

**Proposed，尚未执行。** 用户本轮只要求创建本计划。2026-09-12 17:46 (+08:00) 完成方案编写阶段的基线整理；下列实施里程碑没有开始时间，不能标记为完成。计划不是 V3 的新阶段，不修改 V3 阶段顺序。R6 已记录遗留的修复另见 [已完成跟进](../completed/agent-baseline-followup.md)。

## Purpose and scope

让项目创作 Agent 在长对话、跨会话、视角切换、并发修改、工具失败和服务中断后仍做到：不越权，不静默丢失关键状态，不重复或覆盖用户写入，能解释来源、恢复工作，并能量化质量和成本。

基线是 [当前工程审阅](../../design-docs/agent-engineering-assessment-2026-09-12.md)，其中列出的未实现能力不是现有产品承诺。本计划覆盖 agent 与参与的 perspectives/artifacts/skills/workflow/production 服务接口及前端交互；保留 FastAPI + SQLite 模块化单体。仅在证据表明必要时才增加基础设施。

目标不承诺自然语言摘要绝对无损，而承诺关键约束有原始证据、摘要覆盖可检验、丢失可检测并有恢复路径。写入仍需作者显式批准；自主维护仅允许产生候选或更新可重建的派生数据。

明确排除：自动发布作品、未经批准修改世界事实或用户偏好、默认跨项目召回、全局 agent 权限扩张、多 agent 编排、向量数据库迁移、多人 SaaS 改造、重写整个前端。作品正文由 Artifact/Production 持有，长期记忆只引用，不复制另一份权威正文。

## Authoritative owners and baseline

- 先读 `AGENTS.md`、`docs/PLANS.md`，然后按切片读必要 owner。
- `docs/product-specs/agent-assistance.md`、`docs/design-docs/agent-system.md`：运行、记忆与确认行为。
- `ARCHITECTURE.md`、`docs/design-docs/platform-boundaries.md`：服务边界和事务所有权。
- 权限切片再读 `docs/design-docs/world-model-and-perspectives.md` / `narrative-state-core.md` 的相关部分。
- Skill/单块编辑切片再读 `atomic-skills.md`、`production-documents.md` 及对应 product spec。
- Feature 只按 ID 查询 F10/F13/F14/F15/F21；F15 基线 `not_started`，现有测试不足以证明未来长期记忆功能。
- R6 跟进后基线：432 个后端测试通过；mypy 87 文件、Ruff、16 import contracts 通过。既有 Starlette 弃用警告不混入此计划默认范围。
- 工作区存在用户 R4–R6 未提交成果；开始实施先记录 status，不提交或清理用户工作。不要以 Git HEAD 代替实际工作区基线。

## Invariants

1. 所有进入模型的图谱、历史、摘要、记忆、工具结果、缓存均携带 scope/provenance，并经过同一可见性边界。
2. 每次 provider 请求，包括重试、摘要和工具后的补全，都执行统一预算检查；不可满足时显式失败，不静默扔掉强制约束。
3. 工具实际执行次数不得超过预算；只读重试有界，写入结果未知时先查询状态。
4. 业务写入与 pending/candidate 决定原子一致；同一个操作最多产生一次业务效果。
5. 修改绑定模型实际读取的版本；用户后续修改不得被旧候选覆盖。
6. 摘要游标推进有覆盖证据；强制决策、否定约束、未决任务和精确标识可回溯原文。
7. 新会话不自动继承无权限或无来源的内容；删除/遗忘可解释其派生影响。
8. UI 的“完成、已写入、已取消”以服务器持久状态为准，不由连接结束或模型措辞决定。
9. 观测区分全部模型调用与最后一次调用、缓存命中与未知；日志不记录凭据，reasoning 不作为事实/记忆来源。

## Progress

以下均为待实施事项。实施开始时获取真实时间并按 PLANS.md 标注起止时间；每个切片完成后才进入依赖它的下一片。

- [ ] A / P0：建立权限与故障行为基线，定义运行状态和来源契约。
- [ ] B / P0：全链路视角隔离与模型请求硬预算、工具执行硬配额。
- [ ] C / P0：原子批准、真实读取版本、幂等和并发冲突。
- [ ] D / P1：持久运行、可恢复流与摘要维护解耦。
- [ ] E / P1：可追溯摘要、关键状态覆盖与原文恢复。
- [ ] F / P1：有来源的长期记忆、跨会话召回、冲突与遗忘。
- [ ] G / P1：受控单块编辑、Skill 强校验与聊天适配。
- [ ] H / P2：检索/缓存/成本优化及故障验收收口。

依赖顺序：A → B → C → D → E → F → G → H。每一片独立交付可观察结果；若用户只授权其中一片，完成后停在该片边界。

## A. 行为基线与契约

定位 `agent/chat.py/context.py/prompts.py/writes.py/documents.py/models.py` 与 `frontend/src/stores/agentStore.ts`。先用无网络 fake provider 和临时数据库构造当前缺陷的可重复证据，不对真实项目注入故障。

基线场景：author 秘密在同会话切 audience；超窗摘要失败；8000 字符中文输入叠加工具 schema；单次响应返回超额调用；用户在 read 与 write 登记之间修改；批准业务提交后状态提交前崩溃；刷新后 pending 回读；切项目后旧流 finally 到达。

定义最小结构：Run/事件序号、SourceRef（project/perspective/character/message or revision/version）、ContextManifest（片段、原因、token 估算、权限、裁剪）、ToolResult（ok/error/retryability/truncated/continuation）、SummaryCoverage。优先作为内部类型，确有持久恢复需求才落表。不要制造可自由跳过的 hook 开关。

验收：每个风险有最小失败用例或明确静态证据，记录预期错误语义；不可复现的并发推论保持“待验证”，不通过修改断言掩盖。给出状态迁移与来源传播设计，移入对应设计 owner。

## B. 权限、预算和工具配额

对会话历史/摘要定义视角处理：推荐以项目+视角+角色作为上下文分区。旧的无视角数据仅 author 可用，窄视角不能猜测其安全性。全量旧数据保留，用户可明确开启新分区。记忆和检索同样有 scope；模型可见错误也不得泄露隐藏名称。

拆分纯规则 system 与不可信项目数据，统一包裹标题/目录/项目名等插槽。wrapper 不作为唯一防线；真正授权在读取边界完成。模型无权覆盖服务端 project/perspective。

实现每次调用统一预算器：计算 system、检索、历史、工具契约、协议开销和输出预留；支持模型 tokenizer/保守 fallback，不能声称 fallback 是精确值。先删除低相关可恢复数据，再压缩有证据的历史；关键约束预留预算。目录分页，工具结果有 continuation，保留工具消息配对。

逐个工具执行前检查计数；超额 tool_call 必须收到明确未执行结果以维持协议一致，不执行副作用。整轮次数/deadline、工具超时、重复失败上限进入 config 与 example env。Provider 不遵守禁用工具或缺少正常结果时明确结束。

验收：跨视角及跨项目 secrets 零泄漏（历史/摘要/文档/错误/缓存入口）；超硬预算调用次数为 0；超额批量只执行允许数量；临界中文/emoji/大 schema/循环追加场景不过限；拒绝原因在 UI 可见。不要运行真实模型计费来测试边界。

## C. 写入原子性、版本与幂等

保留跨域 service 边界；增加明确参与调用方事务的 service 操作或 UoW，禁止 Agent 直接 import 其他领域 repository。业务效果、操作幂等记录、pending/candidate 状态在同一主库事务提交。保持每项独立成功/失败的现有 UX，可用每项事务实现，避免把整批改为全成功才提交。

数据库条件更新实现 version CAS，并用 rowcount 判断冲突；段更新与文档版本增长原子执行。read 工具返回版本；写入要求实际 read version，缺少基线拒绝并要求重读。实体/Artifact 也定义相应版本前置条件；Skill candidate 保存 base revision。

pending 决定使用条件状态迁移/唯一幂等键；重复请求返回已完成的同一结果。拒绝和批准竞争只能成功一个。当前领域内部 commit 不得绕过外层恢复保证。唯一指导文档等约束在清查存量重复后再加数据库约束；不可自动删重复数据。

验收：双连接并发同版本写仅一个成功，其余明确 conflict；read 后用户改再登记拒绝；业务提交边界故障不产生 pending 与效果不一致；同 key 重试/重放/双 approve 不重复创建；一项失败不污染后一项 session；R6 candidate accept 同样成立。

## D. 持久运行、流式恢复与资源

复用 Workflow 的审计能力时先确认其“创作流程 run”与“聊天轮 run”的语义是否相同；必要时建小的 AgentRun 并引用 workflow_run，不强迫混用。持久状态必须有唯一轮次 ID、请求幂等键、事件序号和最终消息/错误/取消结果。

用户输入保存后开始 run；回答与 pending 提交后再异步/独立触发摘要维护。摘要故障不得回滚成功回答。缩短持锁事务，工具/网络等待不能占用不必要写锁。服务器对同会话并发明确串行或 conflict；跨会话不依赖单浏览器锁实现后端正确性。

SSE 事件带 run ID/序号，客户端发现 EOF 无 done 时查询运行状态；明确重连/回放策略与保留期限。刷新先回读 pending。store 异步结果检查 project generation 和 run ID，旧请求不能清空新流。停止有服务端取消状态；已提交操作返回真实结果，不能伪称撤销。

显式关闭 provider stream；shutdown 各资源独立 finally 清理，保留关闭错误日志。客户端归属应用 lifespan；不要共享跨 loop 的活动连接池。重试/限流分类与总预算一并管理。

验收：刷新/关闭 dock/切会话不丢 pending；断网后能查 completed/failed；取消释放连接与数据库事务；多标签并发不交错摘要；旧流收尾不影响新项目。崩溃重启有确定 restart point，不自动重放未确认写入。

## E. 摘要、关键状态和恢复

保留原始 messages，新增摘要版本与 covered message range/source IDs、生成模型/策略版本、覆盖校验结果和失败状态。结构化提取关键约束、决策、未决任务、精确引用；对可机器验证项逐条验证来源存在、范围完整、精确值未改。自然语言的语义保持仍需质量评估，第二模型审核不能被当数学保证。

摘要输入输出分别限额，批次有界。失败保留旧版，不推进游标；未覆盖的关键消息从原文有界回补，并把未覆盖范围显式留给恢复机制。cursor 损坏告警，支持按源消息重建；不要只使用 `tail[-window:]` 静默忽略缺口。

原文工具支持按来源 ID/时间范围读取，严格 scope 与分页。提供用户可见“本轮用了哪些记忆/省略了哪些可恢复材料”视图。压缩和重建是幂等任务，可中断后继续，不重写原文。

验收语料：否定/数值/人名/长程约束/撤销决定/用户未答问题/工具失败；多次连续压缩后所有人工标记关键项仍可定位原文。空摘要、错误摘要、provider 超时、超长积压、缺失 cursor 都有显式恢复，不丢回答。测试把“原文存在”和“本轮确实可召回”分开断言。

## F. 长期记忆、跨会话、冲突与删除

在项目记忆层引入最小候选/来源/状态模型，避免复制世界事实。状态至少支持 proposed/accepted/superseded/disputed/deleted；每项带 scope、source refs、版本与适用时间，明示作者决定和模型建议的差别。

默认自动提取候选、去重建议和可重建索引；接受/语义替换由用户确认。全局偏好默认不从角色台词或临时创作假设推断，用户可查看编辑删除。跨会话搜索基于已授权来源，目录/全文索引先行，向量后置为有证据收益的可选决策。

冲突不得默认 last-write-wins：同一对象/范围的矛盾标 disputed，提供来源与替代候选；领域事实仍从领域 service 读取最新 revision。用户撤销决定后，旧摘要/缓存必须不再作为有效指导。

定义两种删除：删会话本身（保留独立已接受作品/项目指导）；显式遗忘派生记忆（预览依赖，多来源不盲删）。建立 tombstone/索引失效与缓存失效机制，隐私删除不能被后台维护重新提取恢复。

验收：新会话能召回已接受决定及来源；未接受建议不变成事实；跨项目/视角和角色台词不污染用户偏好；冲突并列可解释；删源后的派生内容遵循选择且重建不会复活已遗忘项。F15 只有满足新的明确验收后才经 task.py verify 更新，不能沿用旧测试宣称全部完成。

## G. 单块编辑与 Atomic Skill 受控协作

先强化 registry/schema：使用真正支持所选 schema 语义的校验器或明确拒绝不支持关键字；不接受未知 context 类别；服务端按引用加载可见内容，gate 从权威域事实计算，不能信任入参 gate_facts。选择性 gate 与必需 gate 在契约中区分。

protected spans 从服务器保存的原文/锚点中验证候选正文；facts 校验明确能证明的结构化字段，无法机器断言的语义变更展示风险和 diff。manifest 声明与实际 adapter 效果一致，prompt/validator 文件加载行为须明确，避免只有文件存在的假保证。

编辑意图带目标 block/section、base revision/version、选区和允许变化范围；生成候选后先校验 diff，再展示确认卡，接受时再检查当前权限、gate、版本与保护区。非选区保持与旧版相同。用户只想改一句时不得退回全文重写。

为聊天加入受控 skill 适配器和必要 Artifact/Production/Narrative-state 读取工具；不允许任意 skill 调用另一个 skill 或自动推进 workflow。统一显示 pending/candidate 但保留各领域状态权威，禁止两套确认各自重复写。

验收：只改指定 block/选区，未选内容字节/结构不变；stale candidate 拒绝；伪造 facts/protected 字段不能绕过正文检查；多余 context/越权引用/过期 gate 拒绝；真实聊天→候选→diff→批准→revision 一条跨层测试通过。

## H. 检索、缓存、成本与收口

图谱先限量名称/别名检索和有界邻域，重名明确歧义；memory 批量查 section、游标分页、避免每轮全量历史/全图加载。按查询与来源做去重、相关性排序。仅在评估表明关键词方案不足时单独决定混合/向量索引。

记录 run 下全部调用（main/summary/repair/retry）的 input/output/cached token、模型、时延、是否未知和成本估算版本；默认不记录敏感正文。规则与契约稳定排序，缓存键包含项目/视角/角色/内容与策略版本。先给出命中与召回基线，再优化摘要频率和模型路由，质量不得低于基线。

验收按固定中文语料比较有效来源召回、关键约束保留、错误写入率、总 token、数据库查询量、首 token/整轮延迟；cached usage 缺失显示 unknown，不显示 0。任何优化必须保留 B–G 的安全回归通过。只在最终跨域收口运行一次 full check，不为每个小改动全仓扫描。

## Validation and acceptance

优先运行最近单元/双连接集成测试，跨层时运行对应后端 API 与前端 store/integration 测试。测试使用临时数据库和脚本化 provider；默认阻止真实网络。真实模型质量评估若需要计费，另行明确模型/预算/样本，不读取生产密钥做隐式试验。

迁移严格 additive：开始先检查当前 head 与所有模型注册，生成后审查每条操作；有存量重复时输出冲突清单而非清理。以填充了会话、summary cursor、记忆段、pending、Artifact revision、Skill candidate 的数据库副本演练 upgrade。证明行数、来源关系、原文与版本不变；保留恢复副本。不要对用户真实库自动降级或回滚删除新表。

收口检查：backend Ruff/format/mypy/import-linter，必要 API schema 生成及 frontend typecheck/lint/build，Agent 与参与领域测试，新增故障矩阵；最后 `python scripts/task.py check`。Feature status 只通过对应 `verify` 命令，先更新准确验收记录。测试名和命令在实现后记录实际值，不预造通过数。

## Surprises / Discoveries

- 现有摘要保留 cursor 不等于覆盖保持，后续尾窗仍可能丢上下文可见性。
- “版本 CAS”和“确认写入”已有顺序场景保护，但数据库并发条件更新和原子决定尚缺。
- R6 Skill 是接收 candidate 的独立校验器，未接聊天；JSON Schema/权限/保护片段保证比设计概括窄。
- F15 仍未开始，不应把 memory_docs 表存在当作完整长期记忆实现。
- 当前 observer/日志 `checkpoint` 是观测装饰器，不是执行恢复 checkpoint。

## Decision Log

- 保留现有模块化单体；优先增强边界，暂不换 agent 框架。理由：主要风险是权限、事务与状态，不是循环语法。
- 摘要作为可重建派生视图，原文和领域事实保持权威；不以模型自述“已记住”作为验证。
- 自主长期维护默认只提议语义改变；接受仍由作者控制，索引等派生数据可自动重建。
- 原子事务通过公开参与式 service/UoW 实现，不绕过领域边界；旧公开 API 可继续承担独立事务。
- 不把本计划算作已授权实施，也不自行修改 V3 master。

## Outcomes / Retrospective

待实施。当前交付仅为问题分析与本计划，未部署任何建议能力。

## Recovery / restart point

下一会话收到实施授权后，先读取本计划与工程审阅，获取实际时间、`git status --short` 和迁移 head，核对工作区是否仍为 432-test 基线。然后从 A 的最小失败场景和契约开始；不要从向量库/框架替换或直接执行全部迁移开始。

本轮无迁移、后台任务或未完成数据操作。若没有新的实施授权，保持 Proposed；不要把计划文字当作可执行命令运行。
