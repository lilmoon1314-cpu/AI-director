# PROGRESS.md

## 当前状态
- 最新commit：F01 项目初始化 checkpoint + 测试机制盘点修正（见 git log）
- 测试状态：9/9 通过（后端 7：unit 5 + architecture 2；前端 2：App 冒烟）
- Lint：make check 全绿（后端 ruff/format/lint-imports/mypy + 前端 typecheck/lint/build）
- 功能清单：F01 passing（F02–F10 not_started）

## 当前已完成
- 2026-08-24: 技术栈定稿（FastAPI / SQLite(WAL)+SQLAlchemy / React+TS+Vite / AntV G6 / Tailwind+shadcn-ui / openai SDK / uv+pnpm+Makefile），共 17 项决策，见 DECISIONS.md
- 2026-08-24: 架构风格定稿：模块化单体 + 前后端分离；MVP 建表范围定为 entities + relationships 两张（第 2 批 7 张表经 Alembic 迁移新增）
- 2026-08-24: AGENTS.md 填充（项目概览 / 首次运行命令 / 文档路由含阅读时机 / DoD 与审查反馈提升规则）
- 2026-08-24: 约束文档分块完成：根 CONSTRAINTS.md（全局横切 + 导航）+ backend + 7 个领域模块 + frontend 共 10 份；各 ARCHITECTURE.md 移除重复约束小节改为指向
- 2026-08-24: 全部架构文档就位：根 ARCHITECTURE.md（修正原 ARCHITECTUER.MD 拼写并重命名）+ backend/ARCHITECTURE.md + frontend/ARCHITECTURE.md + 7 个领域模块 ARCHITECTURE.md（职责/接口/依赖）
- 2026-08-24: Makefile 与 init.sh 对齐 INIT.md 初始化契约（setup / dev / test / check）；init.sh 降级为 make setup 薄封装
- 2026-08-24: docs/features.md 任务分解制定（F01–F10，含跨组件标注与分层验证命令）+ INIT.md 初始化验收清单
- 2026-08-24: 质量保障体系设计完成：docs/testing.md（L1/L2/L3 三层验证 + DoD + 测试文档模板）、docs/tests/F01_project_setup.md（首个测试文档范本）、docs/architecture_checks.md（约束→检查映射表 + 审查清单）、docs/lessons.md（审查反馈提升流程 + 错误模式库 + 错误三要素规范）
- 2026-08-24: 错误体系与信号采集设计：AppError 三要素必填（problem/cause/fix）、错误响应结构升级、独立错误日志 error.jsonl、core observability 五类信号自动采集（lifecycle/request/checkpoint/metric/error 统一 JSONL 三流 + 轮转）
- 2026-08-24: Makefile 增加分层测试命令（test-unit/test-integration/test-e2e）、lint-imports 与 check-api-types 纳入 check
- 2026-08-24: **F01 项目初始化完成并通过验证（passing）**：
  - 后端骨架：pyproject.toml（uv 依赖锁）/ .env.example / config.py（pydantic-settings）/ core 基础设施（db 引擎单例+WAL、exceptions 三要素、responses 统一响应、observability 五类信号）/ main.py 应用工厂（lifespan+CORS+健康检查）/ Alembic 迁移框架（env.py+script 模板）
  - 后端测试：tests/unit/test_smoke.py（3 例）+ tests/architecture/test_architecture.py（2 例）+ conftest.py（临时目录隔离 DATABASE/LOG/ASSET）；pytest 配置 pythonpath/markers
  - 前端骨架：React 18 + TS 5 + Vite 5 + Tailwind v4（CSS-first）+ ESLint 9 flat config + Vitest 2 + RTL；App 毛玻璃占位工作台 + 冒烟测试（2 例）
  - 跨平台命令面板：scripts/task.py（18 条命令，Windows 兼容层解析 .cmd 工具）+ Makefile 全量委托（单一实现源）
  - 功能验证器：scripts/verify_feature.py（解析 features.md 验证命令 → 跨平台翻译 → 逐条执行 → 自动写状态 passing/blocked）
  - 环境坑修复：pnpm store 收进项目根（沙箱拦截项目外写入致 EPERM）、alembic.ini 改 ASCII（GBK locale 解码崩溃）、mypy 类型修复（异常处理器签名收窄/引擎同步调用）
- 2026-08-24: **测试机制盘点与修正**：
  - RSS 守卫文档虚登修正：testing.md §7 改为「已就位（运行侧 metrics.jsonl）/ 计划（F02 测试侧 fixture）」双态（错误模式 E01 登记，文档-代码一致性入审查清单）
  - 幽灵节点防线补全至 F02 计划：backend/CONSTRAINTS + features.md F02 行 + architecture_checks.md 映射表新增「FK DDL + ON DELETE RESTRICT 架构测试」「PRAGMA foreign_key_check 空结果巡检」两条 F02 自动检查；F02 首迁移建齐 entities+relationships 两表
  - verify 脚本容错（错误模式 E02）：IDE markdown 格式化器转义 not_started 致状态正则失配——脚本剥离转义+宽容匹配，回归测试 tests/unit/test_verify_script.py（2 例）固化

## 进行中
- 无

## 已知问题
- 无（F02 起按功能清单顺序推进）

# 下一步
1. 执行 F02（实体 CRUD API）：按 docs/features.md 验证命令实现，开工时 `python scripts/task.py verify F02 --activate`，完成后 `python scripts/task.py verify F02`
2. F02–F10 依次逐功能实现（一次一个，端到端通过后再下一个）
