# entities 模块 — 实体管理

## 职责

- 7 类实体（character / faction / location / item / skill / event / concept）的 CRUD
- 按实体类型校验 `properties` JSON 结构（类型 schema 定义于本模块）
- 名称/别名检索（供前端 @ 实体选择器）
- 视角标记字段（`audience_known`）的读写与完整性校验
- id 生成（创建后不可变）

## 对外接口

### service 层（其他模块唯一入口）

| 函数 | 说明 | 异常 |
|------|------|------|
| `create(schema: EntityCreate) -> EntityRead` | 校验类型与 properties 后创建 | ValidationError |
| `get(entity_id: str) -> EntityRead` | 按 id 读取 | NotFoundError |
| `update(entity_id, schema: EntityUpdate) -> EntityRead` | 局部更新，校验视角标记完整性 | NotFoundError / ValidationError |
| `delete(entity_id: str) -> None` | 删除前校验关系引用 | NotFoundError / ReferentialError |
| `search(q: str, type: str | None) -> list[EntityBrief]` | 名称/别名模糊检索 | — |
| `get_many(ids: list[str]) -> list[EntityRead]` | 批量读取（供 perspectives/sync 聚合） | — |

### HTTP 路由（/api/entities）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/entities | 创建 |
| GET | /api/entities/{id} | 详情 |
| PATCH | /api/entities/{id} | 局部更新 |
| DELETE | /api/entities/{id} | 删除（引用校验） |
| GET | /api/entities?q=&type= | 检索（@选择器） |

## 数据模型（MVP，见 docs/data_struct_define.md §1）

表 `entities`：`id`(PK) / `type` / `name` / `aliases`(JSON) / `description` / `audience_known` / `properties`(JSON) / `created_at` / `updated_at`。

## 依赖

- 依赖：core
- 被依赖：relations（端点校验）、perspectives（图查询聚合）、assets（挂载目标校验）、sync（导入导出）、agent（建议草案落库）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 entities 前必读）。
