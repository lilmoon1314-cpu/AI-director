"""agent 模块 HTTP 路由：会话、SSE 对话、草案两段式与记忆文档端点。

路径约定（F11 渐进迁移）：领域端点挂 /api/agent 前缀，项目维度经
project_id 查询参数（缺省=默认项目），与既有模块一致（DECISIONS 2026-09-06）。
本层仅做参数解析与响应包装，业务逻辑在 service，事务不在此层感知。
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import service
from app.agent.schemas import (
    ChatRequest,
    ConfirmRequest,
    ConfirmResponse,
    MemoryDocBrief,
    MemoryDocRead,
    MemoryDocSectionRead,
    MessageRead,
    ProposeRequest,
    ProposeResponse,
    SectionUpdate,
    SessionCreate,
    SessionRead,
)
from app.core.db import get_session

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _sse_frame(event: str, data: dict[str, Any]) -> str:
    """格式化单个 SSE 帧（事件名 + JSON 数据）。

    参数: event — 事件名；data — 事件载荷。
    返回值: str — SSE 帧文本。异常: 无。依赖: json。
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/sessions", response_model=SessionRead, status_code=201)
async def create_session(
    schema: SessionCreate,
    project_id: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
) -> SessionRead:
    """创建会话（201；项目维度归属校验经 projects.service）。"""
    schema.project_id = project_id or schema.project_id
    return await service.create_conversation(session, schema)


@router.get("/sessions", response_model=list[SessionRead])
async def list_sessions(
    project_id: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
) -> list[SessionRead]:
    """列出项目会话（最近活跃在前；缺省归属默认项目）。"""
    return await service.list_conversations(session, project_id)


@router.get("/sessions/{conversation_id}/messages", response_model=list[MessageRead])
async def list_session_messages(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[MessageRead]:
    """读取会话全部消息（时间正序；会话不存在 404）。"""
    return await service.get_messages(session, conversation_id)


@router.delete("/sessions/{conversation_id}", status_code=204)
async def delete_session(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """删除会话（消息经级联清理；204；会话不存在 404）。"""
    await service.delete_conversation(session, conversation_id)
    return Response(status_code=204)


@router.post("/chat")
async def chat(
    schema: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """SSE 流式对话（事件协议见 agent/ARCHITECTURE.md；会话不存在 404）。"""
    await service.ensure_conversation(session, schema.conversation_id)
    generator = service.stream_chat(
        schema.conversation_id,
        schema.message,
        perspective=schema.perspective,
        character_id=schema.character_id,
    )
    return StreamingResponse(
        (_sse_frame(evt["event"], evt["data"]) async for evt in generator),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/propose", response_model=ProposeResponse)
async def propose(
    schema: ProposeRequest,
    session: AsyncSession = Depends(get_session),
) -> ProposeResponse:
    """生成实体/关系写入草案（LLM JSON mode；不落库）。"""
    return await service.propose_drafts(session, schema)


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm(
    schema: ConfirmRequest,
    session: AsyncSession = Depends(get_session),
) -> ConfirmResponse:
    """确认草案并落库（两段式第二段；服务端复核全部 payload）。"""
    return await service.confirm_write(session, schema)


@router.post("/memory-docs", response_model=MemoryDocRead, status_code=201)
async def create_memory_doc(
    kind: str = Query(default="positioning"),
    project_id: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
) -> MemoryDocRead:
    """按模板创建记忆文档（kind ∈ positioning/style，缺省 positioning；201）。"""
    return await service.create_doc(session, project_id, kind)


@router.get("/memory-docs", response_model=list[MemoryDocBrief])
async def list_memory_docs(
    project_id: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
) -> list[MemoryDocBrief]:
    """列出项目记忆文档卡片（名称+更新时间+首段预览）。"""
    return await service.list_docs(session, project_id)


@router.get("/memory-docs/{doc_id}", response_model=MemoryDocRead)
async def get_memory_doc(
    doc_id: str,
    session: AsyncSession = Depends(get_session),
) -> MemoryDocRead:
    """读取记忆文档全文（含段列表与段版本）。"""
    return await service.get_doc(session, doc_id)


@router.delete("/memory-docs/{doc_id}", status_code=204)
async def delete_memory_doc(
    doc_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """删除记忆文档（段经级联清理；204）。"""
    await service.delete_doc(session, doc_id)
    return Response(status_code=204)


@router.get("/memory-docs/{doc_id}/page", response_class=HTMLResponse)
async def get_memory_doc_page(
    doc_id: str,
    session: AsyncSession = Depends(get_session),
) -> HTMLResponse:
    """记忆文档自包含 HTML 页（iframe 预览数据源；全转义）。"""
    html_text = await service.render_page(session, doc_id)
    return HTMLResponse(content=html_text)


@router.patch(
    "/memory-docs/{doc_id}/sections/{section_id}",
    response_model=MemoryDocSectionRead,
)
async def update_memory_doc_section(
    doc_id: str,
    section_id: str,
    schema: SectionUpdate,
    updated_by: str = Query(default="user", pattern="^(user|agent)$"),
    session: AsyncSession = Depends(get_session),
) -> MemoryDocSectionRead:
    """段级更新（CAS 乐观锁：expected_version 不符 409；用户手改优先）。"""
    return await service.update_section(session, doc_id, section_id, schema, updated_by=updated_by)
