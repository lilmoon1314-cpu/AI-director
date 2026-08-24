# F01 项目初始化 — 测试文档

> 模板与规则见 docs/testing.md。状态列仅在验证命令通过后更新。

## 测试目标
验证初始化契约（INIT.md）：环境可启动、测试框架可运行、架构检查框架就位。

## 层级矩阵

| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1: 后端 smoke（config 加载 + 应用装配 + health 端点信号） | backend/tests/unit/test_smoke.py | 必须 | pass |
| L1 单元 | U2: 前端 smoke（App 渲染 + 毛玻璃视觉锚点） | frontend/src/App.test.tsx | 必须 | pass |
| L2 集成 | 不适用（无业务模块） | — | — | — |
| L3 E2E | 不适用（无跨组件修改） | — | — | — |
| 架构 | A1: import-linter 配置可运行（空模块基线） | backend/pyproject.toml 契约 | 必须 | pass |
| 架构 | A2: 架构测试基线通过（core 纯净性 + 日志集中） | backend/tests/architecture/ | 必须 | pass |

## 用例说明

- U1: `uv run pytest -m unit` 通过——证明 pytest 框架、marker 注册、config 加载链路可用
- U2: `pnpm test:unit` 通过——证明 Vitest + RTL 框架可用
- A1: `uv run lint-imports` 通过——import-linter 契约机制就位（领域模块契约随 F02+ 逐条生效）
- A2: `uv run pytest -m architecture` 基线通过——自定义架构检查框架就位

## 验收判定（INIT.md 验收清单）

- [x] `make setup` 从零开始能成功（Windows 经 `python scripts/task.py setup` 等价执行）
- [x] `make test` 全部通过（后端 5 + 前端 2 = 7 个测试）
- [x] `make check` 通过（后端 ruff/format/lint-imports/mypy/pytest + 前端 typecheck/lint/build）
- [x] 新会话只看仓库可回答"怎么跑/怎么测"（AGENTS.md 首次运行命令）
- [x] git checkpoint 已提交
- [x] 本文档状态列全部 pass
