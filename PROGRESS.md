# PROGRESS.md

## 当前状态
- 最新commit：F08 资产管理完成（passing，见 git log）
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

## 进行中
- 无

## 已知问题
- 无

## 下一步
1. F10（Agent 对话与确认写入）：POST /api/agent/chat SSE 流式回复（上下文经视角过滤）；propose 结构化草案；confirm 确认落库（开工时 `python scripts/task.py verify F10 --activate`；首任务撰写测试文档 docs/tests/F10）
2. 第二阶段候选项（届时先立功能项）：通用资产自定义属性 schema 注册表 + agent 辅助定制（分类→属性定义→动态表单/HTML 模板）、通用资产页 HTML 源码级编辑、资产注入 LLM 多模态上下文（依赖 F10）
3. mutmut 运行规程提醒：mutmut 必须在代码定稿并提交后单独运行，运行期间禁止编辑被测模块（E11，已由脏树守卫拦截）

