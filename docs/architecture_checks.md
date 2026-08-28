# docs/architecture_checks.md — 架构约束可执行检查映射

> 原则：**每条架构约束必须有对应的自动检查（lint / 测试），或登记于审查清单**；审查清单项经 docs/lessons.md 流程持续转化为自动检查。
> 新增或修改任何架构约束时，必须同步更新本表；无法自动化的约束须注明原因。

## 1. 检查工具

| 工具 | 用途 | 运行命令 |
|------|------|----------|
| import-linter | 模块边界契约（import 依赖检查） | `uv run lint-imports`（纳入 make check） |
| tests/architecture/ | 自定义架构测试（AST 扫描、源码模式检查） | `pytest -m architecture` |
| ruff / eslint | 通用 lint + 前端限制规则 | make check |
| 类型同步检查 | 前端 API 类型与后端 schema 一致 | `make check-api-types`（导出 OpenAPI → openapi-typescript 生成 → git diff 校验；**F05 起挂入 `task.py check` 前端链首步**） |

## 2. 约束 → 检查映射表

| 约束（出处） | 检查机制 | 类型 | 引入 |
|--------------|----------|------|------|
| 跨模块仅经 service（根 CONSTRAINTS §2） | import-linter：每模块一条 forbidden 契约——外部模块禁止直接 import 该模块的 repository/models/schemas（`allow_indirect_imports=true` 只拦直接引用，模块自身装配边豁免） | 自动 | F01 登记 / **F04 落地**（此前虚登，见 error.jsonl T-20260827-06） |
| core 零业务依赖（core/CONSTRAINTS） | import-linter：core 禁止 import 任何领域模块 | 自动 | F01 登记 / **F04 落地**（同上） |
| router 不碰数据层（backend/ARCHITECTURE §2） | tests/architecture：AST 检查 router.py 禁止 import repository/models | 自动 | F02 |
| 配置禁止硬编码（根 §1） | tests/architecture：扫描源码禁止端口/URL/密钥样式字面量（白名单：config.py、tests） | 自动（启发式） | F02 |
| 错误响应三要素统一结构（backend/CONSTRAINTS） | 集成测试断言错误响应含 code/problem/cause/fix | 自动 | F02 |
| SQLite WAL + 外键（backend/CONSTRAINTS） | 集成测试启动时断言 PRAGMA 值 | 自动 | F02 |
| relationships 外键 DDL + ON DELETE RESTRICT（backend/CONSTRAINTS） | 架构测试：断言迁移/ORM 模型含 FK 声明与 RESTRICT 策略 | 自动 | F02 |
| 无幽灵节点（悬空外键巡检） | 集成测试：`PRAGMA foreign_key_check` 断言空结果 | 自动 | F02 |
| id 不可变（entities/CONSTRAINTS） | 单元测试：update 尝试改 id 被拒 | 自动 | F02 |
| 视角过滤只读/单一事实源（perspectives/CONSTRAINTS） | E2E：视角查询前后数据库快照逐字节一致 | 自动 | F04 |
| character 视角不泄露被过滤实体名（perspectives/CONSTRAINTS） | L2/L3：响应文本级断言（不含被过滤实体名） | 自动 | F04 |
| 禁止散点日志（backend/CONSTRAINTS） | tests/architecture：业务模块禁止 import logging 直接调用（仅 core 可） | 自动 | F02 |
| 前端类型自动生成（frontend/CONSTRAINTS） | check-api-types = 重新生成 + `git diff --exit-code` | 自动 | F05 |
| 前端禁止直连 fetch（frontend/CONSTRAINTS） | eslint no-restricted-syntax：fetch/axios 仅允许出现在 src/api/ | 自动 | F05 |
| 上传 uuid 重命名/防穿越（assets/CONSTRAINTS） | 单元测试：路径穿越用例（`../`、绝对路径）全部拒绝 | 自动 | F08 |
| LLM 配置不硬编码（agent/CONSTRAINTS） | tests/architecture：agent 源码禁止端点/密钥字面量 | 自动 | F10 |

## 3. 审查清单（暂无自动检查，人工执行）

| 约束 | 暂无法自动化的原因 |
|------|--------------------|
| docstring 完整性（作用/参数/返回/异常/依赖） | 语义级检查（ruff DOC 规则成熟后转化） |
| 文档-代码一致性（文档声称「已就位」的机制实际存在，E01） | 语义级比对（发现虚登按 docs/lessons.md E01 当场修正并双态标注） |
| router 无业务逻辑 | 逻辑语义判断 |
| properties 校验"读宽容写严格" | 行为语义判断（部分由单元测试覆盖） |
| G6 单例与增量更新 | 渲染行为判断（组件测试部分覆盖） |
| 视觉基调与动效克制 | 视觉判断 |

## 4. 维护规则

- 新增约束 → 本表登记检查机制，与约束同一功能点内落地
- 检查规则误报/漏报 → 经 docs/lessons.md 流程修正
- 审查清单项一旦具备自动化条件 → 立即转化并从清单移除
