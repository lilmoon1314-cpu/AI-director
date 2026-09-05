"""entities 模块 Pydantic 模型与 properties 类型校验。

校验策略（entities/CONSTRAINTS.md「读宽容写严格」）:
    - 写入（create/update）时对当前 schema 中已声明的字段做严格类型校验；
    - 未声明字段（旧版本 schema 写入的历史数据）保留不丢弃——保证 schema 演进后旧数据可读写。
类型表来源: docs/data_struct_define.md §1 各类型 properties 定义。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# 实体类型枚举（7 类，见 docs/data_struct_define.md §1）
EntityType = Literal["character", "faction", "location", "item", "skill", "event", "concept"]

# id 前缀映射（生成可读 id，如 char-a1b2c3d4；前缀冲突于本表内不存在的类型由 Literal 保证）
_ID_PREFIXES: dict[str, str] = {
    "character": "char",
    "faction": "fct",
    "location": "loc",
    "item": "item",
    "skill": "skill",
    "event": "event",
    "concept": "cpt",
}

# 各类型 properties 字段的允许类型（来自 docs/data_struct_define.md §1）
_PROPERTY_FIELD_TYPES: dict[str, dict[str, str]] = {
    "character": {
        "age": "number|string",
        "gender": "string",
        "occupation": "string",
        "social_class": "string",
        "resources": "list",
        "obligations": "list",
        "abilities": "list",
        "weaknesses": "list",
        "habits": "object",
        "outer_desire": "string",
        "inner_need": "string",
        "wrong_belief": "string",
        "main_opposition": "string",
        "final_choice": "string",
        "observable_arc": "string",
        "backstory": "list",
        "core_symbol": "object",
        "conscious_creed": "string",
        "subconscious_desire": "string",
        "shadow": "string",
        "desire": "string",
        "aversion": "string",
        "delusion": "string",
        "cognitive_lens": "string",
        "family_theme": "string",
        "worldview_initial": "string",
        "life_view_initial": "string",
        "value_view_initial": "string",
        "affiliation": "string",
        "origin": "string",
        "cultivation": "object",
        "pressure_behaviors": "list",
        "language_fingerprint": "list",
        "writing_guide": "object",
        "forbidden_distortions": "list",
        "visual_features": "list",
    },
    "faction": {
        "description": "string",
        "headquarters": "string",
        "members": "list",
        "resources": "list",
        "doctrine": "string",
        "public_relations": "list",
    },
    "location": {
        "location_type": "string",
        "description": "string",
        "parent_location": "string",
        "climate": "string",
        "season": "string",
        "weather": "string",
        "time_of_day": "string",
        "crowd_state": "string",
        "special_restrictions": "list",
        "visual_elements": "object",
        "resources": "list",
    },
    "item": {
        "appearance": "string",
        "authenticity": "string",
        "damage": "string",
        "location": "string",
        "holder": "string",
        "seen_by": "list",
    },
    "skill": {
        "description": "string",
        "owner": "string",
        "cost": "string",
        "level": "string",
        "category": "string",
    },
    "event": {
        "description": "string",
        "participants": "list",
        "location": "string",
        "time": "string",
        "is_public": "boolean",
        "known_by": "list",
    },
    "concept": {
        "concept_type": "string",
        "description": "string",
        "origin": "string",
        "image_ref": "string",
    },
}


def _matches_type(value: Any, spec: str) -> bool:
    """判断值是否满足类型描述（如 "number|string"）。

    作用: properties 字段类型的严格校验器。
    参数: value — 待校验值；spec — 竖线分隔的类型描述。
    返回值: bool。异常: 无。依赖: 无。
    """
    for name in spec.split("|"):
        if name == "string" and isinstance(value, str):
            return True
        # bool 是 int 的子类，须显式排除，防止布尔值混入数值字段
        if name == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if name == "boolean" and isinstance(value, bool):
            return True
        if name == "list" and isinstance(value, list):
            return True
        if name == "object" and isinstance(value, dict):
            return True
    return False


def _type_name(value: Any) -> str:
    """值的可读类型名（用于错误消息）。

    作用: 生成与类型描述同词表的类型名（string/number/boolean/list/object/其他）。
    参数: value — 任意值。返回值: str。异常: 无。依赖: 无。
    """
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def generate_entity_id(entity_type: str) -> str:
    """生成实体 id（类型前缀 + 随机串，创建后不可变）。

    作用: 满足「id 系统生成」约束，同时前缀提升可读性。
    参数: entity_type — 实体类型（ENTITY_TYPES 之一）。
    返回值: str — 形如 "char-a1b2c3d4e5f6"。
    异常: KeyError — 未知类型（由上层 Literal 校验先行拦截，正常不可达）。
    依赖: uuid。
    """
    import uuid

    return f"{_ID_PREFIXES[entity_type]}-{uuid.uuid4().hex[:12]}"


def validate_properties(entity_type: str, properties: dict[str, Any]) -> None:
    """校验 properties 中已声明字段的类型（写严格；未声明字段保留）。

    作用:
        按 docs/data_struct_define.md §1 的类型表逐字段校验；类型不符抛
        ValidationError（三要素完整）。未声明字段不校验不丢弃（读宽容，
        保证 schema 演进后旧数据可整体写回）。
    参数:
        entity_type — 实体类型；properties — 待校验的属性字典。
    返回值: 无（通过则静默返回）。
    异常:
        app.core.exceptions.ValidationError — 存在类型不符的已声明字段。
    依赖: app.core.exceptions。
    """
    from app.core.exceptions import ValidationError

    field_types = _PROPERTY_FIELD_TYPES.get(entity_type)
    if field_types is None:
        return  # 未登记类型表的类型：不校验（枚举外类型已被 Pydantic Literal 拦截）
    for field, spec in field_types.items():
        if field in properties and not _matches_type(properties[field], spec):
            raise ValidationError(
                problem=f"实体属性 {field} 类型校验失败",
                cause=(
                    f"type='{entity_type}' 的 properties.{field} "
                    f"期望 {spec}，实际收到 {_type_name(properties[field])}"
                ),
                fix=f"修改 properties.{field} 为 {spec} 类型后重试",
                detail={"entity_type": entity_type, "field": field, "expected": spec},
            )


class EntityBase(BaseModel):
    """实体公共字段（请求/响应模型的共同部分）。"""

    type: EntityType
    name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    audience_known: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)


class EntityCreate(EntityBase):
    """创建实体请求体。

    作用: POST /api/entities 的载荷模型；extra=forbid 拒绝未知字段（含 id——
    id 由系统生成，禁止客户端指定）。
    参数: 无（字段见 EntityBase）。返回值: 无（模型类）。异常: 无。依赖: pydantic。
    """

    model_config = ConfigDict(extra="forbid")


class EntityUpdate(BaseModel):
    """局部更新实体请求体（PATCH）。

    作用:
        所有字段可选，仅更新显式提供的字段；extra=forbid 保证 id 不可变
        （传入 id 字段直接被 422 拒绝，见 entities/CONSTRAINTS.md）。
    参数: 无（字段定义见下）。返回值: 无（模型类）。异常: 无。依赖: pydantic。
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    aliases: list[str] | None = None
    description: str | None = None
    audience_known: bool | None = None
    properties: dict[str, Any] | None = None


class EntityRead(EntityBase):
    """实体完整响应（详情/创建/更新返回）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class EntityBrief(BaseModel):
    """实体摘要响应（@ 检索列表，供前端选择器）。

    audience_known 供选择器提示「实体对当前视角是否可见」（F07，判定基准
    为前端已加载图数据的节点集合，audience 视角下未收录实体不可见）。
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    type: EntityType
    name: str
    aliases: list[str]
    audience_known: bool
