"""relations 模块 Pydantic 模型与请求校验。

校验策略（relations/CONSTRAINTS.md）:
    - 数值动态属性（trust/intimacy/dependency/resentment，0-1 标度）在本层
      以 Field(ge/le) 约束拦截（docs/data_struct_define.md §2）；
    - 端点存在性与 known_by 成员校验需查询数据库，在 service 层完成；
    - id 系统生成、source/target/type 创建后不可变：Create 模型不含 id，
      Update 模型 extra=forbid 直接拒绝携带 id/source/target/type 的载荷。
字段蓝图: docs/data_struct_define.md §2。
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def generate_relation_id() -> str:
    """生成关系 id（rel- 前缀 + 随机串，创建后不可变）。

    作用: 满足「id 系统生成」约束，前缀提升可读性。
    参数: 无。返回值: str — 形如 "rel-a1b2c3d4e5f6"。异常: 无。依赖: uuid。
    """
    import uuid

    return f"rel-{uuid.uuid4().hex[:12]}"


class RelationCreate(BaseModel):
    """创建关系请求体（POST /api/relations）。

    作用:
        创建载荷模型；extra=forbid 拒绝未知字段（含 id——id 由系统生成，
        禁止客户端指定）。端点/known_by 的数据库级校验在 service 层。
    参数: 无（字段定义见下，蓝图见 docs/data_struct_define.md §2）。
    返回值: 无（模型类）。异常: 无。依赖: pydantic。
    """

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: str = Field(min_length=1, max_length=100)
    trust: float | None = Field(default=None, ge=0.0, le=1.0)
    intimacy: float | None = Field(default=None, ge=0.0, le=1.0)
    dependency: float | None = Field(default=None, ge=0.0, le=1.0)
    resentment: float | None = Field(default=None, ge=0.0, le=1.0)
    public_identity: str | None = None
    private_identity: str | None = None
    promise: str | None = None
    wants_from: str | None = None
    believes_other_wants: str | None = None
    leverage: str | None = None
    boundary: str | None = None
    status: str | None = None
    known_by: list[str] = Field(default_factory=list)
    audience_known: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationUpdate(BaseModel):
    """局部更新关系请求体（PATCH）。

    作用:
        动态属性全部可选，仅更新显式提供的字段；extra=forbid 保证
        id/source/target/type 不可变（传入即被 422 拒绝，见 relations/CONSTRAINTS.md）。
    参数: 无（字段定义见下）。返回值: 无（模型类）。异常: 无。依赖: pydantic。
    """

    model_config = ConfigDict(extra="forbid")

    trust: float | None = Field(default=None, ge=0.0, le=1.0)
    intimacy: float | None = Field(default=None, ge=0.0, le=1.0)
    dependency: float | None = Field(default=None, ge=0.0, le=1.0)
    resentment: float | None = Field(default=None, ge=0.0, le=1.0)
    public_identity: str | None = None
    private_identity: str | None = None
    promise: str | None = None
    wants_from: str | None = None
    believes_other_wants: str | None = None
    leverage: str | None = None
    boundary: str | None = None
    status: str | None = None
    known_by: list[str] | None = None
    audience_known: bool | None = None
    properties: dict[str, Any] | None = None


class RelationRead(BaseModel):
    """关系完整响应（详情/创建/更新/列表返回）。

    作用: 对外只读 DTO；字段与 ORM 模型一致（from_attributes 装配）。
    参数: 无（字段定义见下）。返回值: 无（模型类）。异常: 无。依赖: pydantic。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    target: str
    type: str
    trust: float | None
    intimacy: float | None
    dependency: float | None
    resentment: float | None
    public_identity: str | None
    private_identity: str | None
    promise: str | None
    wants_from: str | None
    believes_other_wants: str | None
    leverage: str | None
    boundary: str | None
    status: str | None
    known_by: list[str]
    audience_known: bool
    properties: dict[str, Any]
    created_at: datetime
    updated_at: datetime
