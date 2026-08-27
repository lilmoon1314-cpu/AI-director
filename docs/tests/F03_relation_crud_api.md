# F03 关系 CRUD API — 测试文档

## 测试目标
验证 /api/relations 的 CRUD 全链路：端点存在性校验（经 entities.service）、自环拒绝、重复关系拒绝（ConflictError）、known_by 成员校验（存在且为 character），以及 entities×relations 跨组件的用户路径闭环。

## 层级矩阵
| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1: 创建成功（id 前缀/字段装配/known_by 校验通过路径） | tests/unit/test_relations_service.py | 必须 | pass |
| L1 单元 | U2: 自环关系拒绝（ValidationError 三要素） | tests/unit/test_relations_service.py | 必须 | pass |
| L1 单元 | U3: 端点缺失（NotFoundError 定位 field=source/target） | tests/unit/test_relations_service.py | 必须 | pass |
| L1 单元 | U4: 重复关系拒绝（ConflictError 含 existing_id） | tests/unit/test_relations_service.py | 必须 | pass |
| L1 单元 | U5: known_by 成员缺失（ValidationError） | tests/unit/test_relations_service.py | 必须 | pass |
| L1 单元 | U6: known_by 成员非 character（ValidationError） | tests/unit/test_relations_service.py | 必须 | pass |
| L1 单元 | U7: 读取不存在关系（NotFoundError） | tests/unit/test_relations_service.py | 必须 | pass |
| L1 单元 | U8: 局部更新（动态字段更新、端点不变、known_by 重校验） | tests/unit/test_relations_service.py | 必须 | pass |
| L1 单元 | U9: 更新请求体携带 id/source/target/type 被模型拒绝 | tests/unit/test_relations_service.py | 必须 | pass |
| L1 单元 | U10: 删除（存在即删/不存在抛 NotFoundError） | tests/unit/test_relations_service.py | 必须 | pass |
| L1 单元 | U11: 条件查询（过滤参数透传 + RelationRead 装配） | tests/unit/test_relations_service.py | 必须 | pass |
| L2 集成 | I1: 创建→详情全链路（201、rel- 前缀、回读一致） | tests/integration/test_relations_api.py | 必须 | pass |
| L2 集成 | I2: 端点缺失 404 统一结构（source/target 两例、无残留） | tests/integration/test_relations_api.py | 必须 | pass |
| L2 集成 | I3: 自环拒绝 422 统一结构 | tests/integration/test_relations_api.py | 必须 | pass |
| L2 集成 | I4: 重复关系 409 CONFLICT；反向组合允许创建 | tests/integration/test_relations_api.py | 必须 | pass |
| L2 集成 | I5: known_by 校验（缺失成员/非 character 成员两例 422） | tests/integration/test_relations_api.py | 必须 | pass |
| L2 集成 | I6: 条件查询（source/target/type 过滤生效） | tests/integration/test_relations_api.py | 必须 | pass |
| L2 集成 | I7: PATCH 动态字段更新（id 不变；type 不可变 422） | tests/integration/test_relations_api.py | 必须 | pass |
| L2 集成 | I8: 数值越界（trust=1.5 → 422 统一结构） | tests/integration/test_relations_api.py | 必须 | pass |
| L2 集成 | I9: 不存在关系 GET/PATCH/DELETE 均 404 三要素 | tests/integration/test_relations_api.py | 必须 | pass |
| L2 集成 | I10: 删除链路（204 → GET 转 404） | tests/integration/test_relations_api.py | 必须 | pass |
| L3 E2E | E1: 关系全生命周期（跨组件：entities+relations 协作） | tests/e2e/test_relations_flow.py | 必须 | pass |
| L3 E2E | E2: 引用阻断与解除闭环（F02 删除防线 × F03 删除关系协作） | tests/e2e/test_relations_flow.py | 必须 | pass |

## 用例说明
- U1: 前置 mock repository + entities.service.get_many 返回全部成员；动作 create；预期 id 以 rel- 开头、动态字段/known_by/时间戳完整。
- U2: 前置 source==target；动作 create；预期 ValidationError 且三要素齐全。
- U3: 前置 get_many 桩缺失 target；动作 create；预期 NotFoundError 且 detail.field 指向缺失端点。
- U4: 前置 find_same 桩返回既有关系；动作 create；预期 ConflictError 且 detail.existing_id 指向既有关系。
- U5: 前置 known_by 含库中不存在的 id；动作 create；预期 ValidationError 且 detail 定位缺失成员。
- U6: 前置 known_by 成员存在但 type=location；动作 create；预期 ValidationError（reason=not_character）。
- U7: 前置空库；动作 get；预期 NotFoundError 三要素。
- U8: 前置已有关系；动作 update(trust, known_by)；预期 动态字段更新、source/target/type/id 不变、known_by 经重校验。
- U9: 前置无；动作构造 RelationUpdate(id=..)；预期 pydantic ValidationError（extra=forbid 拒绝不可变字段）。
- U10: 前置已有关系/不存在 id 两例；动作 delete；预期 存在即从存储移除；不存在抛 NotFoundError。
- U11: 前置 mock query；动作 get_all(source=.., type=..)；预期 过滤参数原样透传 repository、返回 RelationRead 列表。
- I1: 前置两实体；动作 POST 后 GET 详情；预期 201、id 带 rel- 前缀、字段回读一致。
- I2: 前置一个实体；动作 POST 缺 source/缺 target 两例；预期 404 NOT_FOUND 三要素且 detail.field 正确，库中无残留关系。
- I3: 前置一个实体；动作 POST source==target；预期 422 VALIDATION_ERROR 三要素。
- I4: 前置 A→B(type=mentor) 已存在；动作 同三元组再 POST；预期 409 CONFLICT；动作 B→A 同 type POST；预期 201（有向语义，反向合法）。
- I5: 前置两实体；动作 POST known_by=[不存在 id] / [location 实体 id]；预期均 422 VALIDATION_ERROR 三要素定位成员。
- I6: 前置三条关系（不同端点/类型）；动作 GET ?source= / ?target= / ?type=；预期 各过滤器命中且互不误报。
- I7: 前置已有关系；动作 PATCH(trust=0.9, promise=..)；预期 200、id/source/target/type 不变；动作 PATCH(type=..)；预期 422（不可变字段被 extra=forbid 拒绝）。
- I8: 前置已有关系；动作 PATCH(trust=1.5)；预期 422 统一三要素结构（Pydantic 请求校验经全局处理器转换）。
- I9: 前置空库；动作 GET/PATCH/DELETE 不存在 id；预期均 404 NOT_FOUND 三要素。
- I10: 前置两实体+一关系；动作 DELETE 关系；预期 204 无响应体，随后 GET 转 404。
- E1: 公开接口完整用户路径：建两实体 → 建关系（含 known_by/动态属性）→ 读详情 → PATCH 信任度与 known_by → 条件查询 → 删关系；全程仅走 HTTP（testing.md §6）。
- E2: 跨组件闭环：删除被引用实体 409（F02 应用层防线）→ 删除关系 → 再删实体 204（引用解除后放行）；验证两模块协作一致。

## 验收判定
所有"必须"层级通过 + 状态列全 pass + make check 通过 → 功能完成。
