# Agent 可靠运行、记忆与受控协作 ExecPlan

## Status / authorization

**Active，已获实施授权。** 用户于 2026-09-13 要求开始 Agent 改善任务，验收仅做必要测试，结束后交付面向技术新手的分模块分析报告。2026-09-12 17:46 (+08:00) 为原方案编写基线时间。计划不是 V3 的新阶段，不修改 V3 阶段顺序。R6 已记录遗留的修复另见 [已完成跟进](../completed/agent-baseline-followup.md)。

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
- 方案编写时工作区曾存在用户 R4–R6 未提交成果；2026-09-13 实施开始实际 `git status --short` 为空。以实际工作区为基线，不提交或清理用户工作。

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

每个切片完成后才进入依赖它的下一片；时间为实际观察值。

- [x] 2026-09-13 11:35–11:47 (+08:00) A / P0：建立权限与故障行为基线，定义运行状态和来源契约。20 项契约测试通过；6 项目标故障真实复现，仍为 strict xfail；2 项 UI 风险有明确静态证据。契约尚未接入运行链路。
- [x] 2026-09-13 12:12–17:17 (+08:00) B / P0：全链路视角隔离与模型请求硬预算、工具执行硬配额。用户明确要求仅继续 B，结束后交付详细分模块报告，完成后停在 C 边界。
- [x] 2026-09-14（完成于 12:30 +08:00）C / P0：原子批准、真实读取版本、幂等和并发冲突。业务效果与决定状态进入同一事务；pending/Skill 重放幂等；Entity、文档段和 Artifact 使用数据库条件更新保护旧基线；真实用户库完成增量升级并保全 435 行旧数据。
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

收口检查按用户 2026-09-13 最新要求，仅运行实际改动需要的 backend Ruff/format/mypy/import-linter、API schema 或 frontend 检查，以及参与边界的定向测试。全仓 `python scripts/task.py check` 仅在最终实际改动范围足够广而有必要时运行，不作为固定步骤。Feature status 只通过对应 `verify` 命令，先更新准确验收记录。实际命令与结果见 [A 故障基线](../../tests/agent-reliability-baseline.md)。

## Surprises / Discoveries

- 2026-09-13 A 阶段：当时唯一迁移 head 为 `f63c8db205a9`，模型注册包含 agent/artifacts/narrative_state/workflow/production/skills；本片无迁移。Alembic 命令需要在 backend 工作目录执行。
- 2026-09-13：临时库复现历史泄露、超窗仍调用、批量工具超额、摘要失败后遗漏、批准分次提交和 read/登记间新版被覆盖六项。后者由第二个真实 session 保存用户新版，不是 mock 版本推论。
- 2026-09-13：前端 pending 刷新和旧流 finally 风险保留静态证据；未进行 UI 动态复现、真正杀进程或同时 CAS 压测。A 不将这些推论包装成通过的稳定性保证。
- 现有摘要保留 cursor 不等于覆盖保持，后续尾窗仍可能丢上下文可见性。
- 2026-09-14 C 阶段：SQLite 的条件 `UPDATE ... WHERE version/status = expected` 配合 `rowcount` 可在数据库层选出唯一赢家；进程内先读后写检查不足以承担并发正确性。
- R6 Skill 是接收 candidate 的独立校验器，未接聊天；JSON Schema/权限/保护片段保证比设计概括窄。
- F15 仍未开始，不应把 memory_docs 表存在当作完整长期记忆实现。
- 当前 observer/日志 `checkpoint` 是观测装饰器，不是执行恢复 checkpoint。

- B：实际用户库停在 `a8f3c1d6e2b4`，早于代码迁移 head；审查完整升级链后，先备份和副本演练，再升级到 `b071c2d3e4f5`。原有 8 张表、435 行的全部旧列数据哈希一致，完整性和外键检查通过。历史 R6 迁移测试固定到其 R6 revision，避免新 head 改变历史测试范围。
- C：实际用户库从 `b071c2d3e4f5` 升级到 `c184d5e6f7a8`。升级前没有 positioning/style 指导文档重复；29 张既有业务表共 435 行的全部旧列哈希一致，完整性与外键检查通过。
- C：部分领域服务原先会自行提交。为保持公开 API 的独立事务习惯，同时允许 Agent/Skill 组成原子事务，新增 `commit=False` 参与模式，由最外层决定一次提交或回滚。
- C：Entity 的 `expected_version` 在公开更新 schema 中暂为可选，以兼容旧客户端；当前 Agent 与前端编辑器都会发送真实读取版本。缺少真实读取基线的 Agent 写入会直接拒绝。

## Decision Log

- 保留现有模块化单体；优先增强边界，暂不换 agent 框架。理由：主要风险是权限、事务与状态，不是循环语法。
- 摘要作为可重建派生视图，原文和领域事实保持权威；不以模型自述“已记住”作为验证。
- 自主长期维护默认只提议语义改变；接受仍由作者控制，索引等派生数据可自动重建。
- 原子事务通过公开参与式 service/UoW 实现，不绕过领域边界；旧公开 API 可继续承担独立事务。
- 2026-09-13 用户已授权实施；不自行修改 V3 master。遵照用户最新要求，验收采用最小充分测试，不把计划中的全仓 check 当作固定仪式。
- A 的运行终态与 pending 批准状态分开：回答和提案保存成功即 run completed，提案仍待作者决定。原因与来源传播设计已写入 agent-system.md。
- 故障基线采用 strict xfail 且仅捕获专用 UnmetAcceptance 异常；数据准备错误不能被当作预期失败。修复后移除对应标记，不改断言掩盖缺陷。

- B：旧消息默认归作者，作者摘要保留原字段；其他视角/角色使用独立摘要分区，避免猜测旧数据归属。
- B：预算采用保守 UTF-8 字节估算，覆盖消息、工具 schema、协议余量和输出预留，不引入 tokenizer 依赖；这不是供应商精确 token 保证。必需指导、摘要和未覆盖历史不静默删除，超限明确失败。
- B：工具续取保存为本轮作用域内快照；每次执行前检查配额，并统一限制调用次数、重复失败和时间。
- C：pending/candidate 先以条件状态迁移取得决定权，但过渡状态只存在于未提交事务中；业务效果、最终状态与可重放结果随后一次提交。失败会整体回滚，重试可安全重新取得 pending。
- C：读取工具把实际返回给模型的 Entity/文档段版本记录在本轮上下文中；写入从该记录取基线。数据库 CAS 再防止读取后的用户修改被旧申请覆盖。
- C：Artifact revision 既是内容历史，也是 Skill 候选的基线；接受候选前必须仍指向候选执行时的 revision。重复同一决定返回已保存结果，相反决定返回冲突。

## Outcomes / Retrospective

A、B、C 已完成；D–H 尚未实施，整体计划保持 Active。C 已把业务效果、pending/candidate 最终决定与稳定结果放入同一事务，并把实际读取版本贯穿到 Entity、文档段、Artifact 与 Skill。A 阶段的六项目标故障现在全部是普通通过的回归测试，没有保留 xfail。

C 定向验证合计 298 项后端通过、0 项 xfail，3 个前端文件共 22 项通过；Ruff check/format、55 个后端源文件 mypy、16 条 import-linter 规则、前端 TypeScript 和定向 ESLint 均通过。只运行参与边界所需测试，未跑全仓、mutation、benchmark 或真实模型，未修改 feature 状态。

面向技术新手的最新报告见 [C 阶段详细分析报告](../../reports/agent-improvement-slice-c-2026-09-14.md)，包含分模块目录、事务与 CAS 原理、选择原因、重难点、异常稳定性、数据库恢复文件与证据限制。[B 阶段报告](../../reports/agent-improvement-slice-b-2026-09-13.md) 和 [A 阶段报告](../../reports/agent-improvement-slice-a-2026-09-13.md) 保留为历史证据。

经验：边界必须检查真实请求和逐次工具执行，不能只限制循环次数；原文在数据库里不等于已进入模型。并发安全必须在数据库条件更新处裁决，应用层先查询只能改善提示，不能防止竞态。数据升级必须以实际数据库 revision 为起点验证，不能只验证代码最新一跳。

## Recovery / restart point

本次按用户要求完成 C 并停在 D 边界，不自动推进。用户后续要求继续时，从 D 的聊天 run 持久化、SSE 查询/回放、取消与刷新恢复开始；先读本计划 D、`agent-system.md` 的运行恢复部分，再定位 chat/API/store 及最近测试。不要重复读取完整历史审阅或重跑 A–C 的历史全仓基线。

C 已完成的验收与命令见 C 报告。实际数据库已升级到 `c184d5e6f7a8`，无待执行迁移操作，不要重复升级或自动 downgrade。升级前备份位于 `backend/data/backups/agent-c-20260914-122119-328323-before.db`，同前缀的 rehearsal 与 verification 文件记录副本演练、旧列哈希、行数及升级检查；恢复应另行评估升级后的新增数据，不直接覆盖现库。

A–C 修改均未提交 Git；未启动后台任务，未调用真实计费模型，C 未修改实际 `.env`。整体计划不归档、不标为完成。D–H 必须按后续用户请求逐阶段推进并更新报告。
