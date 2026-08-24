# relations 模块 — 关系管理

## 职责

- 实体间关系的 CRUD（如 BELONGS_TO / KNOWS_ABOUT / TRUSTS）
- 动态关系属性（trust/intimacy/dependency/resentment、public/private_identity、promise、status 等）的校验与更新
- 视角可见性标记（`known_by` / `audience_known`）的读写与完整性校验
- 关系端点存在性校验（source/target 必须为已存在实体）

## 对外接口

### service 层（其他模块唯一入口）

| 函数 | 说明 | 异常 |
|------|------|------|
| `create(schema: RelationCreate) -> RelationRead` | 校验端点存在后创建 | NotFoundError（端点缺失）/ ValidationError |
| `get(relation_id: str) -> RelationRead` | 按 id 读取 | NotFoundError |
| `update(relation_id, schema: RelationUpdate) -> RelationRead` | 局部更新动态属性 | NotFoundError / ValidationError |
| `delete(relation_id: str) -> None` | 删除关系 | NotFoundError |
| `get_all() -> list[RelationRead]` | 全量读取（供 perspectives/sync 聚合） | — |

### HTTP 路由（/api/relations）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/relations | 创建 |
| GET | /api/relations/{id} | 详情 |
| PATCH | /api/relations/{id} | 局部更新 |
| DELETE | /api/relations/{id} | 删除 |
| GET | /api/relations?source=&target=&type= | 条件查询 |

## 数据模型（MVP，见 docs/data_struct_define.md §2）

表 `relationships`：`id`(PK) / `source` / `target` / `type` / 动态属性列（trust 等） / `known_by`(JSON) / `audience_known` / `created_at` / `updated_at`。MVP 落地时将 data_struct_define.md 中的静态属性（dynamic_type/element_interaction）并入 `properties` JSON 列，动态数值列保持独立以便查询。

## 依赖

- 依赖：core、entities（经 entities.service 校验端点存在）
- 被依赖：perspectives（图查询聚合）、sync（导入导出）、agent（建议草案落库）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 relations 前必读）。
