# F02 实体 CRUD API — 测试文档

## 测试目标
验证 POST/GET/PATCH/DELETE /api/entities 全链路：properties 按类型校验、id 系统生成且不可变、删除时应用层引用校验（ReferentialError）+ DB 层外键 ON DELETE RESTRICT 双层防线、@ 检索（名称/别名/type 过滤），以及统一错误三要素结构。

## 层级矩阵
| 层级 | 用例 | 测试文件 | 必须 | 状态 |
|------|------|----------|------|------|
| L1 单元 | U1–U10: service 层创建/校验/读宽容/404/局部更新/id 不可变/properties 合并/删除校验/删除成功/检索 | backend/tests/unit/test_entities_service.py | 必须 | pass |
| L2 集成 | I1–I10: CRUD 全链路、@ 检索、422 三要素、PATCH 合并、id 不可变、404 三要素、删除 204/409、DB RESTRICT 兜底、foreign_key_check 巡检、WAL 持久化 | backend/tests/integration/test_entities_api.py | 必须 | pass |
| L3 E2E | 不适用（features.md F02 E2E 列=否，无跨组件修改） | — | 不适用 | 不适用 |

## 用例说明
### L1 单元（U1–U10，mock repository）
- U1: 创建成功，id 带类型前缀（char- 等）、字段完整回填
- U2: properties 已声明字段类型不符抛 ValidationError，消息含三要素
- U3: 未声明的 properties 字段保留（schema 演进宽容）
- U4: 读取不存在实体抛 NotFoundError（三要素完整）
- U5: 局部更新仅变更显式提供的字段，name 变更不影响 id
- U6: 请求体携带 id 字段直接被请求模型拒绝（id 不可变）
- U7: properties 局部更新为浅合并，保留其余字段
- U8: 被关系引用时删除抛 ReferentialError（应用层防线）
- U9: 无引用时删除成功（物理删除）
- U10: 检索名称与别名均可命中，type 过滤生效

### L2 集成（I1–I10，真实 SQLite 临时库，router→service→repository）
- I1: 创建→详情回读一致，201 + 系统生成 id
- I2: @ 检索：名称命中、别名命中、type 过滤三项全部生效
- I3: properties 类型校验（HTTP 层）422 + 统一三要素 + 无残留数据
- I4: PATCH 局部更新全链路：id 不变，properties 合并语义
- I5: PATCH 携带 id 被 422 拒绝且统一三要素结构，数据未改动
- I6: GET/DELETE 不存在实体均返回 404 统一三要素
- I7: 无引用实体 DELETE 204，随后 GET 404
- I8: 旁路直插真实关系行后，DELETE 返回 409 REFERENTIAL_INTEGRITY，实体仍在
- I9: 旁路裸 DELETE 被外键 RESTRICT 拦截（IntegrityError），foreign_key_check 为空（无幽灵节点）
- I10: 应用连接激活的 WAL 模式持久于数据库文件（PRAGMA journal_mode=wal）

## 验收判定
- L1: `pytest tests/unit/test_entities_service.py` — 10 passed
- L2: `pytest tests/integration/test_entities_api.py` — 10 passed
- `make check` 通过（ruff/format/lint-imports/mypy/pytest + 前端 typecheck/lint/build）

所有"必须"层级通过 + 状态列全 pass + make check 通过 → 功能完成。
