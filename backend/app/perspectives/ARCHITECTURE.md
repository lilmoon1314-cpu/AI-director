# perspectives 模块 — 视角过滤

## 职责

- 三种视角的图数据查询：author（全知）/ character（受限）/ audience（仅已展示）
- 聚合 entities + relations 并按视角规则过滤，输出图可视化所需节点/边集合
- 视角可见性判定（单一事实源原则的唯一执行点）

## 对外接口

### service 层（其他模块唯一入口）

| 函数 | 说明 | 异常 |
|------|------|------|
| `get_graph(perspective: Literal["author","character","audience"], character_id: str | None) -> GraphData` | 返回过滤后的节点+边 | PerspectiveError（character 视角缺 character_id 或角色不存在） |
| `filter_entities_for_agent(...) -> list[EntityBrief]` | 供 agent 模块过滤可注入上下文的实体 | — |

`GraphData = { nodes: list[EntityBrief], edges: list[RelationBrief] }`（Brief 为不含全量 properties 的轻量投影，图渲染够用即止）。

### HTTP 路由（/api/graph）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/graph?perspective=author | 全知视图 |
| GET | /api/graph?perspective=character&character_id=X | 角色受限视图 |
| GET | /api/graph?perspective=audience | 观众视图 |

### 过滤规则（单一事实源的执行契约）

| 视角 | 实体可见 | 关系可见 |
|------|----------|----------|
| author | 全部 | 全部 |
| character | `character_id ∈ known_by`（event/concept 类按各自 known 字段）或与该角色有可见关系 | `character_id ∈ known_by` |
| audience | `audience_known == true` | `audience_known == true` |

## 依赖

- 依赖：core、entities（get_many / search）、relations（get_all）
- 被依赖：agent（上下文过滤）、frontend（主数据源）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 perspectives 前必读）。
