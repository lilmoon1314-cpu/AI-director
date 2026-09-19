# V4-R0 Baseline Reconciliation

核对日期：2026-09-19（+08:00）。范围仅为 V4 §69、§80、§83；未实现功能、未迁移数据库、未开始 R1/R2 或 Agent G/H。本文记录该时点的仓库事实，不替代 master plan 或长期设计 owner。

## 1. 基线与验证证据

| 核对项 | 本次观察 |
|---|---|
| Git | `main`，HEAD `764db247628153434f247548baf017c4856584e7`，提交标题 `agent长期记忆优化`；与 V4 §0.2 相同 |
| 初始工作区 | `git status --short` 仅 `?? CODEX_REFACTOR_MASTER_PLAN_V4.md`；V4 尚未被 Git 跟踪，不能描述为已入库方案 |
| 初始 active plans | 仅 `docs/exec-plans/active/agent-reliability-and-memory.md`；A–F 完成，G/H 未完成 |
| 迁移图 | Alembic ScriptDirectory 读取 15 个 revision，唯一 head `f4b7c8d9e0a1`，前驱 `e3a6f7b8c9d0` |
| 本地数据库 | 从应用配置解析主库路径，SQLite URI `mode=ro` 查询 `backend/data/app.db`：`alembic_version=f4b7c8d9e0a1`，36 张表；没有待补跑的迁移版本 |
| ORM 注册 | `backend/migrations/env.py` 已注册 agent/artifacts/entities/narrative_state/projects/production/relations/skills/workflow；assets 使用独立 Base/库 |
| API/schema | 内存生成 `app.openapi()` 与 `backend/openapi.json` JSON 完全相等：73 个 path、100 个 component schema |
| 前端类型 | 73 个 OpenAPI path 都出现在 `frontend/src/api/schema.d.ts`；这是路径覆盖检查，未重新生成并逐字验证所有 TS 类型 |
| Feature | 20 条记录：19 passing、1 not_started；唯一 not_started 为 F16「多系列剧情线」 |

F10/F11/F13/F14/F15 与 F17 Artifact、F18 Narrative State、F19 Workflow、F20 Production、F21 Skills 均记录 passing。这里是读取历史验收状态，并非本次重新验收。F19 的 Series/Episode 模型存在不等于 F16 产品能力已完成；F21 passing 也不等于 Agent G 已完成。未修改 `feature_list.json`。

读取迁移图与库状态使用 backend 已有 `.venv/Scripts/python.exe`；没有调用 upgrade/downgrade/autogenerate，也未读取项目正文。OpenAPI 比对时仅在进程内 mock `observability.setup`，避免初始化日志文件；不进入应用 lifespan、不连接 provider、不启动服务。revision 相等不等于逐列数据库漂移检查，本次不宣称已完成 schema/data 完整性验收。

## 2. Still true：V4 的现状判断仍成立

| V4 判断 | 当前代码证据与实际边界 |
|---|---|
| 模块化单体、双 SQLite、service 边界 | `ARCHITECTURE.md`、`backend/app/main.py` 路由组合、`config.py` 主库/资产库配置；无需从零重建 V3 领域 |
| Artifact 版本、稳定 block、局部 diff、并发保护 | `artifacts/models.py` 的四类 identity/revision 表及 dependency；`service.py:245–338` 的版本检查、CAS、快照和局部 stale |
| Narrative State 有账本和补偿引用 | `narrative_state/models.py` 六类模型与 `compensates_event_id`；`service.py` 验证补偿事件存在及项目归属，追加事件而非改历史 |
| Workflow 底座存在 | `workflow/models.py` 的 RequirementSpec、Series、Episode、ScenePlan、Gate、ExecutionRun/Step 已存在；Gate 权威性限制见下节 |
| Production 是固定线性链 | `production/service.py:16` 的六项 `DOCUMENT_ORDER`，要求上一个文档类型；timeline semantic 仍为 `track_type/source_ref/start/duration` |
| Skill 有候选与确认边界 | `skills/service.py` 和 `registry.py` 已实现 pending/accept/reject、base revision 与三种固定 commit action；不是可扩展的领域 adapter registry |
| Episode/ScenePlan 不是 Artifact 正文血缘 | `workflow/models.py` 保持结构行与 outline 等字段，没有 planning artifact/revision binding |
| 参考图片与生产媒体应分开 | `assets/models.py` 使用独立 AssetsBase、AssetImage；配置只允许图片类型；没有独立生产 Media Registry |
| 前端仍是图谱工作台 | `App.tsx:29` 默认 graph；`Workbench.tsx:28` 导航为 graph/assets/agent；资产子路由和 `agent/s/:sessionId` 深链已存在 |
| V4 新领域尚未落地 | 当前 app 目录、路由、模型注册及迁移图均无 Lineage/Change Proposal、Creative Design、Timeline Core、Director Previz、Generation 领域；前端也没有对应主路由 |

V4 §2 的十项主要缺口仍成立。不存在“代码已经提前完成 R1/R2、只需更新状态”的证据。

## 3. Already changed：需要纠正的旧事实

1. **Agent active plan 的未提交叙述失效。** HEAD 与 V4 基线本身没有变化，但 A–F 已包含在当前 Git 历史；`git log` 可见 F 提交 `764db24`、D 提交 `ae155be`、A/B/C 提交 `260b7ae` 等。已只修正 Agent plan 的 Recovery 末段，保留其 Active 状态和 G/H 边界。
2. **F15 当前是 passing。** Agent plan 的 authoritative baseline 中 `not_started` 是方案编写时基线，不是当前状态；F Progress/Outcomes 已正确记为 passing，故不重写历史段落。
3. **远端状态不在本次证明范围。** 本次核对的是本地 `main` 和实际 HEAD；未 fetch，不将 V4 §83 的“当前远端”措辞当作刚刚验证过的远端事实。

## 4. Conflicts / qualifications：方案中需要收紧的前提

### C1. R1 不能仅靠已有 API 拼出完整真实导航

`workflow/router.py` 的 series/episodes/scene-plans 仅 POST，没有 GET 列表或详情入口；现有读取只包含 current requirement。`production/router.py` 仅创建及按 ID 读取，无按 episode 列表。Artifact 也缺项目级列表/影响汇总入口。OpenAPI 与路由源码一致，不是 schema 过期。

因此“后端 R4–R6 已有”准确，但不等于“R1 所需读取契约齐全”。Series/Episode selector、当前阶段/下一动作/阻断、stale/review 总数缺少完整的可发现数据链。下一阶段应明确最小只读 API 补齐范围，或用真实的 unavailable/blocked 状态，不能构造假进度、假 Gate 或 mock API 冒充已实现能力。

此外 `ProjectPicker.tsx:116,143` 和 `ProjectSwitcher.tsx:40` 直接导航 `/graph`。R1 仅修改 App index redirect 不足以改变用户默认落点，必须同时覆盖打开、新建、切换项目这三个入口。

### C2. “确定性 Gate”不等于“服务端权威 Gate”

`workflow/service.py:evaluate_gate` 的规则比较由代码执行，但比较的是请求 `schema.facts`；`skills/service.py:131` 仍传入 `payload.gate_facts`。不能把这条链路当作已经从真实领域状态计算的生产放行依据。这与 V4 §71 要先收口 G 一致，是对 §1.4/§1.6 的必要限定。

### C3. 现有 stale 是 block 局部标记，不是 V4 的通用 revision-aware 影响引擎

`artifacts/repository.py:80–89` 按 changed block IDs 和 `is_stale=False` 选边，没有按旧 source revision 过滤；`artifacts/service.py:324–333` 直接标记这些依赖及 dependent artifact。source revision 被保存，但当前 stale 查询不使用它做 compatibility/rebase 判断，也没有跨域递归影响引擎。因此可继承稳定 ID/历史快照和局部失效能力，不能把 V4 §74.1 的精确 revision/policy 验收视为现成通过。

### C4. lifecycle 迁移不可把 stale 翻译成审批状态

当前 Artifact 只有 `status`（默认 draft，依赖变化时 stale）、current revision 和依赖 `is_stale`，没有审批历史。R2 应把旧 freshness 与 approval 分开；不能推断旧 stale 表示曾批准，也不能声称旧库已有结构化 stale cause/event audit。能从边和 revision 确认的来源保留，无法恢复的历史原因需明确 unknown/legacy。

以上为现状差异或前提限定，本次不修复、不扩展为新的功能任务。

## 5. Active Agent G/H 的实际状态

**G 尚未完成，且存在直接源码证据：**

- `skills/service.py:23–47` 只做 required 和顶层基础类型检查，没有完整递归 JSON Schema 语义或不支持关键字的 fail-closed 校验。
- `_validate_contract` 检查 required/denied context 键，没有将所有未知类别拒绝，也没有按引用加载权威可见内容。
- `facts_preserved` 和 `protected_spans_unchanged` 比较调用方 input/candidate 的声明字段，未从服务端原文锚点验证实际候选正文。
- registry 检查 `prompt.md`、`validators.py` 文件存在，但其执行路径读取 manifest/schema；不能把文件存在当作 prompt/validator 已执行的证明。
- `agent/tools.py:707` 工具映射没有聊天→Skill 调用适配器或 Artifact/Production/Narrative State 专用读取工具。
- 现有 C 阶段的 candidate 原子批准、版本冲突保护已存在，后续 G 应复用，不能回退为从零实现候选。

**H 尚未收口，但并非检索和预算完全为空：**

- 已有 `search_entities`、有界目录/工具续读、budget 和 F 的来源/分区召回；保留这些能力。
- `agent/chat.py:145,168,292,322` 仍用 `final_usage` 更新消息/返回 usage；`llm.py:_record_usage` 已有逐调用日志，但没有 H 要求的 run 全调用成本账本及 cached-token/成本版本契约。
- 本次未跑固定语料召回、成本、时延或最终故障矩阵；不为 H 补验收，也不新调用计费模型。

Agent plan 已记录 F14 同时间戳 pending 顺序断言在完整组中偶发失败、独立重跑通过。这里只保留“历史已记录未处理”的事实，不声称本次复现或修复；也不据此改写 feature 历史 passing。

## 6. Migration facts：后续实施必须携带

1. 后续主库增量迁移从真实 head `f4b7c8d9e0a1` 开始，而非 V3 R6 head；必须重新读取实施当天状态。当前版本一致，无需 R0 补迁移。
2. 保留 Artifact/Block/Revision IDs、完整旧快照、source revision、dependency ID/类型、既有 stale 标记及项目归属。Lineage 映射必须明确 block 粒度与 baseline revision 的对应方式，避免只记录 artifact ID 导致失去局部性。
3. 旧 status 没有 approval 历史；freshness/cause 的可恢复程度应由存量边和 revision 证据决定，不能伪造批准或失效事件。
4. 当前 timeline 是 Production Artifact；未来 R4 importer 保留旧 revision，R0/R1/R2 不提前迁移为 Timeline Core。
5. `assets.db` 与 `data/assets` 保持原状，未来 Media 是新域；不搬库，不扩 AssetImage 为万能媒体。
6. Episode/ScenePlan 正文版本化留给单独 Planning Artifact Binding，不在 R2 顺手迁移。
7. G 拥有权威 context/gate/schema/protected-span/chat 适配收口。后续新增生产 Skill 要复用其结果；H 的检索成本优化不是 Timeline/Director 的硬前置。

## 7. R1 / R2 最小边界建议（仅建议，未执行）

**R1：Frontend Product Shell。** 单独 ExecPlan；overview 默认入口、Scope Bar、概览/创作/剧集/资料一级导航、Series/Episode navigation 与 Production Rail 壳层。保留 Graph/Assets/Agent 深链及 Dock、刷新/返回/切项目隔离。新建/打开/切项目都走 overview。为达到真实导航验收，建议把 project-scoped Series/Episode 和必需文档索引的最小只读契约纳入该阶段的明确范围；概览仅展示可证明事实。尚无权威 Gate/审查状态时显示未接入，不作放行判断。不实现编辑器、Timeline/Director、审批/Lineage，也不借 R1 实施 G/H。

**R2：Lifecycle + Lineage + Change Proposal。** 单独 ExecPlan；首先冻结 identity/revision/block 与审批/新鲜度契约，再以现有 Artifact→Artifact 链为首个完整切片，验证填充库增量升级、局部影响与项目隔离。随后完成阶段内 Impact、Proposal accept/reject、兼容性校验与 rebase、生成新 revision 的 revert、review audit。不能仅做几张新表就宣称 R2 完成。旧依赖短期一致性对照后切换 owner，避免长期双写；不自动删旧表，不重生成内容。不接 Media/Provider、Timeline Core、Previz，不改 Planning 正文。若需聊天/新 Skill 接入而 G 未完成，单独记录依赖并留在边界内，不造第二套执行通道。

## 8. 交付与停止点

R0 交付本报告、阶段 ExecPlan，以及 Agent active plan 的 Git 恢复事实修正。用户原 V4 文件保留不动；不修改功能代码、OpenAPI、前端类型、feature 状态或数据库。未运行 full check、历史测试、mutation、benchmark，也未联网核对外部架构参考——本次只对照仓库事实，不评价第三方最新实现。

静态审计和 schema 比对足以完成本阶段；行为正确性、填充库升级演练、R1/R2 新契约验证属于后续明确授权的阶段。停在 R0 完成边界。
