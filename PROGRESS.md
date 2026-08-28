# PROGRESS.md

## 当前状态
- 最新commit：F04 三视角过滤图查询完成（见 git log）
- 测试状态：后端 100 通过（unit 59：core 5 + entities 10 + relations 11 + perspectives 33；integration 32：entities 10 + relations 10 + graph 12；e2e 4；architecture 5）+ mutmut 变异测试 perspectives kill rate 95.4%；前端 2
- Lint：make check 全绿（后端 ruff/format/lint-imports/mypy + 前端 typecheck/lint/build）
- 功能清单：F01–F04 passing（F05–F10 not_started）

## 当前已完成
- 2026-08-24: 设计阶段收口——技术栈/架构定稿、约束文档分块（10 份）、架构文档就位、features.md 任务分解（F01–F10）、质量保障体系（testing/architecture_checks/lessons）、错误体系与信号采集设计。详见 DECISIONS.md
- 2026-08-24: **F01 项目初始化完成（passing）**——前后端骨架 + 9 例测试 + 跨平台命令面板 task.py + 功能验证器 verify_feature.py。详见 docs/tests/F01_project_setup.md 与 git log
- 2026-08-24: 测试机制盘点修正——RSS 守卫虚登改双态标注（E01）、幽灵节点防线写入 F02 计划、verify 脚本容错（E02，含回归测试）。详见 docs/lessons.md 错误模式库
- 2026-08-27: **F02 实体 CRUD API 完成（passing）**——entities/relations 模块（CRUD/@检索/删除双层防线）+ 首个 Alembic 迁移建齐两表 + L1 10 例 + L2 10 例 + 内存回归守卫 fixture 落地。详见 docs/tests/F02_entity_crud_api.md 与 git log
- 2026-08-27: agent 规则升级——任务清单同步 PROGRESS/测试文档先行/测试失败记录 error.jsonl 三条硬规则写入 AGENTS.md；错误模式库迁移 backend/logs/error.jsonl（入版本库），运行时错误日志改名 runtime_error.jsonl。详见 DECISIONS.md 与 docs/lessons.md §2
- 2026-08-27: **F03 关系 CRUD API 完成（passing）**——relations 模块补全（自环/端点存在性经 entities.service/重复三元组/known_by 成员四重写入校验 + 条件查询路由）+ L1 11 例 + L2 10 例 + L3 e2e 2 例（含 F02×F03 引用解除闭环）；同场修正 E01 复发（T-20260827-03）：补齐映射表声称的三项架构测试。详见 docs/tests/F03_relation_crud_api.md 与 git log
- 2026-08-27: agent 规则升级（二）——测试用例设计方法学（等价类划分 + 边界值分析，参数化强制）与变异测试机制（mutmut，kill rate ≥ 85% + 存活变异体分析归档）写入 AGENTS.md 与 docs/testing.md §2/§8/§9，自 F04 起生效（工具随 F04 落地）。详见 DECISIONS.md
- 2026-08-28: **F04 三视角过滤图查询完成（passing）**——perspectives 模块（schemas/service/router 纯只读聚合，author 全量 / character 按 known_by+标记+端点推导 / audience 双端规则，PerspectiveError 403 三 reason）+ L1 18 例 + L2 12 例 + L3 e2e 2 例 + 变异测试落地：mutmut 判杀 kill rate 95.4%（83/87，存活 4 个 OpenAPI 文案等价性归档），判杀器纳入 L1+L2 双层（纯 unit 判杀对 HTTP 层变异失效，kill rate 曾仅 47%）；含 T0 前置修正（import-linter 三契约补登 + 负例注入验证，E01 复发 T-20260827-06）与 T1 变异工具（task.py mutate 命令）。详见 docs/tests/F04_graph_perspective_query.md、DECISIONS.md 与 git log
- 2026-08-28: 变异测试规则完整化（T-20260828-01 提升）——判杀器层级覆盖原则写入 docs/testing.md §9（L1 基线 + 含 router 必加 L2 + 必须层级含 L3 时加 e2e，防后续端到端场景漏杀）；task.py mutate 对含 router 模块缺 L2 判杀自动拦截（拦截/放行双分支已验证）；错误用例断言强度规范（三要素 + detail 字典钉死）登记 E05。详见 DECISIONS.md 与 backend/logs/error.jsonl（E04/E05）

## 进行中
- 无（F04 已完成，F05 待启动）

## 已知问题
- 无

# 下一步
1. 执行 F05（前端图谱工作台）：G6 力导向图渲染 + 节点详情面板 + CRUD 表单，开工时 `python scripts/task.py verify F05 --activate`；首任务：按 docs/testing.md §5/§8 撰写测试文档 docs/tests/F05_frontend_graph_workbench.md（等价类/边界值设计 + 变异测试计划）
2. F05–F10 依次逐功能实现（一次一个，端到端通过后再下一个）
