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
| `create(session, schema: RelationCreate) -> RelationRead` | 自环/端点存在性/known_by 成员/重复三元组四重校验后创建 | NotFoundError（端点缺失）/ ValidationError（自环、known_by）/ ConflictError（重复） |
| `get(session, relation_id: str) -> RelationRead` | 按 id 读取 | NotFoundError |
| `update(session, relation_id, schema: RelationUpdate) -> RelationRead` | 局部更新动态属性（known_by 更新时重校验；端点与 id/type 不可变） | NotFoundError / ValidationError |
| `delete(session, relation_id: str) -> None` | 删除关系（即解除对两端实体的引用） | NotFoundError |
| `get_all(session, *, source/target/rel_type 可选) -> list[RelationRead]` | 条件查询（无过滤返回全量，供 perspectives 聚合） | — |
| `count_by_entity(session, entity_id: str) -> int` | 实体被引用计数（entities.service 删除防线数据源） | — |

校验取数约定: 端点/known_by 校验统一经 `entities.service.get_many` 单次批量读取
（禁止直查 entities 表，见本模块 CONSTRAINTS.md）。

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
- 被依赖：perspectives（图查询聚合）、agent（建议草案落库）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 relations 前必读）。
