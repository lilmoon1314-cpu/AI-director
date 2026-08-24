```
agent入口文件
- 项目概览
- 首次运行命令
- 全局硬约束
- 工作规则
- 专题文档路由
```
# AGENT.md

## 项目概览
基于"全知底层 + 视角属性"设计的影视世界观数据底座：模块化单体架构（FastAPI + SQLite + React/G6）提供实体/关系管理与作者-角色-观众三级视角隔离的力导向图可视化，为多智能体剧本工作流奠定单一事实源（第 1 批 MVP：数据管理 + 可视化 + Agent 辅助创建，不含图像生成）。

## 首次运行命令
```bash
# 环境要求: Python 3.12+ / Node.js 20+ / uv / pnpm 9+
make setup         # 初始化: 安装前后端依赖、生成 .env、执行数据库迁移
make dev           # 同时启动前后端（后端 http://localhost:8000/docs，前端 http://localhost:5173）
make dev-backend   # 仅启动后端；make dev-frontend 仅启动前端
make test          # 运行前后端全部测试
make check         # 完整验证: 后端 ruff+format+mypy+pytest / 前端 typecheck+lint+build
```

> Windows 无 make 时用等价命令面板：`python scripts/task.py setup|dev|test|check`（Makefile 各 target 均委托该脚本，行为完全一致）。
> 功能项验证与清单状态更新：`python scripts/task.py verify FXX`（等价 `make verify FXX`；状态由脚本写入 docs/features.md，禁止手改）。


## 全局硬约束
- 所有公共函数必须按标准格式写 docstring（包含作用、参数、返回值、异常处理、依赖）
- 禁止在代码中硬编码配置，使用 config.py 从环境变量或 .env 读取。
- 每次决策都必须更新 DECISIONS.md 中的记录。
- 每次进度更新都必须更新 PROGRESS.md 中的记录。
- 每完成一个功能必须添加对应单元测试
- 功能完成判定必须满足验证层级：L1 单元测试与 L2 集成测试每功能必须通过；L3 端到端测试涉及跨组件修改时必须通过；跳过任何必须层级 = 未完成（docs/testing.md）
- 所有错误消息必须包含三要素：什么出了问题、为什么、怎么修（docs/lessons.md）
- 每条架构约束必须有对应的自动检查（lint/测试）或登记于审查清单（docs/architecture_checks.md）

## 功能清单规则
- 功能清单文件: /docs/features.md
- 每次只激活一个功能项
- 功能项验证命令必须通过才能标为 passing
- 不要修改功能清单的状态，由验证脚本自动更新

## 工作规则
- 每次只完成一个功能点
- 当前功能点在端到端通过之后，才能开始下一个
- 不要在实现功能 A 时"顺便"重构功能 B
- 功能完成的唯一标准（DoD，docs/testing.md §2）：必须层级测试全通过 + 测试文档 docs/tests/FXX 就位且状态全 pass + make check 通过
- 审查反馈提升（docs/lessons.md §1）：每次代码审查/测试失败中发现新类型的 agent 错误，当次会话内登记错误模式库并转化为自动检查（lint/架构测试/回归测试）；暂无法自动化的加入审查清单

## 每次会话开始时
1. 读 PROGRESS.md 了解当前状态
2. 读 DECISIONS.md 了解重要决策
3. 跑 make check 确认仓库处于一致状态
4. 从 PROGRESS.md 的"下一步"部分继续工作

## 每次会话结束前
1. 更新 PROGRESS.md
2. 跑 make check 确认一致状态
3. 提交所有已完成的工作

## 专题文档路由

> 格式：文档 — 阅读时机。未按时机阅读即动手视为违规。

### 每次会话开始时必读
- `PROGRESS.md` — 了解当前状态、已完成项与下一步
- `DECISIONS.md` — 了解既有技术决策，避免重复决策或与决策冲突
- `CONSTRAINTS.md`（根）— 全局硬约束 + 模块约束文件导航，写任何代码前确认

### 修改对应部分时必读
- `ARCHITECTURE.md`（根）— 改动模块边界、依赖关系或跨模块数据流时必读
- `backend/ARCHITECTURE.md` — 修改后端任何代码前必读（分层/异常/生命周期/API 总表）
- `backend/CONSTRAINTS.md` — 修改后端任何代码前必读（解耦/事务/数据/异常）
- `backend/app/<module>/ARCHITECTURE.md` — 修改该模块职责/接口/依赖前必读；变更时必须同步更新
- `backend/app/<module>/CONSTRAINTS.md` — 实现/修改该模块任何功能前必读（core / entities / relations / perspectives / assets / sync / agent）
- `frontend/ARCHITECTURE.md` — 修改前端任何代码前必读（分层/store/渲染策略/生命周期）
- `frontend/CONSTRAINTS.md` — 修改前端任何代码前必读（API 契约/视觉/性能/生命周期）
- `Makefile` — 新增或修改开发命令时必读（命令契约见 INIT.md）

### 特定场景必读
- `INIT.md` — 执行项目初始化（F01）或调整初始化流程前必读
- `docs/features.md` — 开始或完成任何功能点时必读（状态由验证脚本更新，禁止手改）
- `docs/data_struct_define.md` — 修改实体/关系 schema、新增字段或新表时必读（9 张表数据蓝图）
- `docs/testing.md` — 编写任何测试或判定功能完成前必读（层级定义/DoD/目录/模板）
- `docs/tests/FXX_*.md` — 实现对应功能点时创建、验证通过后更新状态（每功能一份测试文档）
- `docs/architecture_checks.md` — 新增或修改架构约束/检查规则前必读（约束→检查映射表）
- `docs/lessons.md` — 代码审查或发现新错误类型时必读必更（审查反馈提升流程）
