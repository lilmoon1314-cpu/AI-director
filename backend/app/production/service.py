"""Production document sequencing and semantic validation."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts import service as artifacts_service
from app.core.exceptions import NotFoundError, ValidationError
from app.production import repository
from app.production.models import ProductionDocument, _utcnow
from app.production.schemas import (
    ProductionDocumentCreate,
    ProductionDocumentRead,
    generate_id,
)
from app.workflow import service as workflow_service

DOCUMENT_ORDER = (
    "screenplay",
    "production_breakdown",
    "performance_script",
    "shot_plan",
    "storyboard",
    "timeline",
)
REQUIRED_SEMANTIC_FIELDS = {
    "screenplay": set(),
    "production_breakdown": {"scene_id", "cast", "location", "props", "asset_refs"},
    "performance_script": {"beat_id", "source_block_refs", "duration_target", "action", "emotion"},
    "shot_plan": {"shot_id", "scene_id", "beat_refs", "duration", "framing", "subject_action"},
    "storyboard": {"shot_ref", "panel_prompt", "asset_refs"},
    "timeline": {"track_type", "source_ref", "start", "duration"},
}
SCREENPLAY_BLOCK_TYPES = {"scene_heading", "action", "dialogue", "parenthetical", "transition"}


def _read(row: ProductionDocument) -> ProductionDocumentRead:
    return ProductionDocumentRead(
        id=row.id,
        project_id=row.project_id,
        episode_id=row.episode_id,
        scene_id=row.scene_id,
        artifact_id=row.artifact_id,
        document_type=row.document_type,
        source_document_id=row.source_document_id,
        source_artifact_id=row.source_artifact_id,
        source_block_ids=row.source_block_ids_json,
        created_at=row.created_at,
    )


def _invalid(problem: str, cause: str, fix: str) -> ValidationError:
    return ValidationError(problem=problem, cause=cause, fix=fix)


def _validate_blocks(schema: ProductionDocumentCreate) -> None:
    if schema.document_type == "screenplay":
        invalid = [
            b.block_type for b in schema.blocks if b.block_type not in SCREENPLAY_BLOCK_TYPES
        ]
        if invalid:
            raise _invalid(
                "screenplay block 类型无效",
                f"发现 {invalid}",
                "只使用 scene_heading/action/dialogue/parenthetical/transition",
            )
        return
    required = REQUIRED_SEMANTIC_FIELDS[schema.document_type]
    for position, block in enumerate(schema.blocks):
        missing = sorted(required - block.semantic.keys())
        if missing:
            raise _invalid(
                "production block 缺少语义字段",
                f"{schema.document_type} block {position} 缺少 {missing}",
                "按对应 production document contract 补齐 semantic",
            )


async def create(session: AsyncSession, schema: ProductionDocumentCreate) -> ProductionDocumentRead:
    await workflow_service.ensure_episode_owned(session, schema.project_id, schema.episode_id)
    if schema.scene_id is not None:
        await workflow_service.ensure_scene_owned(
            session, schema.project_id, schema.episode_id, schema.scene_id
        )
    _validate_blocks(schema)
    index = DOCUMENT_ORDER.index(schema.document_type)
    source: ProductionDocument | None = None
    if index == 0:
        if schema.source_document_id is not None or schema.source_block_ids:
            raise _invalid(
                "screenplay 不接受 production upstream",
                "screenplay 是链路首项",
                "移除 source_document_id/source_block_ids",
            )
    else:
        if schema.source_document_id is None or not schema.source_block_ids:
            raise _invalid(
                "缺少 immediate upstream",
                "下游 production document 必须可追溯",
                "提供前一类型 document id 与至少一个 current source block id",
            )
        source = await repository.get(session, schema.source_document_id)
        if source is None:
            raise NotFoundError(
                problem="source document 不存在",
                cause="id 未找到",
                fix="使用已创建的 production document id",
            )
        expected = DOCUMENT_ORDER[index - 1]
        if source.project_id != schema.project_id or source.episode_id != schema.episode_id:
            raise _invalid(
                "source document 跨项目或 episode",
                "ownership 与目标不一致",
                "选择同项目同 episode 的 upstream",
            )
        if source.document_type != expected:
            raise _invalid(
                "source document 类型顺序无效",
                f"{schema.document_type} 必须直接来源于 {expected}",
                "按 master-plan production 顺序创建",
            )
        artifact = await artifacts_service.get(session, source.artifact_id)
        current_ids = {block.id for block in artifact.current_revision.blocks}
        if not set(schema.source_block_ids).issubset(current_ids):
            raise _invalid(
                "source block 不在 upstream current revision",
                "至少一个 block id 无效或属于旧/其他 artifact",
                "从 source artifact current_revision 选择 block",
            )

    artifact = await artifacts_service.create_structured(
        session,
        project_id=schema.project_id,
        artifact_type=schema.document_type,
        title=schema.title,
        blocks=[block.model_dump() for block in schema.blocks],
    )
    if source is not None:
        await artifacts_service.create_block_dependencies(
            session,
            source_artifact_id=source.artifact_id,
            source_block_ids=schema.source_block_ids,
            dependent_artifact_id=artifact.id,
            dependency_type=f"{source.document_type}_to_{schema.document_type}",
        )
    row = ProductionDocument(
        id=generate_id(),
        project_id=schema.project_id,
        episode_id=schema.episode_id,
        scene_id=schema.scene_id,
        artifact_id=artifact.id,
        document_type=schema.document_type,
        source_document_id=None if source is None else source.id,
        source_artifact_id=None if source is None else source.artifact_id,
        source_block_ids_json=schema.source_block_ids,
        created_at=_utcnow(),
    )
    await repository.add(session, row)
    await session.commit()
    return _read(row)


async def get(session: AsyncSession, document_id: str) -> ProductionDocumentRead:
    row = await repository.get(session, document_id)
    if row is None:
        raise NotFoundError(
            problem="production document 不存在",
            cause="id 未找到",
            fix="先创建或列出 production document",
        )
    return _read(row)


async def delete_project_data(session: AsyncSession, project_id: str) -> None:
    await repository.delete_project(session, project_id)


async def create_from_payload(
    session: AsyncSession, project_id: str, payload: dict[str, object]
) -> ProductionDocumentRead:
    """Confirmed-write adapter without exposing Production internal schemas."""
    merged = dict(payload)
    merged["project_id"] = project_id
    return await create(session, ProductionDocumentCreate.model_validate(merged))
