"""assets 模块 Pydantic 请求/响应模型与 id 生成。

资产分类（category）为自由字符串标签（DECISIONS 2026-09-05：增删分类零代码变更）；
通用资产自定义属性以 attributes 自由 JSON 承载，HTML 模板按键值小节渲染。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

# 资产种类：general=通用资产（用户创建）；entity=实体资产页（系统按主库实体生成）
AssetKind = Literal["general", "entity"]
# 图片归属面：general 图片挂通用资产；entity 图片挂主库实体 id
AssetScope = Literal["general", "entity"]

# 实体类型展示顺序（与 docs/data_struct_define.md §1 的 7 类一致；
# 独立常量声明——跨模块禁止 import entities.schemas 内部类型）
ENTITY_TYPE_ORDER: tuple[str, ...] = (
    "character",
    "faction",
    "location",
    "item",
    "skill",
    "event",
    "concept",
)

# 实体类型中文名（HTML 页与卡片展示用）
ENTITY_TYPE_LABELS: dict[str, str] = {
    "character": "人物",
    "faction": "门派",
    "location": "地点",
    "item": "物件",
    "skill": "功法",
    "event": "事件",
    "concept": "概念",
}


def generate_asset_id() -> str:
    """生成资产记录 id（系统生成，创建后不可变）。

    作用: 满足「id 系统生成」约束，前缀提升可读性。
    参数: 无。返回值: str — 形如 "asset-a1b2c3d4e5f6"。异常: 无。依赖: uuid。
    """
    import uuid

    return f"asset-{uuid.uuid4().hex[:12]}"


def generate_image_id() -> str:
    """生成图片记录 id（系统生成，创建后不可变）。

    作用: 满足「id 系统生成」约束，前缀提升可读性。
    参数: 无。返回值: str — 形如 "img-a1b2c3d4e5f6"。异常: 无。依赖: uuid。
    """
    import uuid

    return f"img-{uuid.uuid4().hex[:12]}"


class AssetImageRead(BaseModel):
    """图片元数据响应（url 为静态访问地址）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    scope: AssetScope
    owner_id: str
    filename_orig: str
    stored_name: str
    mime: str
    size: int
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        """图片访问地址（/api 前缀同源路由——HTML 资产页内的图片引用在任何部署
        形态下都与页面同源，开发期经 vite /api 代理，生产可经网关统一转发）。"""
        return f"/api/assets/file/{self.stored_name}"


class GeneralAssetCreate(BaseModel):
    """创建通用资产请求体（extra=forbid 拒绝未知字段）。"""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(default="", max_length=100)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20000)
    attributes: dict[str, Any] = Field(default_factory=dict)


class GeneralAssetUpdate(BaseModel):
    """局部更新通用资产请求体（仅更新显式提供的字段；extra=forbid）。"""

    model_config = ConfigDict(extra="forbid")

    category: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    attributes: dict[str, Any] | None = None


class CoverSet(BaseModel):
    """设置封面请求体（PUT /general/{id}/cover）。"""

    model_config = ConfigDict(extra="forbid")

    image_id: str


class AssetRead(BaseModel):
    """通用资产完整响应（详情/创建/更新返回，含图片列表）。"""

    id: str
    kind: AssetKind
    category: str
    title: str
    description: str
    attributes: dict[str, Any]
    cover_image_id: str | None
    cover_url: str | None
    images: list[AssetImageRead]
    created_at: datetime
    updated_at: datetime


class AssetCard(BaseModel):
    """通用资产卡片（列表项：缩略图 + 摘要，不含 html 全文与图片明细）。"""

    id: str
    category: str
    title: str
    description: str
    cover_url: str | None
    image_count: int
    updated_at: datetime


class EntityAssetCard(BaseModel):
    """项目资产卡片（主库实体的展示面：缩略图 + 名称/概述）。"""

    id: str
    type: str
    name: str
    description: str
    cover_url: str | None
    image_count: int
