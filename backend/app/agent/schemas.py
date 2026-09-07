"""agent 模块 Pydantic 模型：会话/消息/记忆文档/草案的请求与响应 DTO。

设计要点:
    - 草案 payload 保持 dict（宽松承载 LLM 输出）；严格校验发生在 confirm
      时构造 entities/relations service 的输入 DTO（服务端复核，不信任前端）。
    - 记忆文档对外暴露段级结构（段级 patch 的 CAS 主体是段 version）。
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# 视角枚举（与 /api/graph 契约一致；不 import perspectives.schemas——模块解耦见
# backend/CONSTRAINTS.md）
Perspective = Literal["author", "character", "audience"]


def _short_uuid() -> str:
    """随机 12 位十六进制串（id 后缀）。"""
    return uuid.uuid4().hex[:12]


def generate_conversation_id() -> str:
    """生成会话 id（创建后不可变）。

    作用: 满足「id 系统生成」约束。参数: 无。返回值: str 形如 conv-a1b2c3d4e5f6。
    异常: 无。依赖: uuid。
    """
    return f"conv-{_short_uuid()}"


def generate_message_id() -> str:
    """生成消息 id（创建后不可变）。

    作用: 同上。参数: 无。返回值: str 形如 msg-...。异常: 无。依赖: uuid。
    """
    return f"msg-{_short_uuid()}"


def generate_memory_doc_id() -> str:
    """生成记忆文档 id（创建后不可变）。

    作用: 同上。参数: 无。返回值: str 形如 mdoc-...。异常: 无。依赖: uuid。
    """
    return f"mdoc-{_short_uuid()}"


def generate_memory_section_id() -> str:
    """生成文档段 id（创建后不可变）。

    作用: 同上。参数: 无。返回值: str 形如 msec-...。异常: 无。依赖: uuid。
    """
    return f"msec-{_short_uuid()}"


def generate_draft_id() -> str:
    """生成草案 id（仅用于前后端相关性关联，不落库）。

    作用: propose 响应与 confirm 请求的关联键。参数: 无。
    返回值: str 形如 draft-...。异常: 无。依赖: uuid。
    """
    return f"draft-{_short_uuid()}"


# ---- 会话与消息 ----


class ChatRequest(BaseModel):
    """对话请求（SSE 流式响应）。

    参数: conversation_id — 会话 id；message — 用户输入；
        perspective — 上下文视角（图谱数据经该视角过滤后注入）；
        character_id — character 视角的角色 id。
    """

    conversation_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=8000)
    perspective: Perspective = "author"
    character_id: str = ""


class SessionCreate(BaseModel):
    """创建会话请求。

    参数: project_id — 归属项目（空=默认项目）；title — 会话标题（空=首条消息截断）。
    """

    project_id: str = ""
    title: str = Field(default="", max_length=200)


class SessionRead(BaseModel):
    """会话响应（滚动摘要为内部字段，不外露）。"""

    id: str
    project_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    """消息响应。"""

    id: str
    conversation_id: str
    role: Literal["user", "assistant", "summary", "tool"]
    content: str
    created_at: datetime


# ---- 记忆文档 ----


class MemoryDocBrief(BaseModel):
    """记忆文档卡片摘要（列表视图：名称+更新时间+首行摘要，DESIGN §5.4）。"""

    id: str
    kind: str
    title: str
    version: int
    updated_at: datetime
    preview: str = Field(description="首段内容预览（截断）")


class MemoryDocSectionRead(BaseModel):
    """文档段响应（version 为段级 CAS 令牌）。"""

    id: str
    seq: int
    title: str
    content: str
    updated_by: Literal["user", "agent"]
    version: int
    updated_at: datetime


class MemoryDocRead(BaseModel):
    """记忆文档响应（含全部段，按 seq 排序）。"""

    id: str
    kind: str
    title: str
    version: int
    created_at: datetime
    updated_at: datetime
    sections: list[MemoryDocSectionRead] = Field(default_factory=list)


class SectionUpdate(BaseModel):
    """段内容更新请求（用户编辑与 agent patch 确认共用；乐观锁）。

    参数: content — 新内容；expected_version — 调用方读取时的段版本，
        与当前不一致即 409 冲突（用户手改优先，绝不静默覆盖）。
    """

    content: str = Field(min_length=0)
    expected_version: int = Field(ge=1)


# ---- 草案（propose / confirm 两段式）----


class DraftItem(BaseModel):
    """单条写入草案（propose 产出；confirm 原样回传 payload）。"""

    draft_id: str
    kind: Literal["entity", "relation"]
    payload: dict[str, Any] = Field(description="entities/relations service 输入形状的宽松载荷")
    summary: str = Field(description="给作者看的一句话摘要")


class ProposeRequest(BaseModel):
    """生成草案请求。"""

    session_id: str
    message: str = Field(min_length=1, max_length=8000)
    perspective: Literal["author", "character", "audience"] = "author"
    character_id: str = ""


class ProposeResponse(BaseModel):
    """草案列表响应。"""

    session_id: str
    drafts: list[DraftItem] = Field(default_factory=list)


class ConfirmItem(BaseModel):
    """确认请求的单项（confirmed=False 表示放弃该条）。"""

    draft_id: str
    kind: Literal["entity", "relation"]
    payload: dict[str, Any]
    confirmed: bool


class ConfirmRequest(BaseModel):
    """确认写入请求（无状态回传草案，服务端重新校验全部 payload）。"""

    session_id: str = ""
    items: list[ConfirmItem] = Field(min_length=1)


class ConfirmResultItem(BaseModel):
    """确认结果：成功项（写入后的实体/关系 id 与名称）。"""

    draft_id: str
    kind: Literal["entity", "relation"]
    target_id: str
    name: str


class ConfirmFailedItem(BaseModel):
    """确认结果：失败项（含三要素 reason）。"""

    draft_id: str
    reason: str


class ConfirmResponse(BaseModel):
    """确认写入响应。"""

    created: list[ConfirmResultItem] = Field(default_factory=list)
    failed: list[ConfirmFailedItem] = Field(default_factory=list)
