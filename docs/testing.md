# docs/testing.md — 测试策略

> 判定功能是否完成的唯一依据（DoD）。编写任何测试或标记功能完成前必读。

## 1. 验证层级

| 层级 | 定义 | 范围 | 必须性 |
|------|------|------|--------|
| L1 单元 | 单函数/类，依赖全部 mock（内存） | 模块内 | **每个功能必须** |
| L2 集成 | 真实 SQLite（临时库），router→service→repository 全链路 | 单模块内 | **每个功能必须** |
| L3 E2E | 公开接口验证完整用户路径（后端 TestClient / 前端 Playwright） | 跨模块或跨前后端 | **涉及跨组件修改时必须** |

- **跳过任何必须层级 = 功能未完成**（不得标记 passing）。
- "跨组件"判定：功能涉及 ≥2 个领域模块协作，或前后端联调。features.md 每项已标注 `E2E` 列。

## 2. 完成定义（DoD）

功能标记 passing 需同时满足：

1. 实现代码 + 对应单元测试（根 CONSTRAINTS.md §1）
2. 测试文档 `docs/tests/FXX_<name>.md` 就位，层级矩阵中所有"必须"状态为 pass
3. 必须层级测试全部通过（验证命令见 features.md）
4. `make check` 通过

## 3. 目录结构

```
backend/tests/
├── conftest.py           # 共享 fixture（临时 DB、TestClient、内存采样）
├── unit/                 # L1：test_<模块>_<行为>.py
├── integration/          # L2：test_<模块>_api.py
├── e2e/                  # L3：test_<场景>_flow.py（跨模块）
└── architecture/         # 架构约束可执行检查（见 docs/architecture_checks.md）

frontend/tests/
├── unit/                 # L1：组件/store 单测（Vitest + RTL）
└── integration/          # L2：组件树 + mock API（Vitest + msw）
frontend/e2e/             # L3：全栈 E2E（Playwright，F05 引入）
```

## 4. 运行方式

```bash
make test-unit          # 后端: uv run pytest -m "unit"    前端: pnpm test:unit
make test-integration   # 后端: pytest -m "integration"    前端: pnpm test:integration
make test-e2e           # 后端: pytest -m "e2e"            前端: Playwright（F05 起）
make test               # 全部层级 + architecture
```

pytest marker 约定：`unit` / `integration` / `e2e` / `architecture`（conftest.py 注册，测试文件必须标注所属 marker）。

## 5. 测试文档模板（docs/tests/FXX_<name>.md）

```markdown
# FXX <功能名> — 测试文档

## 测试目标
一句话说明验证什么。

## 层级矩阵
| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1: <行为> | tests/unit/xxx.py | 必须 | pending |
| L2 集成 | I1: <链路> | tests/integration/xxx.py | 必须 | pending |
| L3 E2E | E1: <场景>（跨组件理由） | tests/e2e/xxx.py | 必须/不适用 | pending |

## 用例说明
- U1: <前置/动作/预期>
- I1: ...

## 验收判定
所有"必须"层级通过 + 状态列全 pass + make check 通过 → 功能完成。
```

状态列规则：与 features.md 相同，仅在验证命令通过后更新为 `pass`。

## 6. 命名与编写规范

- 测试文件：`test_<模块>_<行为>.py`；用例：`test_<行为>_<预期结果>`
- 一个用例只验证一个行为；断言消息包含三要素（什么/为什么/怎么修，见 docs/lessons.md）
- L3 用例必须走公开接口（HTTP/浏览器），禁止直接调用内部函数

## 7. 内存回归守卫

- 运行侧（**已就位**）：core observability 后台线程低频采样 RSS / CPU 写入 `logs/metrics.jsonl`（运行期资源趋势分析）。
- 测试侧（**计划，F02 落地**）：conftest.py 将提供 e2e 级 fixture——用例执行前后采样进程 RSS，增长超阈值（config: `memory_guard_threshold_mb`）即失败。
- 规则：文档描述机制必须区分「已就位 / 计划（FXX）」双态，禁止把计划写成现状（错误模式 E01，见 docs/lessons.md）。
