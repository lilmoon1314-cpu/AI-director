# perspectives 模块 — 视角过滤

## 职责

- 三种视角的图数据查询：author（全知）/ character（受限）/ audience（仅已展示）
- 聚合 entities + relations 并按视角规则过滤，输出图可视化所需节点/边集合
- 视角可见性判定（单一事实源原则的唯一执行点）

## 分层结构（F04 落地）

本模块为**只读聚合模块**，无 ORM 表与数据访问，故不设 models.py / repository.py：

```
router.py       # GET /api/graph 参数解析与响应包装
service.py      # get_graph：唯一对外接口，可见性判定只发生在此
schemas.py      # Perspective / GraphNode / GraphEdge / GraphData 投影模型
```

跨模块数据以结构契约（typing.Protocol 只读属性）约束，不 import 其他模块 schemas（backend/CONSTRAINTS.md）。

## 对外接口

### service 层（其他模块唯一入口）

| 函数 | 说明 | 异常 |
|------|------|------|
| `get_graph(session, *, perspective, character_id=None) -> GraphData` | 返回过滤后的节点+边（只读，不开事务） | PerspectiveError（character 视角缺 character_id / 角色不存在 / 非 character 类型，均 403） |
| `filter_entities_for_agent(...)` | 供 agent 模块过滤可注入上下文的实体 | **计划（F10 落地）**，当前未实现 |

`GraphData = { nodes: list[GraphNode], edges: list[GraphEdge] }`（GraphNode：id/type/name/aliases；GraphEdge：id/source/target/type——轻量投影，不含 properties/description/known_by，收窄泄露通道）。

### HTTP 路由（/api/graph）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/graph?perspective=author | 全知视图 |
| GET | /api/graph?perspective=character&character_id=X | 角色受限视图 |
| GET | /api/graph?perspective=audience | 观众视图 |

perspective 为必填参数（无默认值，避免缺参误入全知视图）；非法枚举值由 Pydantic 请求校验 422。

### 过滤规则（单一事实源的执行契约）

| 视角 | 实体可见 | 关系可见 |
|------|----------|----------|
| author | 全部 | 全部 |
| character | 视角角色自身（恒可见）∪ known 标记命中（event→`properties.known_by`、item→`properties.seen_by` 含视角角色 id）∪ 可见关系端点推导 | `character_id ∈ known_by` |
| audience | `audience_known == true` | `audience_known == true` 且双端实体均可见（防悬空边与间接泄露） |

- known 标记值非列表（脏数据）容错不命中（读宽容）；未登记标记字段的类型仅经可见关系端点推导。
- character 视角错误一律 PerspectiveError 403，`detail.reason ∈ {missing_character_id, character_not_found, not_character_type}`。

## 依赖

- 依赖：core、entities（search + get_many，service 层调用）、relations（get_all，service 层调用）
- 被依赖：agent（上下文过滤，F10）、frontend（主数据源）

## 约束

见本模块 [CONSTRAINTS.md](./CONSTRAINTS.md)（实现/修改 perspectives 前必读）。
