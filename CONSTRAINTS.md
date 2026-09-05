# CONSTRAINTS.md — 全局硬约束

> 语言规则：每条以「必须」或「禁止」开头。违反任一条视为实现缺陷，不得进入下一个功能点。
> 本文件只保留**全局横切约束**；各模块专属约束见其目录内 CONSTRAINTS.md（导航见文末）。

## 1. 通用工程
- 必须：所有公共函数/类/方法编写标准 docstring（作用、参数、返回值、异常处理、依赖）。
- 禁止：在代码中硬编码配置（路径、密钥、模型名、端口、大小上限）；必须经 config.py 从环境变量或 .env 读取。
- 必须：每次设计决策后更新 DECISIONS.md，每次进度变更后更新 PROGRESS.md。
- 必须：每完成一个功能添加对应单元测试。
- 必须：功能完成判定 = 必须层级测试全部通过 + 测试文档 docs/tests/FXX 就位——L1 单元与 L2 集成每功能必须，L3 E2E 涉及跨组件修改时必须；**跳过任何必须层级 = 未完成**（docs/testing.md）。
- 必须：所有错误消息（异常/lint/测试失败）包含三要素：什么出了问题、为什么、怎么修（docs/lessons.md §3）。
- 禁止：在实现功能 A 时"顺便"重构功能 B；当前功能点端到端通过前不得开始下一个。
- 必须：会话结束前运行 make check 并保持通过状态。

## 2. 架构总原则
- 禁止：跨领域模块 import 其他模块的 ORM 模型、repository 或内部函数；必须经由目标模块的 service 层接口。
- 必须：每个模块目录内维护 ARCHITECTURE.md（职责、接口、依赖）与 CONSTRAINTS.md（硬约束）；接口、依赖或约束变更时同步更新。
- 必须：视角过滤只在读取层实现（单一事实源原则）；禁止为任何视角生成或持久化数据副本。
- 禁止：MVP（第 1 批）引入图像生成功能；资产模块仅支持上传、存储、展示。

## 3. 功能清单
- 必须：docs/features.md 同时只激活一个功能项；验证命令通过才可标记 passing。
- 禁止：手工修改功能清单状态（由验证脚本自动更新）。

## 4. 版本与提交
- 必须：commit message 遵循 Conventional Commits（feat / fix / docs / refactor / test / chore）。
- 禁止：一次提交混合多个功能点；禁止提交未通过 make check 的代码。
- 禁止：将 .env、*.db、data/assets/ 下用户数据、node_modules/、.venv/ 提交至版本库。

## 模块约束文件导航

| 文件 | 范围 | 阅读时机 |
|------|------|----------|
| backend/CONSTRAINTS.md | 后端全局（解耦/事务/数据/异常） | 修改后端任何代码前必读 |
| backend/app/core/CONSTRAINTS.md | core 模块 | 修改 core 前必读 |
| backend/app/entities/CONSTRAINTS.md | entities 模块 | 实现/修改 entities 前必读 |
| backend/app/relations/CONSTRAINTS.md | relations 模块 | 实现/修改 relations 前必读 |
| backend/app/perspectives/CONSTRAINTS.md | perspectives 模块 | 实现/修改 perspectives 前必读 |
| backend/app/assets/CONSTRAINTS.md | assets 模块 | 实现/修改 assets 前必读 |
| backend/app/agent/CONSTRAINTS.md | agent 模块 | 实现/修改 agent 前必读 |
| frontend/CONSTRAINTS.md | 前端全局 | 修改前端任何代码前必读 |
