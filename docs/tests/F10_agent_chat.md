# F10 Agent 对话与确认写入 — 测试文档

## 测试目标

验证 Agent 对话底座：会话/消息/记忆文档持久化（按项目隔离）、SSE 流式对话（上下文经视角过滤组装 + 受控工具检索 + 预算裁剪）、propose 结构化草案与 confirm 两段式落库、HTML 分段记忆文档（段级编辑/段级 patch/CAS 冲突消解）、前端 AgentHome + AgentDock 同一会话池（SSE 会话级生命周期）。

设计基线: DESIGN.md §5.4/§5.5（Agent 界面）/§8.3（数据蓝图）；docs/tests/F10 规划（2026-09-06 用户决策：F10 底座 / F13 创作工作流拆分、轻量 ReAct 内环、记忆文档两段式、内置三防线+合规 hook、HTML 分段模板取代 OQ-2 markdown 方案）。

## 层级矩阵

| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1–U24: llm 封装 / prompts 组装 / tools 检索 / memory_docs / service | backend/tests/unit/test_agent_llm.py、test_agent_prompts.py、test_agent_tools.py、test_agent_memory_docs.py、test_agent_service.py | 必须 | pending |
| L2 集成 | I1–I11: agent API 全链路（真实临时库，LLM mock） | backend/tests/integration/test_agent_api.py | 必须 | pending |
| L3 E2E | E1–E2: 对话→草案→确认→图谱 / 用户手改记忆文档后 agent 读新 | backend/tests/e2e/test_agent_flow.py | 必须（跨 agent+entities+relations+perspectives+projects） | pending |
| L1/L2 前端 | FU1–FU2: agentStore 事件归约 / AgentHome+确认卡组件 | frontend/tests/unit/stores/agentStore.test.ts、frontend/tests/integration/AgentHome.test.tsx | 必须 | pending |
| L3 前端 | FE1: Playwright agent 对话工作流（SSE mock 路由拦截） | frontend/e2e/agent.spec.ts | 必须（跨前后端联调） | pending |

说明: features.md 的 L1 验证命令锚定 `tests/unit/test_agent_service.py`（变异门禁 L1 定位约定）；L1 全集为 `tests/unit/test_agent_*.py` 五个行为文件（命名规范 `test_<模块>_<行为>.py`，docs/testing.md §6），make test 全量执行。

## 用例说明

### 后端 L1（service 层，LLM 与跨模块依赖 mock）

**test_agent_llm.py（LLM 客户端封装）**

- U1: chat 补全成功 → 返回文本且 usage（prompt/completion tokens）被记录（设计依据：等价类-有效调用）
- U2 参数化: 端点失败三型 timeout / APIError / 连接失败 → 均 AgentError，三要素完整文案与 detail 整体相等（E05 范式）（设计依据：等价类-无效-失败模式三分类同构断言）
- U3: JSON 草案解析失败 → 修复重试 1 次后成功返回结构（设计依据：边界值-重试恰 1 次）
- U4 参数化: JSON 草案两次解析失败 → ValidationError；非法 kind / 超出白名单字段 → ValidationError（设计依据：边界值-重试上限+1 次 0 次成功；等价类-无效-schema 违约）
- U5: 摘要等辅助调用路由到轻量模型（llm_model_light）（设计依据：等价类-模型路由分支）

**test_agent_prompts.py（上下文组装）**

- U6: 组装分层顺序 = system → 文档段 → 图谱目录 → 会话摘要 → 近期消息（前缀缓存友好契约）（设计依据：等价类-分层顺序唯一正确序）
- U7: 图谱目录紧凑渲染——类型分组、含 id/name/aliases、不含 properties/description（设计依据：等价类-目录投影收窄）
- U8: 文档目录含段标题 + 内容 hash；内容不变 hash 稳定，内容变 hash 变（设计依据：等价类-hash 函数契约 + 边界-空段）
- U9 参数化: 预算裁剪——总 tokens 恰好不超限（不裁）/ 超 1（裁最旧消息）/ 极小预算（消息全裁、文档降级为目录、system 保留）（设计依据：边界值-预算上下界与邻界）
- U10: 文档段与工具输出经注入分隔符包裹，system 含「数据非指令」声明（设计依据：等价类-防护结构必须存在）
- U11: character 视角组装输入（已过滤 GraphData）只含可见实体——组装函数不产生任何直查库旁路（设计依据：等价类-输入契约；端到端泄露断言在 I4）

**test_agent_tools.py（检索工具与配额）**

- U12: get_entity_detail 有效可见 id → 完整属性；不可见 id → PerspectiveError（设计依据：等价类-有效/无效-视角不可见）
- U13: get_neighborhood 返回一度关系且仅可见边（设计依据：等价类-邻域投影）
- U14 参数化: search_entities 命中名称 / 命中别名 / 空结果（设计依据：等价类-检索命中三分支）
- U15 参数化: read_doc_section 有效 seq / seq 越界（0、len+1）→ NotFoundError（设计依据：边界值-序号两侧邻界）
- U16: 工具调用配额——第 K 次成功、第 K+1 次被拒（K=config 值）（设计依据：边界值-配额恰好/超 1）
- U17: 超长工具输出截断到上限并带截断标记（设计依据：边界值-输出长度上限）

**test_agent_memory_docs.py（记忆文档段级模型）**

- U18: 按模板新建文档 → 初始段生成（世界观定位 / 风格约定两 kind）（设计依据：等价类-有效模板）
- U19: 用户段级保存 → 该段更新、version+1、updated_by=user、其余段不动（设计依据：等价类-段级隔离写入）
- U20: agent patch 确认——CAS 版本一致 → 落库 updated_by=agent；版本不一致 → ConflictError 且原段未被覆盖（设计依据：等价类-并发冲突两态，核心边界语义）
- U21: HTML 渲染自包含且全转义——`<script>`/引号/尖括号注入均被转义，无未转义插值（设计依据：等价类-无效-注入载荷）
- U22: read_doc_section 返回单段全文（供工具复用）（设计依据：等价类-有效读取）

**test_agent_service.py（对话/草案/确认主链路）**

- U23: stream_chat 正常流（mock 流式 LLM）→ 事件序列 token…done、完成后 user/assistant 消息落库、会话 updated_at 前进（设计依据：等价类-有效会话轮）
- U24 参数化: 历史窗口——消息数恰在窗口内（全量注入）/ 超 1 条（最旧压缩进摘要）/ 摘要增量更新落 conversations.summary（设计依据：边界值-窗口两侧邻界）
- U25: propose 有效描述 → list[Draft]（draft_id 系统生成、kind/payload/summary 齐全）；LLM 不可用 → AgentError（设计依据：等价类-有效/无效-端点失败）
- U26: confirm_write 确认项经 entities/relations service 落库、放弃项跳过；单项落库失败 → failed 列表含 draft_id+reason，其余成功（设计依据：等价类-部分失败）
- U27: 会话标题取首条用户消息截断（边界值：恰为上限/超上限 1 字符）（设计依据：边界值-标题长度）
- U28: 内容合规 hook 开启且命中敏感词 → AgentError 三要素；关闭 → 不拦截（设计依据：等价类-开关两态）

### 后端 L2（HTTP 全链路，真实临时库，LLM monkeypatch mock）

- I1: POST /api/agent/sessions（project_id）→ 201 会话落库；GET sessions 列表按项目过滤——双项目互不可见（设计依据：等价类-项目隔离）
- I2: chat SSE 全链路 → 事件流含 message_start/token/done，messages 表新增 user+assistant 两行（设计依据：等价类-有效流式轮）
- I3 参数化: **视角过滤注入断言（关键安全用例）**——author/character/audience 三视角下 chat，捕获发往 LLM 的 prompt：character 视角下不可见实体的名称与描述不出现在 prompt，可见实体出现；author 全量；audience 仅 audience_known（设计依据：等价类-三视角正交，E05 范式钉死包含/排除集合）
- I4: propose → 响应草案列表 → confirm → entities/relationships 真实落库 → GET /api/entities|graph 可查（两段式闭环）（设计依据：等价类-有效链路）
- I5: confirm 携带服务端已失效/非法 payload → 422 ValidationError（不信任前端，服务端复核）（设计依据：等价类-无效-篡改载荷）
- I6: memory-docs: 新建（模板段）→ GET 列表 → PATCH 段（version 递增）→ 并发 CAS 冲突 PATCH 旧 version → 409 且内容未变（设计依据：边界值-version 恰好/差 1）
- I7: GET memory-docs/{id}/page → text/html 自包含且载荷转义（设计依据：等价类-输出安全）
- I8: 删除项目（级联）→ 该项目 conversations/messages/memory_docs 同步清理，他项目不受影响（设计依据：等价类-级联边界）
- I9: 跨项目访问会话/记忆文档（A 项目 id 访问 B 项目资源）→ 404（设计依据：等价类-无效-越权归属）
- I10 参数化: LLM 未配置（api_key 空）/ 端点超时 → 502 AgentError 三要素完整（设计依据：等价类-无效-降级两态）
- I11: 工具检索轮——chat 中 LLM 请求工具（mock 返回 tool_call）→ tool 事件推送 + 配额超限拒绝 + 结果进入上下文（设计依据：等价类-受控 ReAct 循环）

### 后端 L3 E2E（TestClient 公开接口，跨模块）

- E1: 对话→草案→确认→图谱全链路（LLM mock）：建会话 → chat 提及新角色 → propose 产实体草案 → confirm → /api/graph 出现新节点（跨组件理由：agent+entities+relations+perspectives+projects 协作）
- E2: 用户手改记忆文档段 → 下一轮 chat 的 LLM prompt 以新内容为准（hash 目录变化）；agent patch 基于旧版本提交 → 409 冲突不覆盖（跨组件理由：记忆冲突边界语义端到端验证）

### 前端 L1/L2（Vitest）

- FU1: agentStore——SSE 事件归约（token 追加/draft 入列/doc_patch 入列/ask_user 占位/error 三要素/done 终态）、streamingSessionId 会话级生命周期（切会话/收起 Dock 不断流、显式 abort 可停）、confirm 成功后广播图谱失效事件（设计依据：等价类-事件类型全集 + 边界-中断路径）
- FU2: AgentHome——会话列表分组与新建、空状态引导卡、记忆文档卡片区（新建两模板）、DraftConfirmCard 确认/放弃、DocPatchCard diff 确认、DocEditor 段级表单保存；AgentDock 开合与 z-index 契约（设计依据：DESIGN §5.4/§5.5 基线 + 等价类-空/非空会话集）

### 前端 L3（Playwright，SSE 经路由拦截 mock）

- FE1: agent 工作流——进入 Agent 页 → 新建会话 → 发送消息（mock 流式回复）→ 草案卡确认 → 提示已写入 → 打开记忆文档编辑段保存（设计依据：DESIGN §6 剧本 C 前半链路）

## 变异测试结果（用例实现完成后填写）

- scope（被测模块）: backend/app/agent/（待运行）
- 判杀器: L1 tests/unit/test_agent_*.py + L2 tests/integration/test_agent_api.py + 架构测试（§9 层级覆盖：模块含 router 必须 L2；L3 视存活体分析决定是否追加）
- kill rate / 存活变异体分析: 待填写

## 验收判定

所有「必须」层级通过 + 状态列全 pass + 变异测试达标（kill rate ≥ 85%，§9）+ make check 通过 → 功能完成。
