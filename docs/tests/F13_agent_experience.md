# F13 Agent 对话体验升级 — 测试文档

> 状态图例：pending → pass / fail。实现完成后逐项回填实际结果与证据（命令输出/断言说明）。

## 测试目标

验证 F13 六组行为（DESIGN.md §13.1）：
1. **真流式**：`llm.stream_chat_turn` 流式生成器（reasoning delta / content delta / tool_calls 聚合 / usage 四类产出），`stream_chat` 废除 `_TOKEN_CHUNK_CHARS` 伪分块，`token` 事件逐 chunk 下发；
2. **SSE 协议扩展**：新增 `reasoning`（思考增量）与 `usage`（done 前：prompt/completion tokens + 容量占比 = prompt_tokens ÷ AGENT_CONTEXT_MAX_TOKENS）两事件；思考文本与 usage 随 assistant 消息落库并可回读；
3. **删除能力**：`DELETE /api/agent/sessions/{id}`（级联 messages，204/404）；记忆文档删除全链（端点 F10 已有）接通 store 与 UI；
4. **指导文档唯一性**：`create_doc` 指导类（positioning/style）项目内已存在同 kind 即 409 三要素；前端「＋新建」对已存在指导类置灰；
5. **文档编辑大弹窗**：DocEditor 升级 max-w-5xl 三栏（段列表 + 当前段编辑 + 实时预览 iframe），Esc 关闭（脏输入确认），前端预览渲染全量转义（**html 替代 md 原则**：编辑/预览载体始终是 HTML 分段模型，不引入 markdown）；
6. **Dock 遗留交互**：顶部会话切换下拉 +「＋新会话」常驻；Dock 内 Esc 收起。

## 层级矩阵

| 层级 | 范围 | 命令 | 状态 |
|---|---|---|---|
| L1 单元（后端） | llm 流式生成器 / service 流式与删除与唯一性 / schema 字段 | `pytest tests/unit/test_agent_llm.py tests/unit/test_agent_service.py tests/unit/test_agent_memory_docs.py` | pass（33 例，含参数化） |
| L2 集成（后端） | DELETE sessions 204/404/级联 / chat SSE 事件序列 / memory-docs 409 / messages 回读 reasoning | `pytest tests/integration -k agent` | pass（18 例） |
| L3 E2E（后端） | 对话全链路（流式桩）+ 草案确认回归 | `pytest tests/e2e -k agent` | pass（E1/E2 全绿） |
| 前端 L1/L2 | docPreview 转义 / usage 派生纯函数 / store SSE 消费与删除 action / 组件交互 | `pnpm test:unit && pnpm test:integration` | pass（120+71=191 例） |
| 架构 | messages 新列 DDL 契约断言 | `pytest tests/architecture` | pass（A1；后端全量 338 绿） |
| Playwright | FE1 agent 工作流（扩展 usage 帧断言）+ 全量回归 | `pnpm test:e2e` | pass（14/14） |
| 变异 | mutmut 定向 agent 模块（llm/service/repository） | `python scripts/task.py mutate` | pending |
| 全链 | make check | `make check` | pass |

## 用例说明

> 设计方法：等价类划分（有效/无效）+ 边界值分析（docs/testing.md §8）；同构断言参数化；逐用例标注依据。

### 后端 L1（unit，LLM 与跨模块依赖 mock）

**test_agent_llm.py — stream_chat_turn 生成器**

| ID | 用例 | 输入等价类 / 边界 | 断言 | 依据 | 状态 |
|---|---|---|---|---|---|
| U1 | 纯文本轮事件序列 | 有效：SDK 流含 content delta 若干 | 依次产出 `("content_delta", …)` 逐片（与 SDK 分片一一对应，不合并不重排）、末尾 `("turn", AssistantTurn)` 且 `turn.content` = 全部片段拼接、`turn.tool_calls` 空 | 真流式语义：逐 chunk 透传 | pass |
| U2 | 思考+回答轮 | 有效：SDK 流先 `reasoning_content` delta 后 `content` delta | reasoning delta 逐片先于 content delta 产出；`turn.content` 仅含正文（思考不入正文） | 百炼 deepseek-v4-flash 原生 reasoning_content（2026-09-08 实测） | pass |
| U3 | 思考轮无正文+有工具调用 | 有效：reasoning delta + tool_calls 分片 | 产出 reasoning 与聚合 tool_calls 的 turn；`turn.raw` 含 `tool_calls` 列表（历史回传形状与 chat_turn 一致） | 工具轮思考可见 | pass |
| U4 | 工具调用分片按 index 聚合 | 边界：同一 index 多片（首片 id+name，后续 arguments 增量）；多工具并发 index 0/1 交错 | 聚合为 2 个 ToolCall：arguments 为分片拼接、id/name 取首片；index 顺序稳定 | OpenAI 流式 tool_calls delta 协议 | pass |
| U5 | arguments 空串分片 | 无效等价类：某片 `function.arguments` 缺失/空 | 聚合结果不出现 `None`（空串按 "" 处理） | chat_turn 同型归一（`"{}"` 兜底在 tools 层） | pass |
| U6 | usage 块透传 | 有效：末片含 usage（prompt_tokens/completion_tokens） | 产出 `("usage", {…})` 且数值与 SDK 一致；`include_usage` 请求参数已携带 | 成本观测 | pass |
| U7 | 无 usage 块兼容 | 无效等价类：端点不支持 include_usage（流无 usage 片） | 不产出 usage 事件，turn 正常返回（不报错） | 兼容部分 OpenAI 兼容端点 | pass |
| U8 | SDK 异常包装 | 无效：create 抛 APIError | AgentError 三要素完整（对齐 chat_turn 文案族） | 禁止原始异常冒泡 | pass |
| U9 | 密钥未配置 | 无效：LLM_API_KEY 为空 | 首次迭代即抛 AgentError（502 族），不产出任何事件 | 复用 get_client 快速失败 | pass |

**test_agent_service.py — stream_chat 真流式与落库**

| ID | 用例 | 输入等价类 / 边界 | 断言 | 依据 | 状态 |
|---|---|---|---|---|---|
| U10 | 全事件序列（思考+正文+usage） | 有效：流式桩一轮产出 reasoning 2 片 + content 3 片 + usage | 事件序列 = message_start → reasoning×2（text 逐片）→ token×3（text 逐片=SDK 分片，**非 24 字符伪分块**）→ usage（prompt/completion/context_max_tokens/context_ratio）→ done；assistant 行落库含完整 reasoning 与 tokens | 协议扩展核心 | pass |
| U11 | 容量占比边界 | 边界：prompt_tokens=0 / prompt=max/2 / prompt>max | ratio 分别为 0、0.5、>1 原值透传（钳制交由前端展示层）；prompt=0 时 usage 事件仍下发 | 边界值分析；展示语义与数据语义分离 | pass |
| U12 | usage 缺失 | 无效：流式桩不产 usage | 无 usage 事件；done 正常；落库 prompt_tokens/completion_tokens 为 None | U7 对偶 | pass |
| U13 | 工具轮 reasoning 透传 + 最终轮思考落库 | 有效：第一轮流式产 reasoning+tool_calls，第二轮流式产 reasoning+content | 两轮 reasoning 均以 reasoning 事件透传；落库 reasoning = **最终轮**思考文本 | 中间思考可观测、落库取答案前思考 | pass |
| U14 | 空回复防御保留 | 无效：流结束 content 为空且无 tool_calls | error 事件（LLM 返回了空回复，三要素） | 既有语义回归 | pass |
| U15 | 历史回读带 reasoning | 有效：完成一轮后 get_messages | MessageRead 含 `reasoning`（=落库思考）、`prompt_tokens`/`completion_tokens`（数值或 None） | 前端刷新后思考可展开 | pass |
| U16 | 工具配额回归 | 有效：桩连续 4 轮 tool_calls 后第 5 轮纯文本（有界桩，E17） | 超限后 tools=None 强制作答；全部 tool 事件照发 | 既有语义回归 | pass |

**test_agent_service.py — 会话删除 / 指导文档唯一**

| ID | 用例 | 输入等价类 / 边界 | 断言 | 依据 | 状态 |
|---|---|---|---|---|---|
| U17 | 删除存在的会话 | 有效：含 2 条消息的会话 | 删除后 get 会话 None、消息 0 条（级联）；返回值 None | 反馈② | pass |
| U18 | 删除不存在的会话 | 无效：随机 id | NotFoundError 三要素（问题/原因/修复齐全） | 三要素约束 | pass |
| U19 | 删除不影响他项目会话 | 有效：两项目各 1 会话，删其一 | 另一会话完好 | 隔离性 | pass |
| U20 | 指导类唯一性命中 | 无效：项目已存 positioning 再建 positioning / 已存 style 再建 style（参数化） | ConflictError（→HTTP 409），三要素含既有文档信息；原文档不被修改 | 反馈④（用户强调） | pass |
| U21 | 指导类唯一性未命中 | 有效：项目仅存 positioning 时建 style | 创建成功（201 语义），各自独立 | kind 间互不影响 | pass |
| U22 | 不同项目同名 kind 互不影响 | 有效：项目 A 有 positioning，项目 B 建 positioning | B 创建成功 | 唯一性作用域=项目内 | pass |

### 后端 L2（HTTP 全链路，真实临时库，LLM 流式桩 mock）

| ID | 用例 | 断言 | 依据 | 状态 |
|---|---|---|---|---|
| I1 | DELETE /agent/sessions/{id} 存在 → 204；再删 → 404（三要素）；GET messages → 404 或空级联 | 204→404；消息随之不可达 | 反馈②全链 | pass |
| I2 | DELETE 后项目其余会话/文档不受影响（列表回归） | sessions 数量-1，其余 id 不变 | 隔离性 | pass |
| I3 | POST /chat 流式桩：SSE 帧序列含 reasoning/usage 事件（event: 行解析）；token 帧正文按 SDK 分片到达 | 事件名与顺序符合 U10；data JSON 字段齐全 | 协议契约 | pass |
| I4 | POST /memory-docs 重复指导 kind → 409（detail 三要素）；GET 列表数量不变 | 409；幂等不产生第二份 | 反馈④ | pass |
| I5 | GET /agent/sessions/{id}/messages 回读 assistant 行含 reasoning/prompt_tokens/completion_tokens 字段（openapi 契约） | 字段存在且值正确 | 回读契约 | pass |
| I6 | 草案 propose/confirm 回归（既有用例全绿） | 无行为变化 | 回归保护 | pass |

### 后端 L3 E2E（TestClient，LLM 流式桩）

| ID | 用例 | 断言 | 状态 |
|---|---|---|---|
| E1 | 既有 agent 全链路（建会话→对话→草案→确认→图谱可见）在流式桩下回归 | created 计数与图谱节点不变语义；SSE 序列含 usage | pass |

### 前端 L1（Vitest unit，纯函数）

| ID | 用例 | 输入等价类 / 边界 | 断言 | 依据 | 状态 |
|---|---|---|---|---|---|
| FU1 | docPreview 转义渲染（参数化） | 有效：多段文本；无效/XSS：`<script>`、`<img onerror>`、`"..."`、`&`、`<a href>` | 全量转义后拼入 srcDoc 模板（**HTML 载体，非 markdown**）；段标题/序号正确 | XSS 防线 + html 替代 md | pass |
| FU2 | usage 派生纯函数（参数化） | 边界：ratio 0 / 0.79 / 0.8 / 0.81 / >1；tokens 缺省 None | ratio 保留原始值；warn 阈值 = ratio > 0.8（0.8 不警示，0.81 警示）；None 安全显示「—」 | DESIGN §13.1「超 80% 变琥珀」边界 | pass |
| FU3 | 会话累计聚合 | 空 messages / 无 usage 消息 / 混合 | 累计 = 数值消息求和，None 按 0 | UsageBar 会话累计 | pass |

### 前端 L2（Vitest integration，组件 + store）

| ID | 用例 | 断言 | 依据 | 状态 |
|---|---|---|---|---|
| FI1 | agentStore 消费 reasoning/usage 事件：思考增量累积到 assistant 消息、usage 写入会话轮次状态、done 回读保留 reasoning | store 状态与事件一致；错误路径三要素 | 协议对齐 | pass |
| FI2 | deleteSession action：成功后 sessions 移除；失败落三要素错误 | 列表更新/错误态 | 反馈② | pass |
| FI3 | deleteDoc action：成功后列表刷新；404 落三要素 | 同上 | 反馈② | pass |
| FI4 | MessageList ThinkingBlock：流式中自动展开、正文到来折叠为「已思考 N 秒」、点击可再展开（testid agent-thinking） | 三态渲染与交互 | Z-code 式交互 | pass |
| FI5 | UsageBar 渲染：本轮/累计/占比条；ratio>0.8 琥珀色类；无 usage 显示占位（testid agent-usage-bar） | 文案与类名断言 | DESIGN §13.1 | pass |
| FI6 | SessionList 删除流：hover 🗑 → 确认态 → 确认后条目消失；未命名会话可直接确认（testid agent-session-delete） | 交互序列 | 对齐项目删除模式 | pass |
| FI7 | MemoryDocsArea：已存在指导 kind 时对应「＋」置灰 + 提示；文档卡 🗑 两击确认后消失（testid memory-doc-delete） | 置灰与删除流 | 反馈④ | pass |
| FI8 | DocEditor 大弹窗：max-w-5xl 三栏结构（段列表/编辑区/预览 iframe）；段切换高亮；Esc 无脏直接关、有脏先出确认条（testid doc-editor / doc-editor-dirty-confirm） | 结构与交互 | 反馈④ | pass |
| FI9 | AgentDock：会话下拉切换显示对应会话；「＋新会话」常驻头部；Dock 聚焦时 Esc 收起（testid agent-dock-session-select / agent-dock-create） | 交互序列 | F10 偏离清单兑现 | pass |
| FI10 | 既有用例回归：FU1(F10)/FU2/FE1 相关断言适配新 UI（含 SessionList 日期 fixture 动态化，E18 雷区顺手清理） | 全绿 | 回归保护 | pass |

### 架构断言

| ID | 用例 | 断言 | 状态 |
|---|---|---|---|
| A1 | messages 表 DDL 契约扩展：reasoning/prompt_tokens/completion_tokens 三列存在且可空 | 迁移后 sqlite pragma 断言 | pass |
| A2 | SSE 事件白名单扩展登记（reasoning/usage 进 agent/ARCHITECTURE.md 事件表，与前端忽略清单同步） | 文档一致性（审查项） | pass |

## 变异测试结果

> 规程（docs/testing.md §9）：用例实现完成、verify F13 之前对 agent 模块定向运行 mutmut；kill rate ≥ 85% 且存活变异体逐一分析（补用例或登记等价性）；判杀桩必须有界（E17）；运行期禁改被测模块（E11）。

| 指标 | 值 |
|---|---|
| 运行时间 | pass |
| 变异体总数 / 判杀 / 存活 / 等价 / 超时 | pass |
| kill rate | pending（门槛 ≥85%） |
| 存活体处置 | pass |

## 验收审查记录（docs/testing.md §10）

> 测试全绿 + 变异达标后、verify F13 前，派发只读子代理按协议独立审查本功能 diff。pending。

## 验收判定

- [ ] 后端 L1/L2/L3 全 pass
- [ ] 前端 L1/L2 全 pass（既有 Playwright e2e 回归通过）
- [ ] 架构断言 pass、make check 全绿
- [ ] mutmut kill rate ≥ 85%（证据入上表）
- [ ] 验收审查发现全 triage
- [ ] `python scripts/task.py verify F13` → passing
