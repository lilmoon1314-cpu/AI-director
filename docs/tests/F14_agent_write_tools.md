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
| L1 单元 | U1-U9: 写入工具登记行为 | backend/tests/unit/test_agent_tools.py | 必须 | pending |
| L1 单元 | U10-U20: 轮末清单/approve/reject/段 CAS | backend/tests/unit/test_agent_service.py | 必须 | pending |
| L1 单元 | FU10: agentStore pending 状态机 | frontend/tests/unit/stores/agentStore.test.ts | 必须 | pending |
| L2 集成 | I1-I7: SSE 携带清单/approve 落库/CAS 冲突/级联 | backend/tests/integration/test_agent_api.py | 必须 | pending |
| L2 集成 | FI10: PendingWritesCard 交互 | frontend/tests/integration/AgentExperience.test.tsx | 必须 | pending |
| L3 E2E | E2: 写入工具→确认→图谱刷新（跨组件：agent+entities+perspectives） | backend/tests/e2e/test_agent_flow.py | 必须 | pending |
| L3 E2E | FE1-AG07/AG08: 浏览器端确认卡流 | frontend/e2e/agent.spec.ts | 必须 | pending |

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

## 变异测试结果（用例实现完成后填写）

- scope：`app.agent`（service/tools 定向）
- kill rate / 实杀数 / 等价登记数 / 存活变异体逐一分析：待填

## 验收审查记录（§10 协议；verify 前填写）

待填

## 验收判定

所有"必须"层级通过 + 状态列全 pass + 变异测试达标（§9）+ make check 通过 → 功能完成。
