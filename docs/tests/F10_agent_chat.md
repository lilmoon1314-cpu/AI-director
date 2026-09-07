# F10 Agent 对话与确认写入 — 测试文档

## 测试目标

验证 Agent 对话底座：会话/消息/记忆文档持久化（按项目隔离）、SSE 流式对话（上下文经视角过滤组装 + 受控工具检索 + 预算裁剪）、propose 结构化草案与 confirm 两段式落库、HTML 分段记忆文档（段级编辑/段级 patch/CAS 冲突消解）、前端 AgentHome + AgentDock 同一会话池（SSE 会话级生命周期）。

设计基线: DESIGN.md §5.4/§5.5（Agent 界面）/§8.3（数据蓝图）；docs/tests/F10 规划（2026-09-06 用户决策：F10 底座 / F13 创作工作流拆分、轻量 ReAct 内环、记忆文档两段式、内置三防线+合规 hook、HTML 分段模板取代 OQ-2 markdown 方案）。

## 层级矩阵

| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1–U31: llm 封装 / prompts 组装 / tools 检索 / memory_docs / service | backend/tests/unit/test_agent_llm.py、test_agent_prompts.py、test_agent_tools.py、test_agent_memory_docs.py、test_agent_service.py | 必须 | pass |
| L2 集成 | I1–I12: agent API 全链路（真实临时库，LLM mock） | backend/tests/integration/test_agent_api.py | 必须 | pass |
| L3 E2E | E1–E2: 对话→草案→确认→图谱 / 用户手改记忆文档后 agent 读新 | backend/tests/e2e/test_agent_flow.py | 必须（跨 agent+entities+relations+perspectives+projects） | pass |
| L1/L2 前端 | FU1–FU2: agentStore 事件归约 / AgentHome+确认卡组件 | frontend/tests/unit/stores/agentStore.test.ts、frontend/tests/integration/AgentHome.test.tsx | 必须 | pass |
| L3 前端 | FE1: Playwright agent 对话工作流（SSE mock 路由拦截） | frontend/e2e/agent.spec.ts | 必须（跨前后端联调） | pass |

说明: features.md 的 L1 验证命令锚定 `tests/unit/test_agent_service.py`（变异门禁 L1 定位约定）；L1 全集为 `tests/unit/test_agent_*.py` 五个行为文件（命名规范 `test_<模块>_<行为>.py`，docs/testing.md §6），make test 全量执行。

## 用例说明

### 后端 L1（service 层，LLM 与跨模块依赖 mock）

**test_agent_llm.py（LLM 客户端封装）**

- U1: chat 补全成功 → 返回文本且 usage（prompt/completion tokens）被记录（设计依据：等价类-有效调用）
- U2 参数化: 端点失败三型 timeout / APIError / 连接失败 → 均 AgentError，三要素完整文案与 detail 整体相等（E05 范式）（设计依据：等价类-无效-失败模式三分类同构断言）
- U3: JSON 草案解析失败 → 修复重试 1 次后成功返回结构（设计依据：边界值-重试恰 1 次）
- U3 补充参数化: 首轮合法输出四种形态（裸 JSON / 小写栅栏 / 大写栅栏 / 无语言标记栅栏）直接解析不触发修复轮（设计依据：等价类-有效-输出形态四分类；边界值-栅栏语言标记大小写两态）
- U4 参数化: JSON 草案两次解析失败 → ValidationError；非法 kind / 超出白名单字段 → ValidationError（设计依据：边界值-重试上限+1 次 0 次成功；等价类-无效-schema 违约）
- U5: 摘要等辅助调用路由到轻量模型（llm_model_light）（设计依据：等价类-模型路由分支）

**test_agent_prompts.py（上下文组装）**

- U6: 组装分层顺序 = system → 文档段 → 图谱目录 → 会话摘要 → 近期消息（前缀缓存友好契约）（设计依据：等价类-分层顺序唯一正确序）
- U7: 图谱目录紧凑渲染——类型分组、含 id/name/aliases、不含 properties/description（设计依据：等价类-目录投影收窄）
- U8: 文档目录含段标题 + 内容 hash；内容不变 hash 稳定，内容变 hash 变（设计依据：等价类-hash 函数契约 + 边界-空段）
- U9 参数化: 预算裁剪——总 tokens 恰好不超限（不裁）/ 超 1（裁最旧消息）/ 极小预算（消息全裁、文档降级为目录、system 保留）（设计依据：边界值-预算上下界与邻界）
- U10: 文档段与工具输出经注入分隔符包裹，system 含「数据非指令」声明（设计依据：等价类-防护结构必须存在）
- U11: render_entity_details 渲染实体完整字段（id/类型/名称/别名/简介/audience/properties；空列表占位说明）——详情注入的投影契约（视角输入契约的端到端断言由 I3 承担）（设计依据：等价类-投影全字段）

**test_agent_tools.py（检索工具与配额）**

- U12: get_entity_detail 有效可见 id → 完整属性；不可见/不存在 id → 静默剔除后返回占位说明文本（不抛异常，对话轮不打断）（设计依据：等价类-有效/无效-视角不可见）
- U13: get_neighborhood 返回一度关系且仅可见边；中心实体不可见 → 三要素错误文本（设计依据：等价类-邻域投影 + 无效-视角外中心）
- U14 参数化: search_entities 命中名称 / 命中别名 / 空结果（设计依据：等价类-检索命中三分支）
- U15 参数化: read_doc_section 有效 seq → 段全文；seq 越界（0、len+1）/ seq 非整数 / 跨项目 doc_id → 三要素错误文本（工具层失败折叠为文本，不抛异常）（设计依据：边界值-序号两侧邻界；等价类-无效-参数与归属）
- U16: 工具调用配额——配额内允许工具轮，超限后不再向 LLM 提供工具定义并强制作答（K=config 值；落点 test_agent_service.py stream_chat 工具循环用例）（设计依据：边界值-配额恰好/超 1）
- U17: 超长工具输出截断到上限并带截断标记（落点同 U16，同一用例内断言）（设计依据：边界值-输出长度上限）

**test_agent_memory_docs.py（记忆文档段级模型）**

- U18: 按模板新建文档 → 初始段生成（世界观定位 / 风格约定两 kind）（设计依据：等价类-有效模板）
- U19: 用户段级保存 → 该段更新、version+1、updated_by=user、其余段不动（设计依据：等价类-段级隔离写入）
- U20: agent patch 确认——CAS 版本一致 → 落库 updated_by=agent；版本不一致 → ConflictError 且原段未被覆盖（设计依据：等价类-并发冲突两态，核心边界语义）
- U21: HTML 渲染自包含且全转义——`<script>`/引号/尖括号注入均被转义，无未转义插值（设计依据：等价类-无效-注入载荷）
- U22: read_doc_section 返回单段全文（供工具复用）（设计依据：等价类-有效读取）

**test_agent_service.py（对话/草案/确认主链路）**

- U23: stream_chat 正常流（mock LLM）→ 事件序列 token…done、完成后 user/assistant 消息落库（设计依据：等价类-有效会话轮）
- U24: 历史窗口超窗（窗口=2，2 条历史+本轮 2 条=4 条）→ 溢出最旧 2 条增量压缩进 conversations.summary 且游标推进（设计依据：边界值-窗口两侧邻界）
- U25: propose 有效描述 → list[Draft]（draft_id 系统生成、kind/payload/summary 齐全）；LLM 不可用 → AgentError；畸形草案（drafts 非列表/kind 白名单外/payload 非对象）参数化 → ValidationError（设计依据：等价类-有效/无效-端点失败与 schema 违约）
- U26: confirm_write 确认项经 entities/relations service 落库、放弃项跳过；单项落库失败 → failed 列表含 draft_id+reason，其余成功；篡改 payload 构造 DTO 校验 fail-closed（设计依据：等价类-部分失败；不信任前端）
- U27 参数化: 会话标题取首条用户消息截断（短消息全取/恰为上限 20/超上限截断）（设计依据：边界值-标题长度）
- U28: 内容合规 hook 开启且命中敏感词 → error 事件收尾且不落库；关闭 → 不拦截（设计依据：等价类-开关两态）
- U29: chat LLM 失败 → error 事件（三要素）收尾且 rollback 被调用，但用户消息已先行提交保留、无 assistant 行（设计依据：等价类-无效-LLM 失败路径；用户输入是已发生事实不得回滚丢失）
- U30: 本轮用户消息在发往 LLM 的 prompt 中恰好注入一次（历史行剔除 + 显式追加防双份）（设计依据：边界值-注入次数恰 1）
- U31: 滚动摘要返回空白 → 视为失败跳过：既有 summary 不被清空、游标不推进、轮次正常 done 收尾（设计依据：边界值-空串摘要等价失败）

### 后端 L2（HTTP 全链路，真实临时库，LLM monkeypatch mock）

- I1: POST /api/agent/sessions（project_id）→ 201 会话落库；GET sessions 列表按项目过滤——双项目互不可见（设计依据：等价类-项目隔离）
- I2: chat SSE 全链路 → 事件流含 message_start/token/done，messages 表新增 user+assistant 两行；发往 LLM 的 prompt 中本轮用户消息恰注入一次（设计依据：等价类-有效流式轮；边界值-注入次数恰 1）
- I3（三视角串联单用例，断言目标异构不适用参数化）: **视角过滤注入断言（关键安全用例）**——author/character/audience 三视角下 chat，捕获发往 LLM 的 prompt：character 视角下不可见实体（沈墨）的名称不出现在 prompt，可见实体（周兰/青云山）出现；author 全量；audience 仅 audience_known（设计依据：等价类-三视角正交，E05 范式钉死包含/排除集合）
- I4: propose → 响应草案列表 → confirm → entities/relationships 真实落库 → GET /api/entities 可查（两段式闭环；payload 未带 project_id 时服务端以会话归属项目注入）（设计依据：等价类-有效链路）
- I5: confirm 携带篡改 payload（非法 type）→ 200 + failed 折叠（不落库，三要素可读）；未知 kind → 422 请求校验拦截（设计依据：等价类-无效-篡改载荷与 kind 白名单）
- I6: memory-docs: 新建（模板段）→ GET 列表 → PATCH 段（version 递增）→ 并发 CAS 冲突 PATCH 旧 version → 409 且内容未变（设计依据：边界值-version 恰好/差 1）
- I7: GET memory-docs/{id}/page → text/html 自包含且载荷转义（设计依据：等价类-输出安全）
- I8: 删除项目（级联）→ 该项目 conversations/messages/memory_docs 同步清理，他项目不受影响（设计依据：等价类-级联边界）
- I9: 不存在的会话/文档/段与文档错配 → 404 且 problem 锁具体文案（无效等价类兜底）（设计依据：等价类-无效-资源缺失与归属错配）。越权边界说明：会话/文档端点按全局唯一 id 寻址、仅校验存在性——跨项目越权面以不可猜 id（uuid 前缀）为 MVP 边界，路径参数式项目维度 API 演进时收紧（DECISIONS 2026-09-07）
- I10 参数化: LLM 未配置（api_key 空）/ 端点超时 → 502 AgentError 三要素完整（设计依据：等价类-无效-降级两态）
- I11: 工具检索轮——chat 中 LLM 请求工具（mock 返回 tool_call）→ tool 事件推送 + 真实检索结果以数据块进入作答轮 prompt（设计依据：等价类-受控 ReAct 循环）
- I12: chat LLM 失败 → SSE 以 error 事件（三要素）收尾且 HTTP 200；用户消息与标题回填已先行提交保留（设计依据：等价类-无效-LLM 失败路径）

### 后端 L3 E2E（TestClient 公开接口，跨模块）

- E1: 对话→草案→确认→图谱全链路（LLM mock）：建会话 → chat 提及新角色 → propose 产实体草案 → confirm → /api/graph 出现新节点（跨组件理由：agent+entities+relations+perspectives+projects 协作）
- E2: 用户手改记忆文档段 → 下一轮 chat 的 LLM prompt 以新内容为准（hash 目录变化）；agent patch 基于旧版本提交 → 409 冲突不覆盖（跨组件理由：记忆冲突边界语义端到端验证）

### 前端 L1/L2（Vitest）

- FU1: agentStore——SSE 事件归约（token 追加/done 回读/error 三要素/未知与 F13 预留事件忽略不崩溃）、SSE 会话级生命周期（Dock 收起与切会话不断流 FU1-6、项目切换显式 abort FU1-4、全局单流守卫拒绝他会议重复轮 FU1-7）、confirm 成功后广播图谱失效事件、会话列表与记忆文档加载（设计依据：等价类-事件类型全集 + 边界-中断/拒绝路径）
- FU2: AgentHome——会话列表分组与新建、空状态引导卡、记忆文档卡片区（新建两模板）、DraftConfirmCard 确认/放弃、DocEditor 段级表单保存（doc_patch diff 确认卡随 F13 落地）；AgentDock 开合与 z-index 契约（设计依据：DESIGN §5.4/§5.5 基线 + 等价类-空/非空会话集）

增强用例登记（未编号，属已编号用例的失败分支/结构校验补强）：U2 补充（API 密钥缺失快速失败）、U3 补充（chat_turn 工具调用归一化）、U23 补充（会话不存在 404）、U25 补充（畸形草案参数化）、U26 补充（篡改 payload fail-closed）、工具层折叠（未知工具/坏参数，test_execute_tool_failures_fold_to_text）、建档未知 kind（test_create_doc_unknown_kind）。

### 前端 L3（Playwright，SSE 经路由拦截 mock）

- FE1: agent 工作流——进入 Agent 页 → 新建会话 → 发送消息（mock 流式回复）→ 草案卡确认 → 提示已写入 → 打开记忆文档编辑段保存（设计依据：DESIGN §6 剧本 C 前半链路）

## 变异测试结果

- scope（被测模块）: backend/app/agent/（9 文件 1015 个变异体；判杀基线为 0c02d08 定稿代码 + d3e1d8f 判杀桩有界化测试增强）
- 判杀器: L1 tests/unit/test_agent_service.py、test_agent_llm.py、test_agent_prompts.py、test_agent_tools.py、test_agent_memory_docs.py + L2 tests/integration/test_agent_api.py + 架构测试（§9 层级覆盖：模块含 router 必须 L2；L3 视存活体分析决定是否追加）
- **kill rate: 100%（实杀 1015/1015，等价登记 0，存活 0 / 超时 0 / 可疑 0）**——零存活故无需 L3 判杀器追加与等价性登记（2026-09-07 第三次运行，前两次运行事故见下）
- 运行事故与判杀器强化（T-20260907-02 / **E17**）：前两次运行均挂死于同一变异体（service.py 工具分支条件 `and`→`or`，位于第 665 位）——该变异使 stream_chat 对纯文本回复也进工具分支 `continue`，无工具执行致 `used` 恒 0、`enable_tools` 恒真，无限循环调用 LLM；原判杀桩无界（假 LLM 有求必应）且 mutmut 超时依赖 SIGALRM 在 Windows 不存在，pytest 永不返回（实测载荷进程 2109s 纯空转）。修复：判杀桩全改有界（单测 `_scripted_llm` 脚本耗尽即抛替换 5 处重复型桩、U16/U30 调用上限守卫、集成 ChatCapture 耗尽显式抛错），手工应用该变异体验证 0.81s 断言失败（挂死→快速判杀）；规程固化于 testing.md §9「判杀桩有界性」
- 运行残留处置：三次运行终止后均按 T-20260907-01 规程做三方对照（git diff / .bak / 当前），残留变异体与 .bak 全部经 `git checkout` 还原、架构测试拦截确认

## 验收审查记录（docs/testing.md §10）

- 审查时机说明: 协议原定时序为「测试全绿 + 变异达标之后」；因 verify 变异证据门禁要求缓存晚于模块最后一次提交（E12），审查与修复必须前置于变异运行，否则任何审查修复都会作废变异缓存——本功能审查实际发生在变异之前，属时序适配而非跳过。
- 审查者: 只读子代理（无实现上下文）；审查范围 = F10 diff（后端 agent 模块 + perspectives 改动 + 前端 agent 载体 + 测试 + 文档）。
- 发现 12 条（P0×0 / P1×5 / P2×7），处置：修复 10、登记驳回（不实现）2：
  - [P1 修复] 会话切换中断声明与实现矛盾 + 跨会话发送被静默吞掉（输入已清空）→ 语义定稿「切会话不断流 + 全局单流」：SessionView busyElsewhere 禁用输入、store 守卫注释、frontend 两文档措辞更正、FU1-6/FU1-7 判杀。
  - [P1 修复] proposeDrafts/confirmDrafts/createDoc 无 catch（unhandled rejection、无三要素 UI）→ 对齐 sendMessage 模式补 catch 落错误态；**新类型错误 E16 登记**（store action 缺 catch）并转化为 frontend/CONSTRAINTS.md 硬约束。
  - [P1 修复] U17 文档声称断言而实际无 → 工具轮用例锁定截断全文（wrap_data 包裹 + 50 上限 + 标记整体相等）。
  - [P1 修复] U15「seq 非整数」虚报 → 参数化扩展 "abc"/null 两态（错误子串断言）。
  - [P1 修复→文档] DocPatchCard 虚报（E01 复发）→ FU2 与 PROGRESS 更正为 F13 预留。
  - [P2 修复] E05 断言强度（U2/U29/I9/I10/I12）→ problem 锁全文、detail 整体相等、I9 三处 404 补 problem 断言。
  - [P2 修复] 恒真断言（`or True`）删除（E08 复发）。
  - [P2 修复] FU1 生命周期三态缺二 → FU1-6（Dock 收起不断流）/FU1-7（全局单流守卫）；FU1-1 加未知事件忽略帧。
  - [P2 修复→文档] U11/I3 描述漂移校准（U11 改投影契约；I3 去「参数化」标注、名称断言措辞）；增强用例补登记。
  - [P2 登记] I9 越权维度收缩 → DECISIONS 登记「不可猜 id 为 MVP 越权边界」+ 本页 I9 说明。
  - [P2 驳回-登记不实现] DESIGN Esc 收起/Dock 会话切换下拉/confirm 卡片成功态 → DESIGN.md 加 F10 落地注记 + DECISIONS 登记（Esc 与 Dock 下拉随 F13；confirm 成功态以消息流摘要为落地语义）。

## 验收判定

所有「必须」层级通过 + 状态列全 pass + 变异测试达标（kill rate ≥ 85%，§9）+ make check 通过 → 功能完成。
