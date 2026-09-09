# F14 Agent 写入工具链 — 测试文档

## 测试目标

验证 agent 写入类工具（图谱/文档五件）「执行仅登记 pending 不落库」、轮末 done 事件携带待写入清单、前端确认卡、approve 服务端二次校验批量落库与图谱/文档失效刷新全链路（DESIGN §13.2，DECISIONS 2026-09-08 OQ-8 轮末统一确认）。

## 范围与关键设计（实现契约）

- 新表 `agent_pending_writes(id "pw-" 前缀, conversation_id FK CASCADE, project_id, kind, payload_json, baseline_json, status: pending/approved/rejected, created_at)`；会话删除经 FK CASCADE 清理、项目删除经会话级联清理。
- 写入工具五件（tools.py，登记≠落库，返回「已登记，待作者确认」tool result）：`create_entity` / `update_entity` / `create_relation(source_name/target_name 登记时名称解析为 id)` / `create_memory_doc(kind, title?)` / `write_doc_section(doc_id, seq, content, title?)`（登记时记录段 CAS 基线 version）。
- 每轮 pending 上限 `AGENT_MAX_PENDING_WRITES`（config，默认 8；超限工具返回错误文本不打断轮）。
- done 事件增 `pending_writes` 键（本轮新增项：id/kind/summary/payload；无新增不带该键）。
- 新端点：`POST /api/agent/pending-writes/approve`（逐项二次校验落库，成功→approved、失败保持 pending 进 failed）、`POST /api/agent/pending-writes/reject`（置 rejected）、`GET /api/agent/pending-writes?conversation_id=`（回读）。
- 落库复用 entities/relations/agent 既有 service（校验单一来源）；approve 白名单重建输入 DTO（不信任前端）；写入工具执行属对话轮事务（轮失败回滚则 pending 一并消失）。
- `DOC_TEMPLATES/GUIDE_KINDS` 抽出 `agent/templates.py`（tools↔service 循环 import 解除）；`create_doc` 增可选 title 覆盖；`SectionUpdate` 增可选 title（None=不改）；`propose` 标注 legacy。

## 层级矩阵

| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1-U9: 写入工具登记行为 | backend/tests/unit/test_agent_tools.py | 必须 | pass |
| L1 单元 | U10-U20: 轮末清单/approve/reject/段 CAS | backend/tests/unit/test_agent_service.py | 必须 | pass |
| L1 单元 | FU10: agentStore pending 状态机 | frontend/tests/unit/stores/agentStore.test.ts | 必须 | pass |
| L2 集成 | I1-I7: SSE 携带清单/approve 落库/CAS 冲突/级联 | backend/tests/integration/test_agent_api.py | 必须 | pass |
| L2 集成 | FI10: PendingWritesCard 交互 | frontend/tests/integration/AgentExperience.test.tsx | 必须 | pass |
| L3 E2E | E2: 写入工具→确认→图谱刷新（跨组件：agent+entities+perspectives） | backend/tests/e2e/test_agent_flow.py | 必须 | pass |
| L3 E2E | FE1-AG07/AG08: 浏览器端确认卡流 | frontend/e2e/agent.spec.ts | 必须 | pass |

## 用例说明

### L1 单元 — 写入工具（test_agent_tools.py）

- U1: create_entity 有效登记（有效类：type/name/description/aliases/properties 全量）→ PendingWrite 行 kind/payload 与 summary 正确，tool result 含「待作者确认」且不含「已写入」。
- U2 参数化: 白名单剔除（无效类-多余字段）：payload 含 `id`/`project_id`/未知键 → 剔除后不进 payload（服务端注入字段不可被工具参数指定）。
- U3 参数化: 必填缺失（无效类）：create_entity 缺 type / 缺 name / name 空串 → 三要素错误文本，不登记。
- U4 参数化: update_entity 目标校验（有效类：本项目实体→登记 entity_id+patch；无效类：不存在 id / 跨项目实体 → 三要素错误）。
- U5 参数化: create_relation 名称解析（有效类：名称精确命中、别名命中 → payload.source/target 为解析 id 且携带 source_name/target_name 名称快照；无效类：未命中名称 / known_by 成员名称未命中 → 三要素错误提示先检索；known_by 命中成员解析为 id 列表）。
- U6 参数化: create_memory_doc（有效类：合法 kind 登记 title 透传，缺省取模板标题；无效类：未知 kind、指导类同 kind 已存在 → 三要素错误，不登记）。
- U7 参数化: write_doc_section（有效类：doc+seq 存在 → 登记 baseline.expected_version=段当前 version；无效类：doc 不存在 / seq 越界 / 跨项目 doc → 三要素错误）。
- U8 边界值: 上限——登记第 AGENT_MAX_PENDING_WRITES 项恰好成功（边界上）；第 +1 项失败（边界外，三要素错误不打断）。
- U9: 检索工具回归——TOOL_SPECS 含九个工具（四检索+五写入）且名称稳定。

### L1 单元 — service（test_agent_service.py）

- U10: 轮末 done 携带清单——LLM 桩调一个写入工具 → done.data.pending_writes 一项且 id/payload 与登记一致；无写入轮 done 不含该键（两项路径由 I1/E2 覆盖）。
- U10 补充: known_by 名称解析为 id（P1-1 审查修复）与 update_entity/create_relation 目标视角过滤守卫（P1-2 审查修复）判杀用例。
- U11: approve create_entity——payload 白名单重建 EntityCreate、project_id 以会话归属覆盖（payload 携带异项目 project_id 被忽略）→ 落库成功 status=approved。
- U12: approve update_entity——properties_patch 浅合并既有 properties（复用 entities.update 合并语义）。
- U13: approve create_relation——source/target id 落库，关系可读回。
- U14 参数化: approve create_memory_doc（有效类：title 覆盖模板标题；无效类：同 kind 指导文档已存在 → failed 三要素不阻断，status 保持 pending）。
- U15 参数化: approve write_doc_section CAS（有效类：基线未变 → 段内容/版本更新且 updated_by=agent；无效类：登记后段已被改（版本推进）→ failed 含版本冲突三要素，段内容不被覆盖）。
- U16: approve 单项失败不阻断——一项损坏 payload 其余项照常落库（failed 列表承载坏项）。
- U17 参数化: approve 拒绝态（无效类：id 不存在 / status 非 pending（approved、rejected）→ 该项 failed 三要素）。
- U18: reject——pending → rejected（响应含 id）；非 pending 项跳过；会话不存在 404。
- U19: list_pending——按会话过滤、created_at 升序、含全部状态。
- U20 参数化: create_doc title 扩展（边界值：title 显式 → 覆盖；title 空/缺省 → 模板标题）。

### L1 单元 — 前端 store（agentStore.test.ts）

- FU10a: done 事件 pending_writes → 写入 pendingBySession（卡片数据源）。
- FU10b: approvePendingWrites 成功——created 项移除待决/failed 项保留并挂错误、图谱失效（loadGraph 调用）、文档列表强刷。
- FU10c: rejectPendingWrites——项移除待决；API 失败落三要素错误态（E16）。

### L2 集成（test_agent_api.py，LLM 桩走 stream_chat_turn）

- I1: SSE 全链——桩轮内调 create_entity+write_doc_section → tool 事件对 ×2 → done.data.pending_writes 两项 → GET pending-writes 回读一致。
- I2: approve → 实体真落库（GET /api/entities 可见）→ 列表状态 approved；message 流不受影响。
- I3: CAS 冲突路径——登记后用户 PATCH 段（版本推进）→ approve 该项 failed 原因含「版本冲突」。
- I4: approve/reject 404——conversation_id 不存在（三要素完整 detail）。
- I5: reject → 响应含 id → GET 状态 rejected → 重复 approve 该项 failed。
- I6: 项目级联——删项目后 pending 行随会话级联清理（直查不存在）。
- I7: 上限集成——桩连续登记超限项 → 超限项 tool result 为错误文本、轮正常 done（不打断）。

### L2 集成 — 前端（AgentExperience.test.tsx）

- FI10: PendingWritesCard——默认全选；取消勾选后「写入所选」仅提交勾选 id，未提交项保留；全部成功项移除；失败项保留并挂三要素错误；「放弃」调 reject 且项移除。

### L3 E2E

- E2: 跨组件理由——approve 落库改变图谱与文档数据，须验证 perspectives 图查询/文档读取与 projects 归属联动；走公开 API 全链：对话（写入工具桩）→ done 清单 → approve → /api/graph 含新实体、文档段内容更新。
- FE1-AG07/AG08: 浏览器端——mock SSE 携带 pending_writes → 确认卡渲染（两项）→ 全部写入 → approve 请求携带全部 ids → 成功后卡片消失。

## 变异测试结果（2026-09-09 定稿）

- **scope（被测文件缩域，DECISIONS 2026-09-09 成本治理）**: `app/agent/` 内 F14 触碰的 7 文件——tools.py(340)/service.py(608)/models.py(113)/schemas.py(74)/router.py(62)/repository.py(17)/templates.py(22) = **1236 变异体**；未触碰的 llm.py/prompts.py/rendering.py（358 体）由 F13 基线（bb6484d 后未改动）覆盖。**静态契约数据源头豁免**：TOOL_SPECS（工具声明 184 行纯契约数据）抽至零逻辑模块 `tool_specs.py` 排除在变异路径外（§9 等价豁免的源头化，审查 P2-2 后置生效）。
- **判杀器（E19 修订后口径）**: 默认模块 L1 单测全集 `tests/unit/test_agent_{llm,memory_docs,prompts,service,tools}.py` + L2 `tests/integration/test_agent_api.py` + L3 `tests/e2e/test_agent_flow.py` + 架构测试 `tests/architecture/test_architecture.py`。
- **结果**: kill rate **100%**（1236/1236 实杀，存活 0 / 等价登记 0 / 超时 0 / 可疑 0），远超 85% 门槛；运行后 `git status` 零残留、无 .bak，后端 391 绿 + make check 通过（T-20260907-01 规程）。

### 过程记录（E19 事故与成本治理，2026-09-09）

1. 首轮缩域跑（判杀器误只带 5 件单测中的 2 件 + 集成 + e2e）：1236 体 kill rate 仅 51%（tools.py 49%/service.py 54%），604 存活集中在窗口压缩/工具配额/SSE 事件常量/三要素文案——均为 prompts/llm/memory_docs/架构测试覆盖的逻辑，属 **E19 判杀器子集化**（E04 层级覆盖的文件级同型），非测试或代码缺陷。
2. 整改：error.jsonl 登记 E19 并转化为自动守卫（`task.py mutate` 默认判杀器 = 模块 L1 单测全集 glob，单测恒为基线、显式路径只可叠加不可排除）；同轮落地 mutmut 成本治理（`--files` 文件级缩域 + 基线指纹续跑，DECISIONS 2026-09-09）。
3. 复跑（E19 修订后完整判杀器）：1236 体全部实杀，约 55 分钟（对比全模块口径 ~3 小时，缩域 + 缩域后判杀器仍全的口径下成本与判杀力兼得）。

## 验收审查记录（§10 协议第 5 轮；verify 前完成）

独立只读子代理审查（2026-09-09），发现 P0×0 / P1×3 / P2×6，triage 决议：

| 编号 | 级别 | 发现 | 决议 |
|------|------|------|------|
| P1-1 | P1 | create_relation 的 known_by 成员名称未解析为 id，approve 落库时 relations service 校验 id 恒失败（工具契约断裂；U5/U13 未覆盖） | **修复**：登记时经 `_resolve_entity_by_name` 与 source/target 同路径解析（未命中三要素错误）；补 U5 known_by 解析/未命中两用例 + U13 known_by id 透传断言 |
| P1-2 | P1 | 写入工具目标读取绕过 perspectives（名称解析与 update 目标快照直接进 LLM 上下文），违反 agent/CONSTRAINTS 视角过滤约束 | **修复**：`_resolve_entity_by_name` 三态化（miss/invisible/ok，invisible 由 filter_entities_for_agent 判定）；update_entity 目标叠加 filter 放行；补视角守卫参数化用例（可见/不可见/不存在） |
| P1-3 | P1 | agentStore.approvePendingWrites 过滤条件把未提交勾选的 pending 项误删（UI 上永久不可操作）；FI10 断言锁死该错误行为（E14 同型） | **修复**：过滤条件改 `!ids.includes(p.id) \|\| failedIds.has(p.id)`（未提交保留、失败保留）；FI10 断言改为保留 pw-2 |
| P2-1 | P2 | 测试文档与实现双态不符（U10 两项/实际一项、U5「不含 source_name」/实际携带快照、FI10 成功态措辞、AG-03 编号） | **修复**：文档措辞对齐实现（E01 同型整改） |
| P2-2 | P2 | tools.py docstring「不抛异常」过度声明（仅折叠 Pydantic 校验） | **修复**：docstring 收窄表述 |
| P2-3 | P2 | GET /pending-writes 前端零调用（刷新后服务端 pending 行 UI 不可见） | **登记为已知限制**：会话内 done 为主路径；回读接线留待后续增强（避免本功能范围膨胀） |
| P2-4 | P2 | 审查时变异门禁未完成、状态列未回填、PROGRESS 任务未勾 | 流程性发现：mutmut 随后运行、状态列与 PROGRESS 随收尾回填（本表即为整改记录） |
| P2-5 | P2 | agent/ARCHITECTURE.md 与 data_struct_define.md 未同步 F14 | **修复**：提交前完成同步（ARCHITECTURE 职责/分层/接口/事件表/写入工具链节；CONSTRAINTS 写入安全与视角过滤；data_struct §11.3 补表） |
| P2-6 | P2 | ①summary 括号格式不一致 ②update_entity except Exception 过宽 ③e2e ChatCapture 无显式有界守卫 | **修复**：①统一 `-[type]-> ` ②只捕 NotFoundError ③补显式守卫（对齐集成侧 T-20260907-02 模式） |

## 验收判定

所有"必须"层级通过 + 状态列全 pass + 变异测试达标（§9）+ make check 通过 → 功能完成。
