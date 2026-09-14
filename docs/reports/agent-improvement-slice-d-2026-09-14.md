# Agent 改善任务分析报告：D 阶段

## 结论

D「持久运行、可恢复流与摘要维护解耦」已经完成。聊天不再把一次 HTTP/SSE
连接当作唯一事实：用户消息、运行状态、流事件、最终回复、错误和取消都能从主库恢复。
浏览器刷新或连接提前结束后，前端会查询服务器并从最后事件序号继续；待确认写入也会随
消息一起回读。下一阶段 E 的“摘要内容是否完整保留关键语义”尚未实施。

## 用户现在得到什么

| 场景 | D 之前 | D 完成后 |
|---|---|---|
| 网络断开或 SSE 提前 EOF | 客户端只能猜测本轮是否完成 | 查询持久 run，并从最后 `seq` 回放 |
| 刷新页面 | 已存消息可回读，但 pending 卡和进行中回复可能消失 | 消息、pending 和最新活动 run 一起恢复 |
| 重复提交 | 可能再次保存同一轮 | 相同 request id 复用同一 run；不同内容返回 409 |
| 点击停止 | 只关闭浏览器请求 | 服务端先保存 cancelled，再取消 provider task |
| 服务器重启 | 旧流没有确定终态 | 有回复的 crash gap 收口为 completed；其余标 failed，不自动重放写入 |
| 摘要失败 | 可能回滚已成功回答 | 回答/pending 先提交；摘要用独立事务维护 |

“completed”只表示回复和 pending 已保存，不表示作者已经批准 pending 所代表的业务修改。
批准状态仍由 C 阶段的 `pending/approved/rejected` 状态机负责。

## 模块说明

### `backend/app/agent/runs.py`

这是 D 新增的运行生命周期 owner。它负责：

- 在一个短事务里保存用户消息和 `queued` run；
- 用 `(conversation_id, request_id)` 保证请求重放幂等；
- 用数据库部分唯一索引禁止同一会话同时存在两个 queued/running run；
- 把 provider 工作放在独立 task 中，SSE 连接只负责读取已保存事件；
- 为每帧分配连续正整数 `seq`，保存后才交给订阅者；
- 保存 completed/failed/cancelled 终态，处理取消、重启协调和七天默认事件保留期；
- 在成功终态之后用独立数据库会话维护滚动摘要。

这不是多 Agent 调度器，也没有自动重新执行失败轮次。重启时自动重放模型或写工具会带来
重复副作用风险，因此 D 明确选择“保存原输入、显示 interrupted、由用户决定是否重试”。

### 数据模型与迁移

迁移 `d295e6f7a8b9` 新增 `agent_runs`、`agent_run_events`，并给 assistant message
增加可空 `run_id`。旧消息保持 `NULL`，没有改写正文。Workflow 的 `execution_runs` 没有复用：
它表示创作 stage/skill 执行，聊天轮次需要 request 幂等、SSE 序号、取消与消息关联，两者语义不同。

核心约束是：

- 每会话/请求键唯一；
- 每会话最多一个活动 run；
- 每 run/seq 唯一；
- 会话删除级联删除 run，run 删除级联删除事件；
- 所有字段和索引由 ORM、迁移与 OpenAPI 同步描述。

### `chat.py` 与 `tools.py`

聊天核心现在可以使用已经持久化的 user message，assistant message 会记录来源 run。
durable run 不在工具调用时立即把 pending ORM 行 flush 到 SQLite，而是先放在本轮内存列表，
在最终 assistant message 提交前统一插入。这样同时满足两件事：

1. 保留 C 的原子性：回答失败时 pending 不会单独留下；
2. provider 网络等待和事件保存期间不持有 SQLite 写锁。

这个处理来自实际测试发现：若 pending 提前 flush，主轮次会持有写锁，独立事件会话保存下一帧时
发生自锁。它不是性能微调，而是 D 的可恢复事件通道与 C 的原子提交必须同时成立的边界设计。

### HTTP 与前端 store

API 新增运行查询、按 request 查找、最新 run、事件列表、续流和取消端点。`POST /agent/chat`
仍返回 SSE，但内部先创建/复用 run，再订阅持久事件。

前端为每次发送生成 request id，记录当前会话的 run id 和最后序号。正常流、EOF 后补偿、刷新续流
都经过同一服务器状态。异步 finally 只有在 project 与 run 仍归当前请求时才能清理状态，所以旧项目
的迟到收尾不会清空新项目的流。项目切换、删除会话和显式停止都会请求服务端取消。

## 异常与资源稳定性

- 取消先落库后取消 task；取消发生在 provider await 中时，生成器由 `aclosing` 释放。
- run event 写入有每 run 的进程内锁，避免取消与正常事件同时争用同一序号。
- shutdown 先停止 Agent tasks、关闭 provider，再分别关闭资产库和主库；一个 owner 的关闭异常
  会记录但不阻止其他 owner 清理。
- assistant 已提交但 run 终态尚未提交的极短 crash gap，可借 assistant 的 `run_id` 在启动时
  恢复 completed；没有最终回复的活动 run 转为 failed。
- 事件默认保留七天，可通过环境配置调整；原始消息和 run 终态不依赖事件保留。

## 数据库升级证据

真实数据库从 `c184d5e6f7a8` 升级到 `d295e6f7a8b9`。升级前先复制原库并在副本演练：

- 备份：`backend/data/backups/agent-d-20260914-1736-before.db`
- 演练副本：`backend/data/backups/agent-d-20260914-1736-rehearsal.db`
- 原库 SHA-256：`9FC1E02AC75FB5792320C46E8AE8FD2B62A1146CA448A850B3820D37AF185EE7`
- 演练后 `PRAGMA integrity_check = ok`，外键错误 0；
- 旧表行数前后一致：projects 4、entities 194、relationships 208、conversations 7、
  messages 17、memory_docs 1、memory_doc_sections 4、pending writes 0；
- 实际库升级后同样为 `integrity_check = ok`、外键错误 0，旧表行数一致。

备份是恢复材料，不应在已有 D 新数据后直接覆盖实际库；恢复前必须先评估新增 run/message。

## 验证结果

- 全部 Agent 后端单元、集成、迁移和 E2E：220 passed；
- D 专项覆盖：幂等重放、连续序号、状态/事件查询、服务端取消、迁移存量保护；
- 前端 store 与 Agent 集成：41 passed；
- Ruff check/format、Agent/main/config mypy、16 条 import-linter contract：通过；
- 前端 TypeScript 和定向 ESLint：通过；
- OpenAPI 重新导出并生成 TypeScript 后哈希不变，证明提交中的 schema 已同步；
- `git diff --check`：通过。

测试使用临时数据库和脚本 provider，没有调用真实计费模型，也没有运行 mutation、benchmark 或
全仓测试。一个旧 E2E 同时覆盖预算与多写工具，D 收口时把它改为显式足够预算，并先执行
`read_doc_section` 取得 C 所要求的真实版本；没有放宽产品默认预算或绕过 stale-write 保护。

## 尚未完成

D 保证“运行和原文不会因连接/维护故障静默丢失”，不保证自然语言摘要完整保留否定、数值、
未决任务等语义。摘要覆盖范围、关键状态抽取、原文按来源恢复和 cursor 损坏处理属于 E，当前应
停在该边界，不把 D 的持久 run 宣称为完整长期记忆。
