# agent 模块 — LLM 对话、记忆文档与写入工具链（F10/F13/F14 已就位）

## 职责

- 会话与消息持久化（conversations / messages，按项目隔离；AgentHome 与 AgentDock 共用同一会话池）
- SSE 流式对话（受控 ReAct 工具循环 + 预算裁剪 + 滚动摘要维护）
- 项目记忆文档：HTML 分段模板建档、段级读写（CAS 乐观锁）、自包含 HTML 渲染
- **写入工具链（F14，OQ-8 轮末统一确认）**：五写入工具（图谱三件 + 文档两件）执行仅登记
  agent_pending_writes（不落库）→ done 事件携带清单 → 作者经确认卡 approve（服务端逐项二次校验
  落库）/reject；propose/confirm 草案两段式为 legacy 保留
- LLM 上下文组装：目录式两跳检索 + 三层记忆模型 + 视角过滤注入（唯一入口 `_assemble_chat_context`）

## 分层结构

```
router.py       # /api/agent 端点：参数解析、SSE 帧序列化、响应包装
service.py      # 业务编排（其他模块唯一入口）：会话/对话/文档/写入确认/草案/项目级联
repository.py   # 数据访问（唯一允许 import models 的层；不 commit/rollback）
models.py       # ORM：Conversation/Message/MemoryDoc/MemoryDocSection/PendingWrite
schemas.py      # Pydantic DTO + id 生成器（conv-/msg-/mdoc-/msec-/draft-/pw- 前缀）
templates.py    # DOC_TEMPLATES/GUIDE_KINDS 共享常量（service 与 tools 同源校验；零逻辑）
llm.py          # OpenAI 兼容客户端封装：进程单例、错误包装、usage 记录、
                #   JSON 修复重试（上限 1 次）、轻量模型路由（summarize）
prompts.py      # system 构建、分层上下文组装与预算裁剪、注入防护分隔符、
                #   token 估算（estimate_tokens）、目录渲染、内容 digest
tools.py        # 受控 ReAct 工具：四检索 + 五写入登记（F14；写入 ≠ 落库；
                #   名称解析经视角过滤；失败折叠为文本）
rendering.py    # 记忆文档自包含 HTML 页（全转义 _esc，暗色适配）
```

import-linter 契约：外部模块只许 `app.agent.service`；repository/models/schemas/llm/prompts/tools/rendering 为内部层（main 经 `service.dispose_resources` 释放 LLM 客户端）。

## 对外接口

### service 层（其他模块唯一入口）

| 函数 | 说明 | 异常 |
|------|------|------|
| `create_conversation(session, schema) -> SessionRead` | 创建会话（project_id 空=默认项目） | NotFoundError |
| `list_conversations(session, project_id) -> list[SessionRead]` | 项目会话（最近活跃在前） | NotFoundError |
| `ensure_conversation(session, conversation_id) -> SessionRead` | 存在性校验（SSE 流开始前的 404 出口） | NotFoundError |
| `get_messages(session, conversation_id) -> list[MessageRead]` | 会话全部消息（时间正序） | NotFoundError |
| `stream_chat(conversation_id, message, *, perspective, character_id="") -> AsyncIterator[dict]` | 一轮对话的 SSE 事件流（见下方协议） | NotFoundError（首个 yield 前）；轮内错误以 error 事件承载 |
| `propose_drafts(session, schema) -> ProposeResponse` | 【legacy】LLM JSON mode 产实体/关系草案（F14 起写入主路径为写入工具链） | NotFoundError / ValidationError / AgentError |
| `confirm_write(session, schema) -> ConfirmResponse` | 【legacy】确认项落库（服务端重验 payload + 会话归属项目注入；单项失败折叠 failed） | 落库异常折叠进 failed，不冒泡 |
| `approve_pending_writes(session, schema) -> ApproveResponse` | 批准待写入（逐项白名单重建 DTO 二次校验落库、project_id 会话归属覆盖；成功置 approved，失败保持 pending 进 failed 不阻断，F14） | NotFoundError |
| `reject_pending_writes(session, schema) -> RejectResponse` | 放弃待写入（置 rejected；非 pending 跳过，F14） | NotFoundError |
| `list_pending_writes(session, conversation_id) -> list[PendingWriteRead]` | 会话全部登记行（时间升序含全部状态，F14） | NotFoundError |
| `create_doc(session, project_id, kind, *, title=None) -> MemoryDocRead` | 按模板建档（positioning/style，title 显式覆盖模板标题；指导类唯一 409） | ValidationError（未知 kind）/ NotFoundError / ConflictError |
| `list_docs(session, project_id) -> list[MemoryDocBrief]` | 文档卡片（首段预览） | NotFoundError |
| `get_doc(session, doc_id) -> MemoryDocRead` | 文档全文（含段列表，seq 升序） | NotFoundError |
| `delete_doc(session, doc_id) -> None` | 删除文档（段经 CASCADE） | NotFoundError |
| `update_section(session, doc_id, section_id, payload, *, updated_by) -> MemoryDocSectionRead` | 段级更新（CAS：expected_version 不符 409；用户与 agent patch 共用唯一写入口） | NotFoundError / ConflictError |
| `render_page(session, doc_id) -> str` | 自包含 HTML 页文本 | NotFoundError |
| `delete_project_data(session, project_id) -> list[str]` | 项目级联清理（projects.router 编排调用） | 无 |
| `dispose_resources() -> None` | 释放 LLM 客户端（lifespan 停机调用） | 无 |

### HTTP 路由（/api/agent；项目维度经 project_id 查询参数，缺省=默认项目）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/agent/sessions?project_id= | 创建会话（201） |
| GET | /api/agent/sessions?project_id= | 列出项目会话 |
| GET | /api/agent/sessions/{id}/messages | 会话消息（时间正序） |
| POST | /api/agent/chat | SSE 流式对话（StreamingResponse，事件协议见下） |
| POST | /api/agent/propose | 【legacy】生成写入草案（不落库） |
| POST | /api/agent/confirm | 【legacy】确认草案落库（两段式第二段） |
| GET | /api/agent/pending-writes?conversation_id= | 会话待写入登记列表（F14） |
| POST | /api/agent/pending-writes/approve | 批准待写入（二次校验落库；F14） |
| POST | /api/agent/pending-writes/reject | 放弃待写入（F14） |
| DELETE | /api/agent/sessions/{conversation_id} | 删除会话（消息级联清理；204；404 三要素，F13） |
| POST | /api/agent/memory-docs?kind=positioning&project_id= | 按模板建档（201） |
| GET | /api/agent/memory-docs?project_id= | 文档卡片列表 |
| GET | /api/agent/memory-docs/{doc_id} | 文档全文 |
| DELETE | /api/agent/memory-docs/{doc_id} | 删除文档（204） |
| GET | /api/agent/memory-docs/{doc_id}/page | 自包含 HTML 页（text/html，iframe 预览源） |
| PATCH | /api/agent/memory-docs/{doc_id}/sections/{section_id}?updated_by=user | 段级更新（updated_by ∈ user\|agent；CAS 409） |

### SSE 事件协议（POST /chat，帧 = `event: <名>\ndata: <json>\n\n`）

| 事件 | data 载荷 | 说明 |
|------|-----------|------|
| `message_start` | `{conversation_id}` | 流开始 |
| `tool` | `{name, phase: start\|done, calls_used?}` | 检索工具轮（每调用两条） |
| `reasoning` | `{text}` | 思考过程增量（逐 chunk，F13；端点不产思考则整类缺省） |
| `token` | `{text}` | 回答文本增量（真流式：stream_chat_turn 逐 chunk 透传，F13 废除伪分块） |
| `usage` | `{prompt_tokens, completion_tokens, context_max_tokens, context_ratio}` | 本轮 token 用量与容量占比（done 前；端点未返回 usage 则缺省，F13） |
| `done` | `{message_id, pending_writes?}` | 正常收尾（assistant 消息含 reasoning/usage 已落库）；本轮有写入工具登记时携带 `pending_writes` 清单（PendingWriteRead 数组，F14） |
| `error` | `{code, problem, cause, fix}` | 轮内失败（LLM/合规拦截），三要素完整 |
| `draft` / `doc_patch` / `ask_user` / `plan` / `step` | — | 预留（服务端已定义事件名常量，前端按白名单忽略未知类型） |

正常序列：`message_start → (tool…)* → (reasoning… token…)… → usage? → done`；失败序列以 `error` 收尾（HTTP 仍 200）。

## 对话轮内部机制（stream_chat）

- **用户消息先行提交**：user 行 + 标题回填在进入 LLM 轮之前 commit——LLM 失败（rollback）不丢已发生的用户输入。
- **受控 ReAct**：每轮工具调用配额 `AGENT_MAX_TOOL_CALLS_PER_TURN`（config）；超限后不再向 LLM 提供工具定义，强制作答（防循环）。
- **写入登记（F14）**：写入类工具执行经 `tools._register_pending` 落 `agent_pending_writes` 行（pending 状态，
  随对话轮事务提交/回滚——轮失败登记一并消失）；轮内上限 `AGENT_MAX_PENDING_WRITES`（config），
  超限返回三要素错误文本不打断轮；done 事件在 commit 后携带本轮清单驱动前端确认卡。
- **真流式（F13）**：`llm.stream_chat_turn` 以 `stream=True + include_usage` 调用补全端点，产出四类事件（reasoning_delta / content_delta 逐片透传、流式 tool_calls 按 index 聚合、usage 透传、聚合 AssistantTurn）；`chat_turn`（非流式）保留给摘要 / propose 等结构化路径。思考与 usage 随 assistant 行落库（`messages.reasoning/prompt_tokens/completion_tokens`，F13 迁移 c7d2e9a4b513），回读经 MessageRead 透出。
- **滚动摘要**：轮末若「摘要游标之后的尾部」超窗（`AGENT_HISTORY_WINDOW_MESSAGES`），溢出部分交轻量模型（`LLM_MODEL_LIGHT`）增量压缩进 `conversation.summary` 并推进 `summary_until_id`；摘要失败或空结果仅发 `agent_summary_skipped` 事件跳过（下轮重试），不阻断对话。
- **会话自管理**：生成器内经 session factory 自开自释放（连接生命周期与 SSE 流一致，不占请求级会话）；轮内错误统一转 error 事件。

## 写入工具链（F14，DESIGN §13.2 / OQ-8 轮末统一确认）

```
agent 调写入工具 → _register_pending 落 pending 行（返回「已登记待确认」tool result）
→ 本轮流式完毕（done 携带 pending_writes 清单）
→ 前端确认卡（勾选）→ POST /pending-writes/approve
   → _apply_pending_write 按类别白名单重建输入 DTO（create_entity → EntityCreate、
     create_relation → RelationCreate、create_memory_doc → create_doc、
     write_doc_section → update_section 的 CAS 复核）→ 落库 → status=approved
   → 单项失败保持 pending 进 failed（三要素），不阻断其他项
→ [放弃] → POST /pending-writes/reject → status=rejected
```

- 工具九件 = 四检索 + 五写入（`create_entity` / `update_entity` / `create_relation` / `create_memory_doc` / `write_doc_section`）。
- 写入参数 Pydantic 白名单（extra=ignore）：id/project_id 等服务端注入字段不可经工具参数指定。
- 端点与 known_by 的**名称在登记时解析为实体 id**（`_resolve_entity_by_name`：entities.search 精确匹配 →
  perspectives.filter_entities_for_agent 放行才返回——名称快照进 LLM 上下文必须过视角过滤）。
- `write_doc_section` 登记时记录段 CAS 基线（`baseline_json`：section_id + expected_version）——
  approve 时经 update_section 复核，用户在确认前手改该段即版本冲突拒绝（绝不覆盖）。
- `update_entity` 的 properties_patch 落库走 entities.update 浅合并语义。
- 落库复用 entities/relations/agent 既有 service（校验单一来源）；approve 服务端复核不信任登记载荷。

## 三层记忆模型（DECISIONS 2026-09-07）

| 层 | 载体 | 说明 |
|----|------|------|
| L0 harness | 代码/配置（prompts.build_system_prompt + config） | 角色设定、规则、注入防护声明（不落库） |
| L1 长期 | 图谱（事实唯一源）+ memory_docs（项目工作上下文）+ conversations.summary（滚动摘要） | 文档为 HTML 分段模板，**非世界观事实副本** |
| L2 短期 | messages 表 + 窗口策略 | 游标后尾部最近 N 条全文注入；本轮输入单独追加（历史行剔除防双份） |

### 上下文分层顺序（前缀缓存友好，稳定 → 易变）

`system（静态规则）→ 项目上下文块（文档段全文 → 图谱目录 → 文档目录 → 会话摘要）→ 近期对话消息`

预算裁剪固定顺序（`AGENT_CONTEXT_MAX_TOKENS`）：文档段降级为目录 → 丢会话摘要 → 裁最旧消息；system 与本轮用户消息永不裁。

### 目录式两跳检索

常驻上下文只含图谱目录（id/type/name/aliases 紧凑清单）与文档目录（段标题 + sha256 前 8 位）；细节经四工具按需读取：`search_entities` / `get_entity_detail` / `get_neighborhood` / `read_doc_section`（工具结果经 wrap_data 包裹 + 截断后注入）；写入经五工具登记（见「写入工具链」，F14）。

## 依赖

- 依赖：core、entities（approve 落库 + 工具检索 + 名称解析）、relations（approve 落库）、perspectives（视角过滤唯一来源：get_graph + filter_entities_for_agent——目录/详情/写入名称解析全走此入口）、projects（归属校验）
- 被依赖：frontend（对话面板/确认卡/记忆文档编辑）、main（路由挂载 + lifespan dispose）、projects.router（删除级联编排）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 agent 前必读）。

内存管理补充：无进程内会话缓存（每轮从 DB 现读文档目录与历史，用户手改下轮即生效）；LLM 客户端为进程级单例（llm.get_client 懒加载，lifespan 停机经 service.dispose_resources 释放）。
