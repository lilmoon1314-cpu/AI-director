# ARCHITECTURE.md — 全局模块架构文档

> 影视多智能体协作平台（第 1 批 MVP）。本文档描述系统全局架构、模块依赖与核心数据流；各模块的职责/接口/依赖细节见其目录内的 ARCHITECTURE.md（路由见 AGENTS.md「专题文档路由」）。

## 1. 系统上下文

```
┌────────────────────────────────────────────────────┐
│  frontend（React 18 + TS + Vite + AntV G6 + Zustand）│
│  views → stores → api（OpenAPI 自动生成类型）        │
└───────────────────── REST / SSE ───────────────────┘
┌────────────────────────────────────────────────────┐
│  backend（单一 FastAPI 进程，模块化单体）            │
│  ┌──────────┬───────────┬────────────────┐         │
│  │ entities │ relations │ perspectives   │         │
│  ├──────────┼───────────┴────────────────┤         │
│  │ assets   │ agent                      │         │
│  └──────────┴────────────────────────────┘         │
│              core（配置/DB会话/异常/日志）           │
└──────────────── SQLAlchemy 2.0 (async) ────────────┘
┌────────────────────────────────────────────────────┐
│  SQLite（WAL，主库 app.db + 独立资产库 assets.db）   │
│  + data/assets/ 图片文件存储                        │
└────────────────────────────────────────────────────┘
```

## 2. 架构风格

模块化单体（Modular Monolith）+ 前后端分离（决策记录：DECISIONS.md 2026-08-24）。

- 单一 FastAPI 进程承载全部领域模块，模块间仅通过 service 层接口调用。
- **禁止跨模块 import 其他模块的 ORM 模型 / repository / 内部函数**（根 CONSTRAINTS.md §2「架构总原则」；后端细则见 backend/CONSTRAINTS.md「模块解耦与事务」）。
- 模块边界即第 2 批微服务拆分边界：将 service 接口升级为 HTTP/gRPC 即可独立部署。

## 3. 模块依赖图

```
core ← entities / relations / perspectives / assets / agent（所有模块依赖 core）
entities ← relations（端点校验）/ perspectives（图聚合）/ assets（实体存在校验）/ agent（草案落库）
relations ← perspectives（图聚合）
perspectives ← agent（上下文视角过滤）
```

箭头=依赖方向，跨模块仅经 service 层。assets 仅依赖 entities（单向）；实体删除后的资产清理走读取时孤儿清扫而非删除回调，避免 assets↔entities 循环依赖（DECISIONS 2026-09-05）。

## 4. 模块清单

| 模块 | 路径 | 职责摘要 | 详细文档 |
|------|------|----------|----------|
| core | backend/app/core | 配置、DB 会话、统一异常、日志 | core/ARCHITECTURE.md |
| entities | backend/app/entities | 7 类实体 CRUD、类型校验、检索 | entities/ARCHITECTURE.md |
| relations | backend/app/relations | 关系 CRUD、动态属性、端点校验 | relations/ARCHITECTURE.md |
| perspectives | backend/app/perspectives | 作者/角色/观众三视角过滤查询 | perspectives/ARCHITECTURE.md |
| assets | backend/app/assets | 资产库（独立 assets.db）：图片上传、通用资产 CRUD、实体 HTML 资产页 | assets/ARCHITECTURE.md |
| agent | backend/app/agent | LLM 多轮对话、实体建议草案 | agent/ARCHITECTURE.md |
| frontend | frontend/ | 图谱工作台 SPA | frontend/ARCHITECTURE.md |

## 5. 核心数据流（按业务场景）

### 5.1 实体/关系 CRUD（作者全知）
表单提交 → `POST/PATCH /api/entities|relations` → router（Pydantic 校验）→ service（业务规则：id 生成、视角标记完整性、删除引用校验）→ repository（ORM）→ SQLite → 响应 EntityRead → 前端 stores 刷新 → G6 按需更新节点/边。

### 5.2 视角过滤查询
前端切换视角 → `GET /api/graph?perspective=author|character|audience&character_id=?` → perspectives.service 聚合 entities + relations 全量 → 规则过滤：
- author：不过滤，返回全部（含秘密）
- character：仅 `character_id ∈ known_by` 的实体/关系
- audience：仅 `audience_known == true`
→ 返回过滤后的节点/边集合 → 前端全量替换图数据重绘。**过滤只发生在读取层，库中始终只有一份全知数据（单一事实源）。**

### 5.3 资产管理（HTML 形态资产库）
图片上传 → `POST /api/assets/images`（multipart）→ assets.service 校验类型白名单/大小上限（阈值来自 config）→ uuid 重命名后流式写盘 data/assets/ → 元数据入独立资产库 assets.db。通用资产（表情/风格/植被等参考）经表单创建、模板渲染为自包含 HTML 存库；项目资产=主库实体：卡片列表（缩略图/名称/概述，按类型分组）由 assets.service 跨库聚合，实体 HTML 资产页按 `entity.updated_at` 惰性生成、过期再生；实体删除后卡片列表请求触发孤儿清扫（记录+图片文件）。

### 5.4 Agent 对话与确认写入
用户消息 → `POST /api/agent/chat`（SSE 流式）→ agent.service 组装上下文（**仅注入当前视角可见实体**，经 perspectives 过滤）→ LLM 生成回复/实体建议草案（结构化 JSON）→ 前端渲染草案表单 → 用户确认 → 调 entities/relations service 落库。

## 6. 分阶段演进路线

| 阶段 | 范围 | 架构形态 |
|------|------|----------|
| 第 1 批（当前） | 实体/关系管理、三视角过滤、图可视化、@选择器、资产管理（HTML 资产库）、Agent 辅助创建 | 模块化单体 |
| 第 2 批（规划） | 作者/角色/观众多 Agent 工作流、场景生成、剧本审查、Ledger 状态管理（新增 7 张表）、批量生成控制台 | 按模块边界拆分微服务：agent 与生成类负载独立伸缩，entities/relations 可合并为"世界观数据服务" |

## 7. 文档体系导航

- 硬约束（禁止/必须）: 根 CONSTRAINTS.md（全局横切 + 模块约束文件导航，共 10 份）
- 决策记录: DECISIONS.md
- 进度: PROGRESS.md
- 数据结构蓝图（9 张表，长期）: docs/data_struct_define.md
- 功能清单: docs/features.md
- 后端/前端/领域模块架构: backend/ARCHITECTURE.md、frontend/ARCHITECTURE.md、backend/app/*/ARCHITECTURE.md
- 初始化方法论与验收清单: INIT.md
