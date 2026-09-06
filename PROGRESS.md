# PROGRESS.md

## 当前状态
- 最新commit：F11 多项目底座完成（passing，见 git log）
- 测试状态：后端 217 通过（projects L1 12 + L2 15 + e2e 2 + 架构/领域适配）+ mutmut projects 100%（125/125）；前端 vitest 122 + Playwright e2e 12（含 projects FE1/FE1b，既有场景路由适配）
- 功能清单：F01–F08、F11 passing；F09 已取消；F10、F12 not_started（执行序：F12 → F10）
- 测试状态：后端 155 通过（含 assets L1 50 + L2 13 + e2e 1 + 新架构测试）+ mutmut（F08 assets kill rate 85.9%，scope 7 逻辑文件 453 变异体）；前端 vitest 111 + Playwright e2e 10（含 assets EF1/EF2）
- Lint：make check 全绿（后端 ruff/format/lint-imports 5 契约/mypy/pytest + 前端 check-api-types/typecheck/lint/build）
- 功能清单：F01–F08 passing；F09 已取消移除；F10 not_started

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

## 进行中
- 无

## 已知问题
- 无

## 下一步
1. F12 工作台导航与资产页重构（not_started）：资产页两级钻取（7 类型库墙→类型卡片墙→HTML）+ 分区独立搜索 + 空状态引导 + 通用资产表单 modal 化 + 卡片规范统一与 testid 迁移（DESIGN.md §5.3/§9/§10；开工时 `python scripts/task.py verify F12 --activate`；首任务撰写 docs/tests/F12 测试文档）
2. F10（Agent 对话与确认写入）：POST /api/agent/chat SSE 流式回复（上下文经视角过滤）；propose 结构化草案；confirm 确认落库；AgentHome + AgentDock 载体按 DESIGN.md §5.4/§5.5（开工时 `python scripts/task.py verify F10 --activate`；首任务撰写测试文档 docs/tests/F10）
3. 第二阶段候选项（届时先立功能项）：通用资产自定义属性 schema 注册表 + agent 辅助定制（分类→属性定义→动态表单/HTML 模板）、通用资产页 HTML 源码级编辑、资产注入 LLM 多模态上下文（依赖 F10）
4. mutmut 运行规程提醒：mutmut 必须在代码定稿并提交后单独运行，运行期间禁止编辑被测模块（E11，已由脏树守卫拦截）

