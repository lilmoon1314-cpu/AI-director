"""F02 L2 集成测试：entities API 全链路（router→service→repository→真实 SQLite 临时库）。

验证依据: docs/features.md F02 + docs/architecture_checks.md §2 —
    - CRUD 全链路与 @ 检索（公开 HTTP 接口）
    - 错误响应统一三要素结构（code/problem/cause/fix/detail）
    - 应用层 ReferentialError 防线（真实关系行落库后删除被阻断）
    - DB 层外键 RESTRICT 兜底（旁路直删被 IntegrityError 拒绝）
    - PRAGMA foreign_key_check 巡检为空（无幽灵节点）
    - WAL journal mode 由应用侧激活（持久化于数据库文件）

旁路说明: I8/I9 需要"绕过应用层校验"直接写入/删除数据以证明双层防线；
    直连引擎通过注册生产级 pragma 钩子（db._set_sqlite_pragma）保证与应用
    连接遵循同一 SQLite 约定，用后即弃避免跨事件循环复用连接池。
"""

import asyncio
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

# conftest 在导入阶段设置的环境变量：应用与旁路连接共用同一临时库文件
_DB_URL = os.environ["DATABASE_URL"]

# 旁路插入关系行的语句（列定义见 app/relations/models.py；F03 前无关系 API，只能直连构造）
_REL_INSERT_SQL = text(
    "INSERT INTO relationships"
    " (id, source, target, type, known_by, audience_known, properties,"
    "  created_at, updated_at)"
    " VALUES ('rel-test-0001', :source, :target, 'mentor', '[]', 0, '{}',"
    "         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
)


def _new_pragma_engine() -> Any:
    """新建一个与应用同等 PRAGMA 配置（WAL+外键）的独立旁路引擎。

    作用:
        为集成测试提供"绕过应用层"的直连通道；复用生产钩子 db._set_sqlite_pragma
        （私有符号访问是有意为之——锁定应用连接配置，防止配置漂移导致防线失真），
        用后 dispose，不跨事件循环复用连接池。
    参数: 无。
    返回值: AsyncEngine（新建未缓存实例）。
    异常: 无。
    依赖: sqlalchemy.ext.asyncio.create_async_engine、app.core.db._set_sqlite_pragma。
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.core import db

    engine = create_async_engine(_DB_URL)
    event.listen(engine.sync_engine, "connect", db._set_sqlite_pragma)
    return engine


def _bypass_execute(statement: Any, params: dict[str, Any] | None = None) -> IntegrityError | None:
    """在旁路连接上单语句执行，返回触发的 IntegrityError（未触发则为 None）。

    作用:
        供 DB 层 RESTRICT 兜底验证：捕获而非抛出异常，让调用方明确区分
        「约束生效」与「意外删除成功」两种结果。
    参数: statement — SQLAlchemy 可执行对象；params — 绑定参数。
    返回值: IntegrityError | None。异常: 其余异常原样上抛（由全局失败兜底）。
    依赖: sqlalchemy、asyncio。
    """

    async def runner() -> IntegrityError | None:
        engine = _new_pragma_engine()
        try:
            async with engine.begin() as conn:
                try:
                    await conn.execute(statement, params or {})
                except IntegrityError as exc:
                    return exc
                return None
        finally:
            await engine.dispose()

    return asyncio.run(runner())


def _bypass_fetchall(sql: str) -> list[tuple[Any, ...]]:
    """在旁路只读连接上执行查询并取回全部行。

    作用: 供 PRAGMA 断言（journal_mode / foreign_keys / foreign_key_check）使用。
    参数: sql — 只读 SQL 文本。
    返回值: list[tuple]。异常: 执行失败原样上抛。
    依赖: sqlalchemy、asyncio。
    """

    async def runner() -> list[tuple[Any, ...]]:
        engine = _new_pragma_engine()
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text(sql))
                return list(result.fetchall())
        finally:
            await engine.dispose()

    return asyncio.run(runner())


def _create_entity(client: TestClient, name: str, **extra: Any) -> str:
    """经公开接口创建实体并返回系统生成的 id。

    作用: 集成用例的通用前置装配（创建成功是后续操作的前提）。
    参数: client — 测试客户端；name — 实体名；extra — 覆盖/追加的载荷字段。
    返回值: str — 生成的实体 id。
    异常: AssertionError — 创建未按预期返回 201 或 id 缺失（三要素消息）。
    依赖: fastapi.testclient.TestClient。
    """
    payload: dict[str, Any] = {"type": "character", "name": name}
    payload.update(extra)
    resp = client.post("/api/entities", json=payload)
    assert resp.status_code == 201, (
        f"【问题】实体 {name} 创建失败: HTTP {resp.status_code} {resp.text}\n"
        "【原因】POST /api/entities 未按预期创建资源\n"
        "【修复】检查请求载荷与 entities 路由/service 实现"
    )
    entity_id = resp.json().get("id")
    assert entity_id, (
        f"【问题】响应缺少系统生成的 id: {resp.json()}\n"
        "【原因】id 系统生成逻辑未随响应返回\n"
        "【修复】检查 service.create 的 EntityRead 装配"
    )
    return entity_id


def _assert_error_shape(body: dict[str, Any], expected_code: str) -> None:
    """断言错误响应体满足统一三要素结构。

    作用: 集中校验 code/problem/cause/fix/detail 字段（docs/architecture_checks.md）。
    参数: body — 响应 JSON；expected_code — 期望的错误码。
    返回值: 无。异常: AssertionError — 结构缺失或码不符（三要素消息）。
    依赖: 无。
    """
    assert body.get("code") == expected_code, (
        f"【问题】错误响应结构不符: got code={body.get('code')!r}, 期望 {expected_code!r}\n"
        "【原因】响应体不是统一三要素结构或错误码映射错误\n"
        "【修复】检查 core/observability 异常处理器与 responses.error_response"
    )
    for key in ("problem", "cause", "fix"):
        assert isinstance(body.get(key), str) and body[key], (
            f"【问题】错误响应缺少三要素字段 '{key}': {body}\n"
            "【原因】错误构造时 problem/cause/fix 存在空缺\n"
            "【修复】检查异常构造处三要素填写是否完整"
        )


def test_create_and_read_back_full_chain(client: TestClient) -> None:
    """I1 创建→详情全链路：201 返回系统生成 id，字段完整，回读一致。

    前置: 空库；动作: POST 后 GET 详情；预期: id 带 char- 前缀、字段一致。
    """
    created = client.post(
        "/api/entities",
        json={
            "type": "character",
            "name": "周兰",
            "aliases": ["兰儿"],
            "description": "女主角",
            "audience_known": True,
            "properties": {"age": 19, "gender": "女"},
        },
    ).json()
    assert created["id"].startswith("char-"), (
        f"【问题】生成的 id 未带类型前缀: {created['id']}\n"
        "【原因】id 生成规则未按类型装配前缀\n"
        "【修复】检查 schemas.generate_entity_id 前缀映射"
    )
    assert created["name"] == "周兰"
    assert created["aliases"] == ["兰儿"]
    assert created["audience_known"] is True
    assert created["properties"] == {"age": 19, "gender": "女"}
    assert created["created_at"] and created["updated_at"], "时间戳应完整序列化"

    read_back = client.get(f"/api/entities/{created['id']}").json()
    assert read_back == created, (
        f"【问题】创建后回读不一致:\n created={created}\n read_back={read_back}\n"
        "【原因】落库序列化或响应装配存在字段偏差\n"
        "【修复】对比 repository 写入与 EntityRead 反序列化的字段列表"
    )


def test_search_matches_name_alias_and_type(client: TestClient) -> None:
    """I2 @ 检索：名称命中、别名命中、type 过滤三项全部生效。

    前置: 三个实体（周兰含别名兰儿/周琴/青云山 location）；动作: 三组 GET 检索；
        预期: q=周 命中前两者；q=兰儿 经别名命中周兰；type=location 仅命中青云山。
    """
    zhou_lan = _create_entity(client, "周兰", aliases=["兰儿"])
    _create_entity(client, "周琴")
    qing_yun = _create_entity(client, "青云山", type="location")

    by_name = {row["id"] for row in client.get("/api/entities", params={"q": "周"}).json()}
    assert by_name >= {zhou_lan}, f"名称检索应命中周兰，实际 {by_name}"

    by_alias = client.get("/api/entities", params={"q": "兰儿"}).json()
    assert [row["id"] for row in by_alias] == [zhou_lan], (
        f"【问题】别名检索未命中或误报: {by_alias}\n"
        "【原因】repository.search 的别名展开匹配逻辑缺陷\n"
        "【修复】检查 search 中 json_each 展开的 ilike 匹配"
    )

    typed = client.get("/api/entities", params={"q": "", "type": "location"}).json()
    assert [row["id"] for row in typed] == [qing_yun]
    assert all(row["type"] == "location" for row in typed)


def test_create_rejects_invalid_property_type_unified_error(client: TestClient) -> None:
    """I3 properties 类型校验（HTTP 层）：非法类型 422 且响应为三要素结构。

    前置: 空库；动作: POST gender=数字；预期: 422 + code=VALIDATION_ERROR +
        detail.field=gender + 三要素齐全，且不产生残留数据。
    """
    resp = client.post(
        "/api/entities",
        json={"type": "character", "name": "校验失败者", "properties": {"gender": 19}},
    )
    assert resp.status_code == 422, f"期望 422 实得 {resp.status_code}: {resp.text}"
    body = resp.json()
    _assert_error_shape(body, "VALIDATION_ERROR")
    assert body["detail"]["field"] == "gender"

    leftovers = client.get("/api/entities", params={"q": ""}).json()
    assert leftovers == [], "校验失败的创建不应在库中留下任何数据"


def test_patch_updates_fields_and_merges_properties(client: TestClient) -> None:
    """I4 PATCH 局部更新全链路：name 更新 id 不变，properties 合并语义。

    前置: 已有实体 properties={age:19, gender:女}；动作: PATCH(name, age=20)；
        预期: 200，id 不变，age 更新且 gender 保留。
    """
    entity_id = _create_entity(client, "周兰", properties={"age": 19, "gender": "女"})
    resp = client.patch(
        f"/api/entities/{entity_id}",
        json={"name": "周兰（成年）", "properties": {"age": 20}},
    )
    assert resp.status_code == 200, f"PATCH 应成功: {resp.status_code} {resp.text}"
    updated = resp.json()
    assert updated["id"] == entity_id, "PATCH 不允许改变实体 id"
    assert updated["name"] == "周兰（成年）"
    assert updated["properties"] == {"age": 20, "gender": "女"}, (
        f"【问题】properties 合并语义失效: {updated['properties']}\n"
        "【原因】update 未保留旧字段或整体替换了 properties\n"
        "【修复】检查 service.update 的浅合并逻辑"
    )


def test_patch_rejects_id_field_with_unified_error(client: TestClient) -> None:
    """I5 id 不可变（HTTP 层）：PATCH 载荷携带 id 被 422 拒绝且三要素结构。

    前置: 已有一个实体；动作: PATCH body={\"id\": ...}；预期: 422 统一结构
        （RequestValidationError 经全局处理器转换），实体未被改动。
    """
    entity_id = _create_entity(client, "周兰")
    before = client.get(f"/api/entities/{entity_id}").json()

    resp = client.patch(f"/api/entities/{entity_id}", json={"id": "char-hacked"})
    assert resp.status_code == 422, f"携带 id 的 PATCH 必须 422: {resp.text}"
    _assert_error_shape(resp.json(), "VALIDATION_ERROR")

    after = client.get(f"/api/entities/{entity_id}").json()
    assert after["id"] == entity_id == before["id"], "被拒绝的更新不得改动任何数据"


def test_get_and_delete_missing_entity_unified_404(client: TestClient) -> None:
    """I6 不存在实体：GET 与 DELETE 均返回 404 统一三要素结构。

    前置: 空库；动作: GET/DELETE 不存在的 id；预期: 404 + NOT_FOUND + 三要素。
    """
    for resp in (
        client.get("/api/entities/char-missing"),
        client.delete("/api/entities/char-missing"),
    ):
        assert resp.status_code == 404, f"期望 404 实得 {resp.status_code}: {resp.text}"
        _assert_error_shape(resp.json(), "NOT_FOUND")


def test_delete_without_reference_succeeds_then_gone(client: TestClient) -> None:
    """I7 删除成功链路：无引用实体 DELETE 204 后 GET 转 404。

    前置: 一个无引用实体；动作: DELETE → GET；预期: 204，随后 404。
    """
    entity_id = _create_entity(client, "青铜镜")
    resp = client.delete(f"/api/entities/{entity_id}")
    assert resp.status_code == 204 and resp.content == b"", (
        f"【问题】删除响应应为无内容的 204: {resp.status_code} {resp.content!r}\n"
        "【原因】路由状态码或响应体声明不符契约\n"
        "【修复】检查 router.delete_entity 的 status_code 配置"
    )
    assert client.get(f"/api/entities/{entity_id}").status_code == 404


def test_delete_blocked_by_application_layer_reference(client: TestClient) -> None:
    """I8 应用层引用阻断（真实关系行）：DELETE 返回 409 REFERENTIAL_INTEGRITY。

    前置: 两实体 + 旁路直插一条关系行；动作: 删除 source 实体；
        预期: 409 + detail.reference_count=1，实体仍在库中可读。
    """
    src_id = _create_entity(client, "周兰")
    tgt_id = _create_entity(client, "李乾")

    error = _bypass_execute(_REL_INSERT_SQL, {"source": src_id, "target": tgt_id})
    assert error is None, (
        f"【问题】前置关系行插入失败: {error}\n"
        "【原因】relationships 表结构与插入语句不符\n"
        "【修复】对照 relations/models.py 核对必填列"
    )

    resp = client.delete(f"/api/entities/{src_id}")
    assert resp.status_code == 409, (
        f"【问题】被引用实体删除未被阻断: HTTP {resp.status_code} {resp.text}\n"
        "【原因】应用层 ReferentialError 前置校验缺失或计数错误\n"
        "【修复】检查 service.delete 与 relations.service.count_by_entity"
    )
    body = resp.json()
    _assert_error_shape(body, "REFERENTIAL_INTEGRITY")
    assert body["detail"]["reference_count"] == 1
    assert client.get(f"/api/entities/{src_id}").status_code == 200, "被阻断后实体必须仍在"


def test_db_restrict_backstop_blocks_bypass_delete(client: TestClient) -> None:
    """I9 DB 层 RESTRICT 兜底：绕过应用层直删被引用实体触发 IntegrityError。

    前置: 两实体 + 旁路插入的关系行；动作: 旁路连接执行裸 DELETE FROM entities
        （外键已按生产配置开启）；预期: IntegrityError，且 foreign_key_check 为空
        （拒绝发生在语句层，数据库不产生悬空引用）。
    """
    src_id = _create_entity(client, "周兰")
    tgt_id = _create_entity(client, "李乾")
    assert _bypass_execute(_REL_INSERT_SQL, {"source": src_id, "target": tgt_id}) is None

    integrity_error = _bypass_execute(text("DELETE FROM entities WHERE id = :eid"), {"eid": src_id})
    assert integrity_error is not None, (
        "【问题】DB 层 RESTRICT 未拦截旁路删除（删除意外成功）\n"
        "【原因】外键未开启或迁移 DDL 缺失 ondelete=RESTRICT\n"
        "【修复】检查 migrations FK DDL 与 db.py 连接钩子的 foreign_keys 设置"
    )

    fk_rows = _bypass_fetchall("PRAGMA foreign_key_check")
    assert fk_rows == [], (
        f"【问题】外键巡检发现悬空引用: {fk_rows}\n"
        "【原因】存在幽灵节点数据（违反单一事实源一致性）\n"
        "【修复】清理引用完整性并核查删除路径"
    )


def test_sqlite_wal_mode_active_from_app_connections(client: TestClient) -> None:
    """I10 SQLite 约定（PRAGMA）：应用连接激活的 WAL 模式持久于数据库文件。

    前置: 先发一次健康检查确保应用至少建立过一条真实连接；动作: 旁路查询
        journal_mode；预期: wal（该属性持久在数据库文件上，可独立于发起连接验证——
        这是唯一由应用行为写入文件的 PRAGMA；foreign_keys 属连接级配置，
        其生效性由 I9 的 IntegrityError 行为间接证明）。
    """
    health = client.get("/api/health")
    assert health.status_code == 200, "健康检查应先确认应用可达"

    rows = _bypass_fetchall("PRAGMA journal_mode")
    assert rows and rows[0][0] == "wal", (
        f"【问题】WAL 模式未生效: journal_mode={rows}\n"
        "【原因】db.py 连接钩子未在每个新连接执行 PRAGMA journal_mode=WAL\n"
        "【修复】检查 get_engine 注册的 connect 钩子"
    )
