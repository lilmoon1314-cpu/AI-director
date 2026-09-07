# PROGRESS.md

## 当前状态
- 最新commit：F12 工作台导航与资产页重构完成（passing，见 git log）
- 测试状态：后端 224 通过 + 前端 vitest 92 单元（含 assetFilters 10 参数化实例）+ 集成 51（FI1–FI13 + F08 保留回归）+ Playwright e2e 13（含 FE1–FE3 两级钻取全链路）；变异门禁按纯前端规则自动跳过（无后端 service 改动，后端资产回归 16 过）
- 功能清单：F01–F08、F11、F12 passing；F09 已取消；F10 not_started
- Lint：make check 全绿（后端 ruff/format/lint-imports 7 契约/mypy/pytest + 前端 check-api-types/typecheck/lint/build）

## 当前已完成
- 2026-08-24: 设计阶段收口——技术栈/架构定稿、约束文档分块（10 份）、features 分解（F01–F10）、质量保障体系（testing/architecture_checks/lessons）、错误体系与信号采集设计。详见 DECISIONS.md
- 2026-08-24~27: **F01 初始化 + F02 实体 CRUD + F03 关系 CRUD（passing）**——前后端骨架与跨平台命令面板 task.py；entities/relations 两表（FK RESTRICT 双层防线）+ CRUD/@ 检索/删除引用校验；L1/L2/L3 分层测试体系与错误模式库（error.jsonl）落地；期间 agent 规则升级三条（任务清单同步/测试文档先行/等价类+边界值设计与变异测试方法论）。详见 docs/tests/F01~F03、docs/testing.md 与 git log
- 2026-08-28: **F04 三视角过滤图查询（passing）**——perspectives 纯只读聚合 + L1/L2/e2e 全过；mutmut kill rate 95.4%；判杀器层级覆盖原则与等价性登记豁免边界两项决策入规。详见 docs/tests/F04 与 DECISIONS.md
- 2026-08-28: **F05 前端图谱工作台（passing）+ 六轮增强返工**——前端基建 + GraphCanvas + 详情面板/表单/Workbench；用户追加七项 → 光点样式+负载验收 → 视觉返工（防重叠真修）→ 交互三轮；错误模式 E06–E08 登记。详见 docs/tests/F05、frontend/CONSTRAINTS.md 与 git log
- 2026-08-28: **F06 视角切换 UI（passing）+ 反馈修复轮**——perspectiveStore + 视角透传 + PerspectiveSwitcher；E09 修复；「视角仅约束展示面」决策入 DECISIONS
- 2026-08-28: **F07 @ 实体选择器（passing）+ 视觉反馈修复**——EntityPicker/可见性徽标/名称解析；E10 钉死；可见性判定与名称显示层决策入 DECISIONS
- 2026-09-05: **F08 重新定界 + F09 取消（用户需求）**——工作台「图谱|资产管理」双页；资产 HTML 形态存储；独立资产库 assets.db；通用资产自定义属性 schema + agent 定制推迟第二阶段。详见 DECISIONS.md 2026-09-05 三条
- 2026-09-05: **F08 资产管理（passing）**——后端 assets 模块重建：独立资产库（data/assets.db，启动 create_all 幂等引导，Alembic 例外入规）+ 图片上传（白名单/上限/uuid/流式 + /api 同源图片路由）+ 通用资产 CRUD（分类自由标签/attributes 自由属性/多图/封面）+ 项目资产（实体按类型分组卡片、HTML 资产页按 updated_at 惰性生成/过期再生、实体删除读取时孤儿清扫）；前端 Workbench 壳层双页签 + AssetLibrary（通用资产区 CRUD 表单/项目资产区卡片网格）+ 内嵌 HTML 查看器 + 实体详情面板图片区；HTML 渲染全量转义（XSS 防线）；测试：后端 L1 50 + L2 13 + e2e 1、前端 vitest 111、Playwright EF1/EF2（截图 AS-01~03）；mutmut 三轮迭代 85.9% 达标（rendering 模板按 §9 成本控制收窄排除）；过程事故 E11/T-20260905-01/02（mutmut 并发编辑覆盖 + 变异体误提交）登记并转化为 task.py mutate 脏树守卫 + app/ 禁 .bak 架构测试。详见 docs/tests/F08_asset_management.md、DECISIONS.md 2026-09-05 与 git log
- 2026-09-06: **交互设计会话（DESIGN.md v1）**——F10 开工前与用户对齐多项目工作台交互设计，四项决策入 DECISIONS（独立项目首屏/Agent 同一会话池/通用库留驻资产页/本轮仅设计文档）；产出根目录 DESIGN.md：现状诊断 9 条（无路由/两级 tab 嵌套/命名失实/无搜索/表单替换丢上下文/agent 零载体/空状态缺失/多项目硬缺失/键盘可达性）、两层作用域模型（全局=通用库+harness+skills；项目=图谱+资产+记忆+会话）、路由方案（/projects/:id/graph|assets|agent，建议 react-router=OQ-1）、五页面设计（项目首屏/图谱页/资产页两级钻取/AgentHome/AgentDock 侧边栏）、端到端剧本 A–E、前端 store 重置矩阵（generalCards 全局缓存跨项目复用）、多项目后端蓝图（projects 表/project_id 迁移/默认项目打包/级联清扫/会话记忆入主库/路径参数式 API）、testid 迁移映射、开放问题 OQ1–OQ7；落地拆解仅作建议稿（多项目底座→工作台重构→F10 挪后），待用户审阅后立功能项。AGENTS.md 专题文档路由已收录 DESIGN.md
- 2026-09-06（续）: **设计基线全仓文档同步**——按「双态标注」原则（规划内容标注并引用 DESIGN.md 章节）将新增/变更设计传播至 13 份文档：README（设计基线与架构演进节：多项目规划 + 模块化单体复评）；根 ARCHITECTURE（上下文图加 projects(规划)/依赖图加 projects 依赖方向（仅依赖 core、禁反向 import、经 service 归属校验）/模块清单/§5.5 多项目数据流/演进路线加第 1 批扩展行/文档导航）；根 CONSTRAINTS（§2 新增三条：DESIGN 基线遵循、projects 依赖方向、单体维持与拆分触发条件）；backend ARCHITECTURE/CONSTRAINTS（目录树 projects 行、API 总表 /api/projects 规划行、归属校验、删项目显式级联跨库补偿、project_id Alembic 迁移打包默认项目）；frontend ARCHITECTURE/CONSTRAINTS（路由规划注记、views/stores 蓝图（ProjectPicker/AgentHome/projectStore）、SSE 生命周期会话级修订注记、统一卡片规范、z-index 规范、资产页升级规划）；data_struct_define 新增 §11（projects 表/project_id/global_state 单例预警/conversations+messages+memory_docs 入主库/assets 多项目语义，全规划态）；agent/assets/entities/relations/perspectives 五模块 ARCHITECTURE+CONSTRAINTS 同步职责/依赖/规划条目

- 2026-09-06（续二）: **F11 多项目底座（passing）**——后端：projects 模块五层（默认项目 lifespan 播种恒存在/计数器反规范化事务内维护/保护性删除/级联=router 组合层编排 relations→entities→projects.delete 原子提交→assets 显式清扫+孤儿清扫兜底）+ Alembic 迁移（projects 表+双表 project_id FK/索引+存量打包默认项目）+ entities/relations/perspectives/assets 四模块 project 维度（归属校验/跨项目引用 422/图查询与资产卡片缺省默认项目）+ import-linter 契约三条（projects 业务层零领域依赖等）+ core 共享层修复（Pydantic value_error ctx 嵌异常致 422→500，responses JSON 安全化）。前端：react-router 路由化（/projects 首屏 + /projects/:id/graph|assets）+ ProjectPicker（卡片/搜索/新建/改名/删除输入名确认/空态）+ ProjectSwitcher + projectStore（Outlet context 渲染期供给 projectId 避免父子 effect 竞态）+ store 陈旧检测重置换机（generalCards 全局缓存保留）+ 表单/@检索/角色下拉隐式项目作用域 + 既有 5 个 e2e spec 路由适配（openWorkbench helper）。测试：后端 217 通过（projects L1/L2/L3 + 领域 179 项适配 + 架构 DDL 契约）、前端 vitest 122（新增 FU1/FU2）+ Playwright 12（新增 FE1/FE1b）；mutmut projects 两轮 63.2%→100%（125/125 零存活零等价）。事故：E12（mutmut 缓存残留→mutate 自动清缓存）、E13（backdrop-filter 层叠拦截→顶栏 z-30+e2e 防线）、T-20260906-03（e2e 僵尸后端持旧库→清理规程）。详见 docs/tests/F11_multi_project_foundation.md、DECISIONS.md 与 git log

- 2026-09-06（续三）: **质量门禁双强化（用户决策）**——①变异证据机器门禁：verify_feature.py 写 passing 前强制校验（缓存存在/含该模块变异体/kill rate≥85%/缓存晚于模块最后提交，F04 起生效、L1 文件名约定定位模块、纯前端与空壳模块跳过；9 项单测；实测 F11 通过、F08/F04 重验将被要求重跑各自模块变异——DoD 诚实反映），E12 流程风险闭环；②验收审查子代理协议落 docs/testing.md §10（只读/自包含 prompt/结构化发现/verify 前触发/发现按 lessons §1 提升）+ AGENTS.md 工作规则；**F11 首次试点即抓出 P0**：GraphView 重置换机 useRef 判定在 key=projectId 整树重挂载下不可达（视角/选中/查看器跨项目残留，E14 登记）→ 改读全局 graphStore.loadedProjectId 陈旧检测 + FU1 集成用例锁定（generalCards 保留断言）；P1×2 文档漂移（FU1 机制/I8 known_by 维度）与 P2×4（默认项目常量收敛 client.ts/测试目标口径/e2e 判杀重叠论证）全部处置，处置记录入 F11 测试文档「验收审查记录」

- 2026-09-06（续四）: **F12 工作台导航与资产页重构（passing）**——资产页分区升级入 URL（react-router 子路由：`assets/general` 默认落点 OQ-6｜`assets/project` 类型库墙｜`assets/project/:entityType` 类型库详情，无效类型重定向回墙）；项目资产两级钻取（ProjectTypeWall 7 类型库卡聚合「N 实体·M 张图」/EntityTypeAssets 面包屑+asset-type-back+asset-search；空类型虚线卡与详情引导「去图谱页创建」经 `?create=entity&type=` 查询参数联动、GraphView 消费即清理）；通用参考库重命名与「跨项目共享」徽标 + 独立搜索（lib/assetFilters 纯函数：标题/描述/分类与 chips AND）+ 空库引导卡/搜索无命中独立提示 + 表单 modal 化（OQ-3，ui/Modal，卡片墙不再被整区替换）；AssetCardTile 按 DESIGN §9 统一（16:10 封面 scale-105/-translate-y-1/text-sm 概要/编辑按钮 hover+focus 可见）；三要素错误态落地（assetStore generalError/entityError + ui/ErrorStrip 错误条+重试，不再吞错成空态）。**验收审查（§10 协议第 2 轮）12 条发现（P0×0/P1×3/P2×9）全处置**：P1 抓出 DESIGN 虚登 verify 状态（E01 同型，改指 features.md 唯一事实源）、FI11 参数清理零断言（补 LocationProbe）、error 态偏离基线（按基线实现而非登记偏离）；集成测试抓出真缺陷 **E15**（react-router 嵌套 Outlet 不自动继承 context，深链冷启动拼 /projects/undefined——已入 CONSTRAINTS 硬约束 + FI4 判杀）与 assetStore 跨用例缓存泄漏（T-20260906-05）。测试：L1 assetFilters 10 参数化实例、L2 集成 51（FI1–FI13+保留回归）、L3 e2e 13/13、后端资产回归 16；ProjectAssetSection 退役。详见 docs/tests/F12_workbench_navigation_assets.md（含 testid 迁移契约与验收审查记录）、DECISIONS.md 与 git log

## 进行中

**F10（Agent 对话与确认写入）**——底座范围（创作工作流拆 F13，2026-09-06 用户决策：轻量 ReAct 内环 / 记忆文档 HTML 分段两段式 / 内置三防线+合规 hook / ToT 以多方案征求替代）：

- [x] 激活 F10 + 撰写测试文档 docs/tests/F10_agent_chat.md（先行，pending 态）
- [ ] config 新增 AGENT_*（预算/窗口/工具配额/合规开关）与 LLM_MODEL_LIGHT + .env.example 同步
- [ ] Alembic 迁移：conversations / messages / memory_docs / memory_doc_sections 四表 + DDL 架构断言扩展
- [ ] llm.py 封装（懒加载单例/超时/usage 记录/JSON 修复重试 1 次/轻量模型路由）+ 单测
- [ ] perspectives.filter_entities_for_agent（可见实体完整属性，规则不出模块）+ 架构断言
- [ ] prompts.py 上下文组装（分层顺序/图谱目录/文档目录 hash/预算裁剪/注入分隔符）+ 单测
- [ ] tools.py 四检索工具（entity_detail/neighborhood/search/doc_section）+ 每轮配额 + 单测
- [ ] memory_docs 段级 service + rendering.py 自包含 HTML（全转义）+ 段级 patch CAS + 单测
- [ ] agent service：stream_chat（SSE 事件协议）/propose/confirm_write/会话 CRUD + 单测
- [ ] router（/api/agent/*，project_id 查询参数渐进迁移约定）+ main 挂载 + openapi.json + import-linter agent 契约 + L2 集成测试
- [ ] 前端：gen:api-types → agentStore（SSE 会话级生命周期）→ AgentHome/AgentDock/消息流/草案确认卡/DocPatchCard/DocEditor → 路由 + vitest
- [ ] L3 e2e（后端流 + 前端 Playwright）+ make check + mutmut（kill rate ≥85%）+ 测试文档状态更新
- [ ] 文档同步：DECISIONS 登记 5 项新决策（HTML 分段记忆文档取代 OQ-2/思考模式/检索模式/安全三防线/F10-F13 切分）、agent 与 frontend ARCHITECTURE/CONSTRAINTS 修订、data_struct_define §11 落地态、DESIGN OQ-2 裁决标注、F13 登记「下一步」
- [ ] 验收审查子代理（§10）→ triage → verify F10 → 提交推送

## 已知问题
- 无

## 下一步
1. F10（Agent 对话与确认写入）：POST /api/agent/chat SSE 流式回复（上下文经视角过滤）；propose 结构化草案；confirm 确认落库；AgentHome + AgentDock 载体按 DESIGN.md §5.4/§5.5（开工时 `python scripts/task.py verify F10 --activate`；首任务撰写测试文档 docs/tests/F10；SSE 会话级生命周期落地时修订 frontend/CONSTRAINTS.md 并按 §10 派验收审查子代理）
2. 第二阶段候选项（届时先立功能项）：通用资产自定义属性 schema 注册表 + agent 辅助定制（分类→属性定义→动态表单/HTML 模板）、通用资产页 HTML 源码级编辑、资产注入 LLM 多模态上下文（依赖 F10）
3. mutmut 运行规程提醒：mutmut 必须在代码定稿并提交后单独运行，运行期间禁止编辑被测模块（E11，已由脏树守卫拦截）

