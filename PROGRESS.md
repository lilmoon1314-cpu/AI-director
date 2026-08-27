# PROGRESS.md

## 当前状态
- 最新commit：F03 关系 CRUD API 完成（见 git log）
- 测试状态：后端 53 通过（unit 26：core 5 + entities 10 + relations 11；integration 20：entities 10 + relations 10；e2e 2：relations flow；architecture 5；前端 2）
- Lint：make check 全绿（后端 ruff/format/lint-imports/mypy + 前端 typecheck/lint/build）
- 功能清单：F01–F03 passing（F04–F10 not_started）

## 当前已完成
- 2026-08-24: 设计阶段收口——技术栈/架构定稿、约束文档分块（10 份）、架构文档就位、features.md 任务分解（F01–F10）、质量保障体系（testing/architecture_checks/lessons）、错误体系与信号采集设计。详见 DECISIONS.md
- 2026-08-24: **F01 项目初始化完成（passing）**——前后端骨架 + 9 例测试 + 跨平台命令面板 task.py + 功能验证器 verify_feature.py。详见 docs/tests/F01_project_setup.md 与 git log
- 2026-08-24: 测试机制盘点修正——RSS 守卫虚登改双态标注（E01）、幽灵节点防线写入 F02 计划、verify 脚本容错（E02，含回归测试）。详见 docs/lessons.md 错误模式库
- 2026-08-27: **F02 实体 CRUD API 完成（passing）**——entities/relations 模块（CRUD/@检索/删除双层防线）+ 首个 Alembic 迁移建齐两表 + L1 10 例 + L2 10 例 + 内存回归守卫 fixture 落地。详见 docs/tests/F02_entity_crud_api.md 与 git log
- 2026-08-27: agent 规则升级——任务清单同步 PROGRESS/测试文档先行/测试失败记录 error.jsonl 三条硬规则写入 AGENTS.md；错误模式库迁移 backend/logs/error.jsonl（入版本库），运行时错误日志改名 runtime_error.jsonl。详见 DECISIONS.md 与 docs/lessons.md §2
- 2026-08-27: **F03 关系 CRUD API 完成（passing）**——relations 模块补全（自环/端点存在性经 entities.service/重复三元组/known_by 成员四重写入校验 + 条件查询路由）+ L1 11 例 + L2 10 例 + L3 e2e 2 例（含 F02×F03 引用解除闭环）；同场修正 E01 复发（T-20260827-03）：补齐映射表声称的三项架构测试。详见 docs/tests/F03_relation_crud_api.md 与 git log

## 进行中
- 无

## 已知问题
- 无（F03 起按功能清单顺序推进）

# 下一步
1. 执行 F04（三视角过滤图查询）：按 docs/features.md 验证命令实现，开工时 `python scripts/task.py verify F04 --activate`，完成后 `python scripts/task.py verify F04`
2. F04–F10 依次逐功能实现（一次一个，端到端通过后再下一个）
