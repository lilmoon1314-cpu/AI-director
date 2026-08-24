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
│  ├──────────┼───────────┼────────────────┤         │
│  │ assets   │ sync      │ agent          │         │
│  └──────────┴───────────┴────────────────┘         │
│              core（配置/DB会话/异常/日志）           │
└──────────────── SQLAlchemy 2.0 (async) ────────────┘
┌────────────────────────────────────────────────────┐
│  SQLite（WAL）+ data/assets/ 文件存储               │
└────────────────────────────────────────────────────┘
```

## 2. 架构风格

模块化单体（Modular Monolith）+ 前后端分离（决策记录：DECISIONS.md 2026-08-24）。

- 单一 FastAPI 进程承载全部领域模块，模块间仅通过 service 层接口调用。
- **禁止跨模块 import 其他模块的 ORM 模型 / repository / 内部函数**（根 CONSTRAINTS.md §2「架构总原则」；后端细则见 backend/CONSTRAINTS.md「模块解耦与事务」）。
- 模块边界即第 2 批微服务拆分边界：将 service 接口升级为 HTTP/gRPC 即可独立部署。

## 3. 模块依赖图

```
                 ┌──────────────┐
                 │     core     │  配置 / DB 会话 / 统一异常 / 日志
                 └──────┬───────┘
        ┌───────────────┼────────────────┐
   ┌────▼─────┐   ┌─────▼──────┐         │
   │ entities │   │ relations  │         │
   └──┬──┬────┘   └─────┬──────┘         │
      │  └───────┐       │          ┌────▼─────┐
      │         │       │          │  assets  │
┌─────▼─────┐ ┌─▼───────▼───┐      └──────────┘
│   sync    │ │perspectives │
└───────────┘ └──────┬──────┘
                     │
               ┌─────▼─────┐
               │   agent   │
               └───────────┘
```

依赖方向（箭头=依赖）：core ← 所有模块；entities ← relations/perspectives/assets/sync/agent；relations ← perspectives/sync；perspectives ← agent。

## 4. 模块清单

| 模块 | 路径 | 职责摘要 | 详细文档 |
|------|------|----------|----------|
| core | backend/app/core | 配置、DB 会话、统一异常、日志 | core/ARCHITECTURE.md |
| entities | backend/app/entities | 7 类实体 CRUD、类型校验、检索 | entities/ARCHITECTURE.md |
| relations | backend/app/relations | 关系 CRUD、动态属性、端点校验 | relations/ARCHITECTURE.md |
| perspectives | backend/app/perspectives | 作者/角色/观众三视角过滤查询 | perspectives/ARCHITECTURE.md |
| assets | backend/app/assets | 文件上传/存储/静态访问 | assets/ARCHITECTURE.md |
| sync | backend/app/sync | Markdown 导入导出、冲突检测 | sync/ARCHITECTURE.md |
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

### 5.3 资产上传
选择文件 → `POST /api/assets`（multipart）→ assets.service 校验类型白名单/大小上限（阈值来自 config）→ uuid 重命名后流式写盘 data/assets/ → 路径与元数据写入实体 properties.assets → 前端节点详情展示缩略图与链接。

### 5.4 Markdown 导入导出
- 导出：`GET /api/sync/export` → sync.service 读取全部实体/关系 → YAML front matter + Markdown 正文 → 下载。
- 导入：上传 Markdown → 解析 → 与库内 `updated_at` 比对生成冲突报告 → 用户确认后应用变更。

### 5.5 Agent 对话与确认写入
用户消息 → `POST /api/agent/chat`（SSE 流式）→ agent.service 组装上下文（**仅注入当前视角可见实体**，经 perspectives 过滤）→ LLM 生成回复/实体建议草案（结构化 JSON）→ 前端渲染草案表单 → 用户确认 → 调 entities/relations service 落库。

## 6. 分阶段演进路线

| 阶段 | 范围 | 架构形态 |
|------|------|----------|
| 第 1 批（当前） | 实体/关系管理、三视角过滤、图可视化、@选择器、资产上传、Markdown 同步、Agent 辅助创建 | 模块化单体 |
| 第 2 批（规划） | 作者/角色/观众多 Agent 工作流、场景生成、剧本审查、Ledger 状态管理（新增 7 张表）、批量生成控制台 | 按模块边界拆分微服务：agent 与生成类负载独立伸缩，entities/relations 可合并为"世界观数据服务" |

## 7. 文档体系导航

- 硬约束（禁止/必须）: 根 CONSTRAINTS.md（全局横切 + 模块约束文件导航，共 10 份）
- 决策记录: DECISIONS.md
- 进度: PROGRESS.md
- 数据结构蓝图（9 张表，长期）: docs/data_struct_define.md
- 功能清单: docs/features.md
- 后端/前端/领域模块架构: backend/ARCHITECTURE.md、frontend/ARCHITECTURE.md、backend/app/*/ARCHITECTURE.md
- 初始化方法论与验收清单: INIT.md
