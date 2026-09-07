# agent 模块 — LLM 对话、记忆文档与草案两段式写入（F10 已就位）

## 职责

- 会话与消息持久化（conversations / messages，按项目隔离；AgentHome 与 AgentDock 共用同一会话池）
- SSE 流式对话（受控 ReAct 工具循环 + 预算裁剪 + 滚动摘要维护）
- 项目记忆文档：HTML 分段模板建档、段级读写（CAS 乐观锁）、自包含 HTML 渲染
- 草案两段式写入图谱：propose 产草案（不落库）→ 作者确认 → confirm 服务端复核后落库（经 entities/relations service）
- LLM 上下文组装：目录式两跳检索 + 三层记忆模型 + 视角过滤注入（唯一入口 `_assemble_chat_context`）

## 分层结构

```
router.py       # /api/agent 端点：参数解析、SSE 帧序列化、响应包装
service.py      # 业务编排（其他模块唯一入口）：会话/对话/文档/草案/项目级联
repository.py   # 数据访问（唯一允许 import models 的层；不 commit/rollback）
models.py       # ORM：Conversation/Message/MemoryDoc/MemoryDocSection
schemas.py      # Pydantic DTO + id 生成器（conv-/msg-/mdoc-/msec-/draft- 前缀）
llm.py          # OpenAI 兼容客户端封装：进程单例、错误包装、usage 记录、
                #   JSON 修复重试（上限 1 次）、轻量模型路由（summarize）
prompts.py      # system 构建、分层上下文组装与预算裁剪、注入防护分隔符、
                #   token 估算（estimate_tokens）、目录渲染、内容 digest
tools.py        # 受控 ReAct 四检索工具（视角过滤后只读检索；失败折叠为文本）
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
| `propose_drafts(session, schema) -> ProposeResponse` | LLM JSON mode 产实体/关系草案（draft_id 系统生成；payload 宽松 dict） | NotFoundError / ValidationError / AgentError |
| `confirm_write(session, schema) -> ConfirmResponse` | 确认项落库（服务端重验 payload + 会话归属项目注入；单项失败折叠 failed） | 落库异常折叠进 failed，不冒泡 |
| `create_doc(session, project_id, kind) -> MemoryDocRead` | 按模板建档（positioning/style，初始段空白） | ValidationError（未知 kind）/ NotFoundError |
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
| POST | /api/agent/propose | 生成写入草案（不落库） |
| POST | /api/agent/confirm | 确认草案落库（两段式第二段） |
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
| `token` | `{text}` | 回答文本分块（伪流式：上游整体返回后按 24 字符下发） |
| `done` | `{message_id}` | 正常收尾（assistant 消息已落库） |
| `error` | `{code, problem, cause, fix}` | 轮内失败（LLM/合规拦截），三要素完整 |
| `draft` / `doc_patch` / `ask_user` / `plan` / `step` | — | **F13 预留**（服务端已定义事件名常量，前端按白名单忽略未知类型） |

正常序列：`message_start → (tool…)* → token… → done`；失败序列以 `error` 收尾（HTTP 仍 200）。

## 对话轮内部机制（stream_chat）

- **用户消息先行提交**：user 行 + 标题回填在进入 LLM 轮之前 commit——LLM 失败（rollback）不丢已发生的用户输入。
- **受控 ReAct**：每轮工具调用配额 `AGENT_MAX_TOOL_CALLS_PER_TURN`（config）；超限后不再向 LLM 提供工具定义，强制作答（防循环）。
- **伪流式**：chat_turn 为非流式补全（简化错误处理与 usage 记录），最终回答按 `_TOKEN_CHUNK_CHARS=24` 分块以 token 事件下发。
- **滚动摘要**：轮末若「摘要游标之后的尾部」超窗（`AGENT_HISTORY_WINDOW_MESSAGES`），溢出部分交轻量模型（`LLM_MODEL_LIGHT`）增量压缩进 `conversation.summary` 并推进 `summary_until_id`；摘要失败或空结果仅发 `agent_summary_skipped` 事件跳过（下轮重试），不阻断对话。
- **会话自管理**：生成器内经 session factory 自开自释放（连接生命周期与 SSE 流一致，不占请求级会话）；轮内错误统一转 error 事件。

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

常驻上下文只含图谱目录（id/type/name/aliases 紧凑清单）与文档目录（段标题 + sha256 前 8 位）；细节经四工具按需读取：`search_entities` / `get_entity_detail` / `get_neighborhood` / `read_doc_section`（工具结果经 wrap_data 包裹 + 截断后注入）。

## 依赖

- 依赖：core、entities（confirm 落库 + 工具检索）、relations（confirm 落库）、perspectives（视角过滤唯一来源：get_graph + filter_entities_for_agent）、projects（归属校验）
- 被依赖：frontend（对话面板/记忆文档编辑）、main（路由挂载 + lifespan dispose）、projects.router（删除级联编排）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 agent 前必读）。

内存管理补充：无进程内会话缓存（每轮从 DB 现读文档目录与历史，用户手改下轮即生效）；LLM 客户端为进程级单例（llm.get_client 懒加载，lifespan 停机经 service.dispose_resources 释放）。
