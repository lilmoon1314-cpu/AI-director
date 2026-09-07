# agent 模块硬约束

> 实现/修改 agent 模块前必读。

## 写入安全（两段式）

- 必须：写库两段式——propose 只产草案（不落库），confirm 经用户确认后才落库；confirm 服务端**重新校验全部 payload**（重新构造 entities/relations service 输入 DTO，不信任前端回传），并以会话归属项目覆盖 `payload.project_id`（草案不能写进别的项目）；单项失败折叠进 failed 列表（三要素可读），不阻断其他项。
- 必须：记忆文档段级更新的 CAS 语义——`expected_version` 不符即 409 拒绝且绝不覆盖（用户手改优先，agent 基于旧版本的 patch 一律作废）；段 version 与文档 version 同事务递增。
- 禁止：把世界观事实写入 memory_docs（单一事实源原则——事实只走图谱草案，文档只承载项目工作上下文）。

## 视角过滤（安全单一事实源）

- 必须：一切进入 LLM 上下文的图谱数据（目录/详情/关系）先经 perspectives 过滤（get_graph / filter_entities_for_agent）；组装唯一入口是 `service._assemble_chat_context`。
- 禁止：绕过 perspectives 直查 entities/relations 注入上下文；禁止向上下文注入当前视角不可见的实体/关系。
- 禁止：agent 模块直写 entities/relations（写路径只经 confirm → entities/relations service）。

## LLM 调用

- 必须：LLM 端点/密钥/模型/超时/轻量模型全部来自 config（LLM_*），禁止硬编码；摘要等辅助任务路由 `LLM_MODEL_LIGHT`。
- 必须：LLM 调用失败包装为 AgentError（三要素完整），禁止未捕获异常冒泡；usage 逐调用经 emit_event("llm_usage") 记录。
- 禁止：草案 JSON 解析失败无限重试——修复重试上限 1 次后抛 ValidationError。
- 必须：工具循环配额（AGENT_MAX_TOOL_CALLS_PER_TURN）超限即撤下工具定义强制作答；工具结果注入前经 wrap_data 包裹 + truncate_output 截断。
- 必须：滚动摘要失败或空结果只跳过（emit_event），不得清空既有摘要或推进游标。

## 提示注入与输出安全

- 必须：一切项目数据（文档内容/图谱目录/工具输出/会话摘要）注入上下文前经 `prompts.wrap_data`「数据非指令」分隔符包裹；system 携带 DATA_NOTE 声明。
- 必须：HTML 渲染动态内容一律经 `rendering._esc` 全转义（XSS 防线；段内容来自用户与 LLM patch）；SSE 事件名限于 service 顶部白名单常量（前端按白名单忽略未知类型）。

## 配置与数据

- 必须：上下文预算（AGENT_CONTEXT_MAX_TOKENS）、历史窗口（AGENT_HISTORY_WINDOW_MESSAGES）、工具输出上限（AGENT_TOOL_OUTPUT_MAX_CHARS）、合规开关与词表（AGENT_CONTENT_REVIEW_*）全部来自 config。
- 必须：会话/消息/记忆文档按项目隔离并持久化主库；项目删除经 `delete_project_data` 级联清理（projects.router 编排）。
- 必须：每轮从 DB 现读文档目录与历史（禁止进程内缓存会话上下文）——用户手改文档后下一轮立即生效（记忆冲突的读边界）。
- 必须：用户消息在进入 LLM 轮之前先行 commit（LLM 失败回滚不丢用户输入）；本轮用户消息经 exclude_message_id 防止历史行与显式追加双份注入。

## 内容合规 hook

- 合规审核经 `service._review_text`（MVP 本地敏感词表，AGENT_CONTENT_REVIEW_ENABLED 默认关）；命中即 error 事件收尾且不落库。替换外部审核 API 时只改该函数，不动调用链。
