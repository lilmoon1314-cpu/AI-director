# agent 模块 — LLM 多轮对话

## 职责

- 前置 Agent 多轮对话（SSE 流式输出）
- 根据用户描述生成实体/关系属性建议（结构化 JSON 草案，不直接写库）
- 用户确认后将草案落库（经 entities/relations service）
- 对话上下文组装（仅注入当前视角可见实体）

## 对外接口

### service 层（其他模块唯一入口）

| 函数 | 说明 | 异常 |
|------|------|------|
| `stream_chat(session_id: str, message: str, perspective: Perspective) -> AsyncGenerator[str]` | SSE 流式回复 | AgentError（超时/端点失败） |
| `propose(session_id: str, message: str) -> list[EntityDraft \| RelationDraft]` | 生成建议草案（LLM JSON mode） | AgentError / ValidationError（草案结构非法） |
| `confirm_write(drafts: list[Draft], confirmed: list[bool]) -> WriteResult` | 确认后落库（逐项调 entities/relations service） | 落库异常原样透出 |

`Draft = { draft_id, kind: entity|relation, payload, summary }`；`WriteResult = { created: [...], failed: [{draft_id, reason}] }`。

### HTTP 路由（/api/agent）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/agent/chat（SSE） | 流式对话 |
| POST | /api/agent/propose | 生成实体/关系建议草案 |
| POST | /api/agent/confirm | 确认草案并写库 |

## 依赖

- 依赖：core、entities（确认落库、上下文检索）、relations（确认落库）、perspectives（上下文视角过滤）
- 被依赖：frontend（对话面板）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 agent 前必读）。

补充（内存管理）：会话历史存于进程内 dict + 上限淘汰（MVP 单进程成立，上限值来自 config）；SSE 使用 async generator，客户端断开自动终止并释放。
