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
    AgentRunEventRead,
    AgentRunRead,
    ApproveResponse,
    ChatRequest,
    ConfirmRequest,
    ConfirmResponse,
    ConversationMemoryDeletionPreview,
    MemoryDeletionPreview,
    MemoryDocBrief,
    MemoryDocRead,
    MemoryDocSectionRead,
    MessageRead,
    PendingWriteActionRequest,
    PendingWriteRead,
    ProjectMemoryCreate,
    ProjectMemoryDecision,
    ProjectMemoryRead,
    ProjectMemoryUpdate,
    ProposeRequest,
    ProposeResponse,
    RejectResponse,
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


@router.get(
    "/sessions/{conversation_id}/memory-deletion-preview",
    response_model=ConversationMemoryDeletionPreview,
)
async def session_memory_deletion_preview(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> ConversationMemoryDeletionPreview:
    await service.ensure_conversation(session, conversation_id)
    return await service.conversation_memory_deletion_preview(session, conversation_id)


@router.post("/chat")
async def chat(
    schema: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """SSE 流式对话（事件协议见 agent/ARCHITECTURE.md；会话不存在 404）。"""
    run = await service.create_or_get_run(session, schema)
    if run.status == "queued":
        service.start_run(run.id)
    generator = service.stream_run_events(run.id)
    return StreamingResponse(
        (_sse_frame(evt["event"], evt["data"]) async for evt in generator),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/lookup", response_model=AgentRunRead)
async def lookup_run(
    conversation_id: str = Query(min_length=1),
    request_id: str = Query(min_length=1),
    session: AsyncSession = Depends(get_session),
) -> AgentRunRead:
    return await service.get_run_by_request(session, conversation_id, request_id)


@router.get("/sessions/{conversation_id}/runs/latest", response_model=AgentRunRead | None)
async def latest_run(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
) -> AgentRunRead | None:
    return await service.get_latest_run(session, conversation_id)


@router.get("/runs/{run_id}", response_model=AgentRunRead)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)) -> AgentRunRead:
    return await service.get_run(session, run_id)


@router.get("/runs/{run_id}/events", response_model=list[AgentRunEventRead])
async def get_run_events(
    run_id: str,
    after_seq: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[AgentRunEventRead]:
    return await service.get_run_events(session, run_id, after_seq)


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str, after_seq: int = Query(default=0, ge=0)) -> StreamingResponse:
    generator = service.stream_run_events(run_id, after_seq=after_seq)
    return StreamingResponse(
        (_sse_frame(evt["event"], evt["data"]) async for evt in generator),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/cancel", response_model=AgentRunRead)
async def cancel_run(run_id: str, session: AsyncSession = Depends(get_session)) -> AgentRunRead:
    return await service.cancel_run(session, run_id)


@router.post("/propose", response_model=ProposeResponse)
async def propose(
    schema: ProposeRequest,
    session: AsyncSession = Depends(get_session),
) -> ProposeResponse:
    """生成实体/关系写入草案（legacy：F14 起写入工具链为主路径；不落库）。"""
    return await service.propose_drafts(session, schema)


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm(
    schema: ConfirmRequest,
    session: AsyncSession = Depends(get_session),
) -> ConfirmResponse:
    """确认草案并落库（legacy 两段式第二段；服务端复核全部 payload）。"""
    return await service.confirm_write(session, schema)


@router.get("/pending-writes", response_model=list[PendingWriteRead])
async def list_pending_writes(
    conversation_id: str = Query(min_length=1),
    session: AsyncSession = Depends(get_session),
) -> list[PendingWriteRead]:
    """列出会话全部待写入登记（确认卡回读；含全部状态，时间升序）。"""
    return await service.list_pending_writes(session, conversation_id)


@router.post("/pending-writes/approve", response_model=ApproveResponse)
async def approve_pending_writes(
    schema: PendingWriteActionRequest,
    session: AsyncSession = Depends(get_session),
) -> ApproveResponse:
    """批准待写入登记（服务端逐项二次校验落库；成功置 approved）。"""
    return await service.approve_pending_writes(session, schema)


@router.post("/pending-writes/reject", response_model=RejectResponse)
async def reject_pending_writes(
    schema: PendingWriteActionRequest,
    session: AsyncSession = Depends(get_session),
) -> RejectResponse:
    """放弃待写入登记（置 rejected；非 pending 项跳过）。"""
    return await service.reject_pending_writes(session, schema)


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


@router.get("/memories", response_model=list[ProjectMemoryRead])
async def list_project_memories(
    project_id: str = Query(default=""),
    context_key: str | None = Query(default=None),
    status: str | None = Query(default=None),
    query: str = Query(default="", max_length=200),
    session: AsyncSession = Depends(get_session),
) -> list[ProjectMemoryRead]:
    return await service.list_memories(
        session, project_id, context_key=context_key, status=status, query=query
    )


@router.post("/memories", response_model=ProjectMemoryRead, status_code=201)
async def create_project_memory(
    schema: ProjectMemoryCreate,
    project_id: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
) -> ProjectMemoryRead:
    schema.project_id = project_id or schema.project_id
    return await service.create_memory(session, schema)


@router.patch("/memories/{memory_id}", response_model=ProjectMemoryRead)
async def update_project_memory(
    memory_id: str,
    schema: ProjectMemoryUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProjectMemoryRead:
    return await service.update_memory(session, memory_id, schema)


@router.post("/memories/{memory_id}/accept", response_model=ProjectMemoryRead)
async def accept_project_memory(
    memory_id: str,
    schema: ProjectMemoryDecision,
    session: AsyncSession = Depends(get_session),
) -> ProjectMemoryRead:
    return await service.accept_memory(session, memory_id, schema)


@router.post("/memories/{memory_id}/resolve", response_model=ProjectMemoryRead)
async def resolve_project_memory(
    memory_id: str,
    schema: ProjectMemoryDecision,
    session: AsyncSession = Depends(get_session),
) -> ProjectMemoryRead:
    return await service.resolve_memory(session, memory_id, schema)


@router.get("/memories/{memory_id}/deletion-preview", response_model=MemoryDeletionPreview)
async def project_memory_deletion_preview(
    memory_id: str,
    session: AsyncSession = Depends(get_session),
) -> MemoryDeletionPreview:
    return await service.memory_deletion_preview(session, memory_id)


@router.delete("/memories/{memory_id}", status_code=204)
async def forget_project_memory(
    memory_id: str,
    expected_version: int = Query(ge=1),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await service.forget_memory(
        session, memory_id, ProjectMemoryDecision(expected_version=expected_version)
    )
    return Response(status_code=204)
