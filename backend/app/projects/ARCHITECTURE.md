# projects 模块 — 多项目底座（F11）

## 职责

- 项目 CRUD（id 系统生成；名称去空白非空；计数器只读于客户端）
- 默认项目不变量：固定 id `project-default`，lifespan 幂等确保存在；不可删除、可改名（无 project_id 请求的兜底归属目标）
- 归属校验出口：`ensure_exists` 供 entities / relations / perspectives / assets 写读路径校验项目存在
- 反规范化计数器（entity_count / relation_count）与最近活跃时间（updated_at）的唯一写入口 `touch`——由领域模块写路径在各自事务内调用（projects 读取零跨模块聚合）
- 删除项目级联编排（位于 router 组合层，见下）

## 存储模型（主库 app.db，Alembic）

```
projects
├── id (PK, "project-" 前缀系统生成；默认项目固定 id)
├── name / description
├── entity_count / relation_count   # 反规范化计数器（事务内维护）
└── created_at / updated_at         # updated_at = 最近活跃（touch 刷新）
```

F11 迁移同时为 `entities` / `relationships` 增加 `project_id`（FK projects + 索引），存量数据打包进默认项目。

## 对外接口

### service 层（其他模块唯一入口）

| 函数 | 说明 | 异常 |
|------|------|------|
| `ensure_default_project(session)` | 幂等确保默认项目存在（lifespan 调用） | — |
| `ensure_exists(session, project_id)` | 归属校验（领域模块写读路径） | NotFoundError |
| `create(session, schema) -> ProjectRead` | 创建项目（计数器 0 起步） | — |
| `get(session, project_id) -> ProjectRead` | 详情 | NotFoundError |
| `list_projects(session) -> list[ProjectRead]` | 全量（updated_at 倒序 + id 稳定序） | — |
| `update(session, project_id, schema) -> ProjectRead` | 改名 / 描述 | NotFoundError |
| `assert_deletable(session, project_id)` | 删除前置校验（存在 + 非默认） | NotFoundError / ValidationError |
| `delete(session, project_id)` | 删除项目行并 commit（级联主库部分的收口提交） | NotFoundError / ValidationError |
| `touch(session, project_id, *, entity_delta=0, relation_delta=0)` | 事务内计数器/活跃时间维护（**不自行 commit**，调用方事务保证原子） | NotFoundError |
| `DEFAULT_PROJECT_ID` | 默认项目固定 id 常量（领域模块缺省归属） | — |

### HTTP 路由（/api/projects）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/projects | 创建（201） |
| GET | /api/projects | 列表（最近活跃倒序） |
| GET | /api/projects/{project_id} | 详情 |
| PATCH | /api/projects/{project_id} | 改名 / 描述（id 与计数器不可变） |
| DELETE | /api/projects/{project_id} | 级联删除（默认项目 422 拒绝） |

## 级联删除编排（router 组合层）

`assert_deletable`（先校验，失败时数据零损伤）→ `relations.delete_by_project`（FK RESTRICT 先行）→ `entities.delete_by_project`（返回实体 id 集合）→ `projects.delete`（commit 原子提交主库三步删除）→ `assets.sweep_entity_assets`（独立事务显式清扫记录/图片/物理文件；失败由既有读取时孤儿清扫兜底，DECISIONS 2026-09-06）。

## 依赖

- 依赖：core（零领域模块依赖——import-linter 契约「projects 业务层零领域依赖」约束 service/repository/models/schemas；router 作为请求级组合点编排级联，是唯一例外）
- 被依赖：entities / relations / perspectives / assets（经 service：ensure_exists / touch / DEFAULT_PROJECT_ID）；frontend（项目首屏 / 顶栏切换器）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 projects 前必读）。
