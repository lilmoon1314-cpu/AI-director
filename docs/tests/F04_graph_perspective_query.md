# F04 三视角过滤图查询 — 测试文档

## 测试目标
验证 GET /api/graph?perspective=author/character/audience 按视角规则过滤节点/边：author 全量；character 按 known_by（含 event/item 的 known 标记与可见关系端点推导）过滤且不泄露被过滤实体名；audience 按 audience_known 过滤（边须双端可见）。

## 测试世界（L1/L2/L3 共用种子数据）

| id | 类型 | 名称 | audience_known | known 标记（properties） |
|----|------|------|----------------|--------------------------|
| char-a | character | 周兰 | true | — |
| char-b | character | 沈墨 | false | — |
| char-c | character | 陆离 | true | —（孤立：无关系无标记） |
| item-x | item | 青铜镜 | false | seen_by=["char-a"] |
| event-e | event | 夜探药庐 | true | known_by=["char-b"] |
| loc-l | location | 青云山 | true | — |

| id | source→target | type | known_by | audience_known |
|----|---------------|------|----------|----------------|
| rel-1 | char-a→char-b | ALLY | ["char-a"] | true |
| rel-2 | char-a→loc-l | LIVES_IN | ["char-a","char-b"] | true |
| rel-3 | char-b→event-e | PARTICIPATES | ["char-b"] | true |

期望视图：

| 视角 | 节点 | 边 |
|------|------|----|
| author | 全部 6 | 3 |
| audience | {周兰, 陆离, 夜探药庐, 青云山} | {rel-2}（rel-1/rel-3 因沈墨不可见被双端规则排除） |
| character=char-a | {周兰, 沈墨, 青铜镜, 青云山} | {rel-1, rel-2} |
| character=char-b | {沈墨, 周兰, 夜探药庐, 青云山} | {rel-2, rel-3} |
| character=char-c | {陆离}（视角角色自身恒可见） | {} |

不泄露断言对象：character=char-a 视角下，响应文本不得出现「陆离」「夜探药庐」。

## 层级矩阵
| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1: author 全量 | tests/unit/test_perspectives_service.py | 必须 | pass |
| L1 单元 | U2: audience 过滤 + 边双端规则 | 同上 | 必须 | pass |
| L1 单元 | U3: character 三态参数化 | 同上 | 必须 | pass |
| L1 单元 | U4: character 缺 character_id | 同上 | 必须 | pass |
| L1 单元 | U5: character_id 无效参数化 | 同上 | 必须 | pass |
| L1 单元 | U6: known 标记边界参数化 | 同上 | 必须 | pass |
| L1 单元 | U7: 投影轻量（不泄露通道） | 同上 | 必须 | pass |
| L1 单元 | U8: 空库参数化 | 同上 | 必须 | pass |
| L1 单元 | U9: schema/协议/装饰契约参数化（§9 变异补充：GraphData 默认空集、GraphNode.type 必填、协议成员只读 property、checkpoint 装饰在位） | 同上 | 必须 | pass |
| L2 集成 | I1: author 200 全量 | tests/integration/test_graph_api.py | 必须 | pass |
| L2 集成 | I2: audience 200 过滤 | 同上 | 必须 | pass |
| L2 集成 | I3: character 三态参数化 | 同上 | 必须 | pass |
| L2 集成 | I4: 缺 character_id → 403 | 同上 | 必须 | pass |
| L2 集成 | I5: character_id 无效参数化 → 403 | 同上 | 必须 | pass |
| L2 集成 | I6: perspective 非法值参数化 → 422 | 同上 | 必须 | pass |
| L2 集成 | I7: 不泄露断言（响应文本） | 同上 | 必须 | pass |
| L2 集成 | I8: 空库 → 空图 | 同上 | 必须 | pass |
| L3 E2E | E1: 全链路三视角场景（跨组件：entities+relations+perspectives） | tests/e2e/test_graph_flow.py | 必须 | pass |
| L3 E2E | E2: 视角查询只读（快照逐字节一致，perspectives/CONSTRAINTS） | 同上 | 必须 | pass |

## 用例说明
- U1: 空桩+种子世界 → get_graph(author) → 6 节点 3 边、节点按 name 排序稳定（设计依据：等价类—perspective 有效-author）
- U2: 种子世界 → get_graph(audience) → 恰 {周兰,陆离,夜探药庐,青云山} + 仅 rel-2（rel-1/rel-3 端点沈墨不可见被双端规则排除）（设计依据：等价类—perspective 有效-audience；含边可见性双端规则）
- U3 参数化: character ∈ {char-a, char-b, char-c} → 期望节点/边集合逐 id 比对；char-c 为孤立角色仅自身可见（设计依据：等价类—perspective 有效-character 三态：边+item 标记 / 边+event 标记 / 孤立）
- U4: perspective=character 未传 character_id → PerspectiveError，detail.reason=missing_character_id（设计依据：无效等价类—必选参数缺失）
- U5 参数化: character_id ∈ {不存在的 id, loc-l(非 character 类型)} → PerspectiveError，detail.reason ∈ {character_not_found, not_character_type}（设计依据：无效等价类—角色不存在 / 角色类型不符）
- U6 参数化: marker 命中矩阵——event+known_by 含目标（命中）、item+seen_by 含目标（命中）、location 无 marker 字段（不命中）、known_by=[] 空表（不命中）、marker 值为非列表脏数据（容错不命中）（设计依据：边界值—列表空/单元素命中/脏数据；等价类—各类型 marker 字段映射）
- U7: 任意视角返回的 GraphNode 仅含 id/type/name/aliases，GraphEdge 仅含 id/source/target/type——不含 properties/description/known_by（潜在的泄露与冗余通道）（设计依据：等价类—输出契约：轻量投影）
- U8 参数化: 空库 → author/audience 均 {nodes:[], edges:[]}（设计依据：边界值—数据集空集；character 视角空库由 U5 覆盖）
- I1: 经 POST /api/entities、/api/relations 建世界 → GET /api/graph?perspective=author → 200，6 节点 3 边（设计依据：等价类—有效-author）
- I2: 同种子 → audience → 200，节点 4/边 1，rel-1 被双端规则排除（设计依据：等价类—有效-audience）
- I3 参数化: 同种子 → character×3 → 期望节点/边集合（设计依据：等价类—有效-character 三态）
- I4: character 不带 character_id → 403 PERSPECTIVE_DENIED，body 含 code/problem/cause/fix 四要素（设计依据：无效等价类—参数缺失；断言统一错误结构）
- I5 参数化: character_id=char-none / loc-l → 403，detail.reason 对应（设计依据：无效等价类—不存在/类型不符）
- I6 参数化: perspective ∈ {editor, 空串} → 422（Pydantic 请求校验），detail.errors[].loc 含 perspective（设计依据：无效等价类—Literal 枚举外）
- I7: character=char-a 的原始响应文本（JSON 序列化）不含「陆离」「夜探药庐」（设计依据：硬约束 perspectives/CONSTRAINTS—不泄露被过滤实体名）
- I8: 空库 → 200 {nodes:[], edges:[]}（设计依据：边界值—空集）
- E1: 公开 HTTP 建世界 → 三视角依次查询 → 断言三组节点/边与不泄露（设计依据：跨组件全链路主路径）
- E2: 建世界后经 GET /api/entities、/api/entities/{id}、/api/relations 导出全量数据快照 → 三视角查询 → 再次导出 → 两次快照逐字节一致（设计依据：perspectives/CONSTRAINTS 只读单一事实源，映射表 F04 行）
- U9a: 无参构造 GraphData → nodes/edges 均为空列表非 None（设计依据：§9 变异补充—default_factory=list 契约钉死）
- U9b: 缺 type 构造 GraphNode → ValidationError（设计依据：§9 变异补充—输出契约 type 必填）
- U9c 参数化: 反射检查 _EntityLike/_RelationLike 全部 12 个成员均为 property 实例（设计依据：§9 变异补充—协议只读 property 协变契约）
- U9d: get_graph 存在 __wrapped__（设计依据：§9 变异补充—@checkpoint 装饰在位，信号 2/3 采集依赖）
- U4/U5 补强（§9 变异补充）: 三要素 problem/cause/fix 文案精确断言 + detail 字典整体相等断言（原仅断言 reason 单键）

## 变异测试结果（用例实现完成后填写；自 F04 起）
- scope: app/perspectives（87 个变异体）；判杀器: tests/unit/test_perspectives_service.py + tests/integration/test_graph_api.py
- 过程: 首轮仅以 L1 单元测试判杀，kill rate 47%（41/87，存活 46）——router 路由注册/Literal 枚举类变异只有 L2 集成测试（HTTP 语义）可杀，错误三要素文案与 detail 键值类变异因 U4/U5 仅断言 reason 单键而存活。据此：判杀器纳入 L2 集成测试；U4/U5 补三要素精确断言与 detail 字典相等断言；新增 U9（schema 默认值/type 必填/协议只读 property/checkpoint 装饰在位）
- kill rate: **95.4%（83/87）≥ 85% 达标**
- 存活变异体分析（4 个，全部登记等价性）:
  - router.py #2 `tags=["graph"]→["XXgraphXX"]`: OpenAPI 分组标签，无运行时行为，无路由/响应差异
  - router.py #6/#7 Query 参数 description 文案变异: 仅影响 OpenAPI 文档展示，请求校验与响应不变
  - schemas.py #12 GraphNode.type Field description 文案变异: 仅影响 OpenAPI 文档展示，模型校验与序列化不变
  - 结论: 四者均为文档性字符串，行为层面等价；不值得以「钉死文案」用例换取 kill rate（文案修订属正常迭代）

## 验收判定
所有"必须"层级通过 + 状态列全 pass + 变异测试达标（§9：kill rate ≥ 85%，存活变异体已分析归档）+ make check 通过 → 功能完成。
