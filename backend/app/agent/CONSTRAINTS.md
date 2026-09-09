# agent 模块硬约束

> 实现/修改 agent 模块前必读。

## 写入安全（F14 写入工具链为主路径 + legacy 草案两段式）

- 必须：写入类工具（create_entity/update_entity/create_relation/create_memory_doc/write_doc_section）
  执行 ≠ 落库——仅登记 `agent_pending_writes`（pending，随对话轮事务提交/回滚）；落库只发生在
  `approve_pending_writes`（作者在确认卡批准后）。轮内登记上限 `AGENT_MAX_PENDING_WRITES`（config）。
- 必须：approve 服务端**逐项二次校验**（按类别白名单重建 entities/relations/agent service 输入 DTO，
  不信任登记载荷与前端回传），并以会话归属项目覆盖 `project_id`；单项失败保持 pending 进 failed
  （三要素可读），不阻断其他项；非 pending 状态（approved/rejected）拒绝再次 approve（fail closed）。
- 必须：`write_doc_section` 的段级 CAS——登记时记录 section_id + expected_version 基线，approve 经
  `update_section` 复核；作者在确认前手改该段即版本冲突拒绝且绝不覆盖（用户手改优先，登记作废重读）。
- 必须：写入工具的目标解析（create_relation 端点与 known_by、update_entity 目标名称快照）经
  perspectives 视角过滤放行——不可见实体拒绝登记，存在性不向 LLM 上下文泄露。
- 必须：legacy 草案路径——propose 只产草案（不落库），confirm 经用户确认后才落库；confirm 服务端
  重新校验全部 payload（重新构造 entities/relations service 输入 DTO，不信任前端回传），并以会话
  归属项目覆盖 `payload.project_id`（草案不能写进别的项目）；单项失败折叠进 failed 列表（三要素
  可读），不阻断其他项。
- 必须：记忆文档段级更新的 CAS 语义——`expected_version` 不符即 409 拒绝且绝不覆盖（用户手改优先，
  agent 基于旧版本的 patch 一律作废）；段 version 与文档 version 同事务递增。
- 禁止：把世界观事实写入 memory_docs（单一事实源原则——事实只走图谱写入工具/草案，文档只承载
  项目工作上下文）。

## 视角过滤（安全单一事实源）

- 必须：一切进入 LLM 上下文的图谱数据（目录/详情/关系/写入工具的名称解析快照）先经 perspectives
  过滤（get_graph / filter_entities_for_agent）；组装唯一入口是 `service._assemble_chat_context`，
  写入登记的名称解析唯一入口是 `tools._resolve_entity_by_name`（search 精确匹配 → filter 放行）。
- 禁止：绕过 perspectives 直查 entities/relations 注入上下文；禁止向上下文注入当前视角不可见的实体/关系。
- 禁止：agent 模块直写 entities/relations（写路径只经 approve/confirm → entities/relations service）。

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

- 必须：上下文预算（AGENT_CONTEXT_MAX_TOKENS）、历史窗口（AGENT_HISTORY_WINDOW_MESSAGES）、
  工具输出上限（AGENT_TOOL_OUTPUT_MAX_CHARS）、轮内待写入上限（AGENT_MAX_PENDING_WRITES）、
  合规开关与词表（AGENT_CONTENT_REVIEW_*）全部来自 config。
- 必须：会话/消息/记忆文档/待写入登记按项目隔离并持久化主库；项目删除经 `delete_project_data`
  级联清理（projects.router 编排；登记行随会话 FK CASCADE 传导清理）。
- 必须：每轮从 DB 现读文档目录与历史（禁止进程内缓存会话上下文）——用户手改文档后下一轮立即生效（记忆冲突的读边界）。
- 必须：用户消息在进入 LLM 轮之前先行 commit（LLM 失败回滚不丢用户输入）；本轮用户消息经 exclude_message_id 防止历史行与显式追加双份注入。

## 内容合规 hook

- 合规审核经 `service._review_text`（MVP 本地敏感词表，AGENT_CONTENT_REVIEW_ENABLED 默认关）；命中即 error 事件收尾且不落库。替换外部审核 API 时只改该函数，不动调用链。
