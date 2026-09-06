"""projects 模块 Pydantic 模型与请求校验。

校验策略:
    - 名称去首尾空白后非空（Pydantic min_length 只拦空串，纯空白在此层拦截）；
    - id 系统生成且不可变：Create 模型不含 id、extra=forbid，Update 模型不含
      id / 计数器字段（计数器只经 service.touch 事务内维护，禁止客户端直写）。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 项目名长度上限（边界值用例依据，docs/tests/F11 I2）
PROJECT_NAME_MAX = 64
# 项目描述长度上限
PROJECT_DESCRIPTION_MAX = 500


def generate_project_id() -> str:
    """生成项目 id（project- 前缀 + 随机串，创建后不可变）。

    作用: 满足「id 系统生成」约束，前缀提升可读性。
    参数: 无。
    返回值: str — 形如 "project-a1b2c3d4e5f6"。
    异常: 无。依赖: uuid。
    """
    import uuid

    return f"project-{uuid.uuid4().hex[:12]}"


def _strip_name(name: str) -> str:
    """去首尾空白并拒绝空白名（Create/Update 共用校验器）。

    作用: 名称以去空白后的值持久化；纯空白名称在请求层即被 422 拒绝
        （等价类-无效：空名称/纯空白，docs/tests/F11 U2/I2）。
    参数: name — 原始名称。返回值: str（去空白后）。
    异常: ValueError — 去空白后为空。依赖: 无。
    """
    stripped = name.strip()
    if not stripped:
        raise ValueError("项目名不能为空白")
    return stripped


class ProjectCreate(BaseModel):
    """创建项目请求体（POST /api/projects）。

    作用: 创建载荷模型；extra=forbid 拒绝未知字段（含 id——id 由系统生成）。
    参数: 无（字段见下）。返回值: 无（模型类）。异常: 无。依赖: pydantic。
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=PROJECT_NAME_MAX)
    description: str = Field(default="", max_length=PROJECT_DESCRIPTION_MAX)
    _strip_name = field_validator("name", mode="after")(_strip_name)


class ProjectUpdate(BaseModel):
    """局部更新项目请求体（PATCH /api/projects/{id}）。

    作用: 字段可选、仅更新显式提供项；extra=forbid 保证 id / 计数器不可
        由客户端指定（计数器只经领域写路径事务内维护）。
    参数: 无（字段见下）。返回值: 无（模型类）。异常: 无。依赖: pydantic。
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=PROJECT_NAME_MAX)
    description: str | None = Field(default=None, max_length=PROJECT_DESCRIPTION_MAX)
    _strip_name = field_validator("name", mode="after")(_strip_name)


class ProjectRead(BaseModel):
    """项目完整响应（列表/详情/创建/更新返回）。

    作用: 对外只读 DTO；计数器供项目首屏卡片（N 实体）与删除确认后果清单。
    参数: 无（字段见下）。返回值: 无（模型类）。异常: 无。依赖: pydantic。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    entity_count: int
    relation_count: int
    created_at: datetime
    updated_at: datetime
