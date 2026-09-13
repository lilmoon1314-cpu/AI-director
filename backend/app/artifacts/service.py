"""Artifact Core business boundary: revisions, diffs, dependencies, and stale propagation."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.artifacts import repository
from app.artifacts.models import (
    Artifact,
    ArtifactBlock,
    ArtifactBlockRevision,
    ArtifactDependency,
    ArtifactRevision,
    _utcnow,
)
from app.artifacts.schemas import (
    ArtifactBlockRead,
    ArtifactCreate,
    ArtifactRead,
    ArtifactRevisionRead,
    BlockEdit,
    DependencyCreate,
    DependencyRead,
    RevisionDiffEntry,
    RevisionDiffRead,
    generate_id,
)
from app.core.exceptions import NotFoundError, ValidationError
from app.core.observability import checkpoint
from app.projects import service as projects_service


@dataclass(frozen=True)
class _BlockState:
    id: str
    block_type: str
    position: int
    content: str
    semantic: dict[str, object] | None


def _not_found(kind: str, resource_id: str) -> NotFoundError:
    return NotFoundError(
        problem=f"{kind}不存在",
        cause=f"id '{resource_id}' 未在 Artifact Core 中找到",
        fix="先读取 artifact 及其 current_revision，确认稳定资源 id",
        detail={"resource_type": kind, "resource_id": resource_id},
    )


def _invalid(problem: str, cause: str, fix: str, **detail: object) -> ValidationError:
    return ValidationError(problem=problem, cause=cause, fix=fix, detail=detail)


def _states(
    rows: list[tuple[ArtifactBlockRevision, ArtifactBlock]],
) -> list[_BlockState]:
    return [
        _BlockState(
            id=block.id,
            block_type=block.block_type,
            position=snapshot.position,
            content=snapshot.content,
            semantic=snapshot.semantic_json,
        )
        for snapshot, block in rows
    ]


def _revision_read(revision: ArtifactRevision, states: list[_BlockState]) -> ArtifactRevisionRead:
    return ArtifactRevisionRead(
        id=revision.id,
        artifact_id=revision.artifact_id,
        revision_no=revision.revision_no,
        blocks=[ArtifactBlockRead(**state.__dict__) for state in states],
        created_at=revision.created_at,
    )


async def _load_revision(
    session: AsyncSession, artifact_id: str, revision_id: str
) -> tuple[ArtifactRevision, list[_BlockState]]:
    revision = await repository.get_revision(session, revision_id)
    if revision is None or revision.artifact_id != artifact_id:
        raise _not_found("revision", revision_id)
    return revision, _states(await repository.list_revision_blocks(session, revision.id))


async def _current_revision(
    session: AsyncSession, artifact: Artifact
) -> tuple[ArtifactRevision, list[_BlockState]]:
    revision = await repository.get_revision_by_no(
        session, artifact.id, artifact.current_revision_no
    )
    if revision is None:
        raise _not_found("revision", f"{artifact.id}@{artifact.current_revision_no}")
    return revision, _states(await repository.list_revision_blocks(session, revision.id))


def _artifact_read(
    artifact: Artifact, revision: ArtifactRevision, states: list[_BlockState]
) -> ArtifactRead:
    return ArtifactRead(
        id=artifact.id,
        project_id=artifact.project_id,
        type=artifact.type,
        title=artifact.title,
        status=artifact.status,
        current_revision=_revision_read(revision, states),
        created_at=artifact.created_at,
        updated_at=artifact.updated_at,
    )


def _diff_entries(old: list[_BlockState], new: list[_BlockState]) -> list[RevisionDiffEntry]:
    old_by_id = {block.id: block for block in old}
    new_by_id = {block.id: block for block in new}
    ordered_ids = [block.id for block in old] + [
        block.id for block in new if block.id not in old_by_id
    ]
    entries: list[RevisionDiffEntry] = []
    for block_id in ordered_ids:
        before = old_by_id.get(block_id)
        after = new_by_id.get(block_id)
        if before is None:
            kind = "added"
        elif after is None:
            kind = "removed"
        elif (
            before.position != after.position
            or before.content != after.content
            or before.semantic != after.semantic
        ):
            kind = "modified"
        else:
            kind = "unchanged"
        entries.append(
            RevisionDiffEntry(
                block_id=block_id,
                kind=kind,
                old_position=None if before is None else before.position,
                new_position=None if after is None else after.position,
                old_content=None if before is None else before.content,
                new_content=None if after is None else after.content,
            )
        )
    return entries


@checkpoint
async def create(session: AsyncSession, schema: ArtifactCreate) -> ArtifactRead:
    project_id = schema.project_id or projects_service.DEFAULT_PROJECT_ID
    await projects_service.ensure_exists(session, project_id)
    now = _utcnow()
    artifact = Artifact(
        id=generate_id("art"),
        project_id=project_id,
        type=schema.type,
        title=schema.title,
        status="draft",
        current_revision_no=1,
        created_at=now,
        updated_at=now,
    )
    await repository.add(session, artifact)
    blocks = [
        ArtifactBlock(
            id=generate_id("blk"),
            artifact_id=artifact.id,
            block_type=item.block_type,
            created_at=now,
        )
        for item in schema.blocks
    ]
    for block in blocks:
        await repository.add(session, block)
    revision = ArtifactRevision(
        id=generate_id("rev"), artifact_id=artifact.id, revision_no=1, created_at=now
    )
    await repository.add(session, revision)
    states: list[_BlockState] = []
    for position, (block, item) in enumerate(zip(blocks, schema.blocks, strict=True)):
        await repository.add(
            session,
            ArtifactBlockRevision(
                id=generate_id("brv"),
                revision_id=revision.id,
                block_id=block.id,
                position=position,
                content=item.content,
                semantic_json=item.semantic,
            ),
        )
        states.append(
            _BlockState(block.id, block.block_type, position, item.content, item.semantic)
        )
    await projects_service.touch(session, project_id)
    await session.commit()
    return _artifact_read(artifact, revision, states)


@checkpoint
async def get(session: AsyncSession, artifact_id: str) -> ArtifactRead:
    artifact = await repository.get_artifact(session, artifact_id)
    if artifact is None:
        raise _not_found("artifact", artifact_id)
    revision, states = await _current_revision(session, artifact)
    return _artifact_read(artifact, revision, states)


@checkpoint
async def get_revision(
    session: AsyncSession, artifact_id: str, revision_id: str
) -> ArtifactRevisionRead:
    revision, states = await _load_revision(session, artifact_id, revision_id)
    return _revision_read(revision, states)


@checkpoint
async def diff(
    session: AsyncSession, artifact_id: str, from_revision_id: str, to_revision_id: str
) -> RevisionDiffRead:
    old_revision, old = await _load_revision(session, artifact_id, from_revision_id)
    new_revision, new = await _load_revision(session, artifact_id, to_revision_id)
    entries = _diff_entries(old, new)
    return RevisionDiffRead(
        artifact_id=artifact_id,
        from_revision_id=old_revision.id,
        to_revision_id=new_revision.id,
        changed_block_ids=[entry.block_id for entry in entries if entry.kind != "unchanged"],
        blocks=entries,
    )


@checkpoint
async def edit_block(
    session: AsyncSession, artifact_id: str, block_id: str, schema: BlockEdit
) -> ArtifactRead:
    artifact = await repository.get_artifact(session, artifact_id)
    if artifact is None:
        raise _not_found("artifact", artifact_id)
    block = await repository.get_block(session, block_id)
    if block is None or block.artifact_id != artifact.id:
        raise _not_found("block", block_id)
    old_revision, old_states = await _current_revision(session, artifact)
    current = next((state for state in old_states if state.id == block_id), None)
    if current is None:
        raise _not_found("block", block_id)
    next_semantic = current.semantic if schema.semantic is None else schema.semantic
    if current.content == schema.content and current.semantic == next_semantic:
        raise _invalid(
            "block 编辑没有变化",
            "提交内容与当前 revision 完全一致",
            "修改 block 内容后再提交",
            artifact_id=artifact_id,
            block_id=block_id,
        )

    now = _utcnow()
    new_revision = ArtifactRevision(
        id=generate_id("rev"),
        artifact_id=artifact.id,
        revision_no=old_revision.revision_no + 1,
        created_at=now,
    )
    await repository.add(session, new_revision)
    new_states = [
        _BlockState(
            state.id,
            state.block_type,
            state.position,
            schema.content if state.id == block_id else state.content,
            next_semantic if state.id == block_id else state.semantic,
        )
        for state in old_states
    ]
    for state in new_states:
        await repository.add(
            session,
            ArtifactBlockRevision(
                id=generate_id("brv"),
                revision_id=new_revision.id,
                block_id=state.id,
                position=state.position,
                content=state.content,
                semantic_json=state.semantic,
            ),
        )

    entries = _diff_entries(old_states, new_states)
    changed_ids = [entry.block_id for entry in entries if entry.kind != "unchanged"]
    dependencies = await repository.list_dependencies_for_blocks(session, changed_ids)
    for dependency in dependencies:
        dependency.is_stale = True
        dependency.updated_at = now
        dependent = await repository.get_artifact(session, dependency.dependent_artifact_id)
        if dependent is not None:
            dependent.status = "stale"
            dependent.updated_at = now
    artifact.current_revision_no = new_revision.revision_no
    artifact.updated_at = now
    await repository.flush(session)
    await projects_service.touch(session, artifact.project_id)
    await session.commit()
    return _artifact_read(artifact, new_revision, new_states)


@checkpoint
async def create_dependency(session: AsyncSession, schema: DependencyCreate) -> DependencyRead:
    source = await repository.get_artifact(session, schema.source_artifact_id)
    dependent = await repository.get_artifact(session, schema.dependent_artifact_id)
    if source is None:
        raise _not_found("artifact", schema.source_artifact_id)
    if dependent is None:
        raise _not_found("artifact", schema.dependent_artifact_id)
    if source.id == dependent.id:
        raise _invalid(
            "artifact 不能依赖自身",
            "source 与 dependent 指向同一 artifact",
            "选择另一个 dependent artifact",
            artifact_id=source.id,
        )
    if source.project_id != dependent.project_id:
        raise _invalid(
            "dependency 不能跨项目",
            "source 与 dependent 的 project_id 不一致",
            "选择同一项目内的 artifacts",
            source_project_id=source.project_id,
            dependent_project_id=dependent.project_id,
        )
    block = await repository.get_block(session, schema.source_block_id)
    if block is None or block.artifact_id != source.id:
        raise _invalid(
            "source block 不属于 source artifact",
            "block identity 与 source artifact 不匹配",
            "从 source artifact 的 revision 读取有效 block id",
            source_artifact_id=source.id,
            source_block_id=schema.source_block_id,
        )
    if schema.source_revision_id is None:
        revision = await repository.get_revision_by_no(
            session, source.id, source.current_revision_no
        )
    else:
        revision = await repository.get_revision(session, schema.source_revision_id)
    if revision is None or revision.artifact_id != source.id:
        raise _invalid(
            "source revision 不属于 source artifact",
            "revision identity 与 source artifact 不匹配",
            "使用 source artifact 的 current_revision id",
            source_artifact_id=source.id,
            source_revision_id=schema.source_revision_id,
        )
    now = _utcnow()
    dependency = ArtifactDependency(
        id=generate_id("dep"),
        project_id=source.project_id,
        source_artifact_id=source.id,
        source_block_id=block.id,
        source_revision_id=revision.id,
        dependent_artifact_id=dependent.id,
        dependency_type=schema.dependency_type,
        is_stale=False,
        created_at=now,
        updated_at=now,
    )
    await repository.add(session, dependency)
    await session.commit()
    return DependencyRead.model_validate(dependency)


@checkpoint
async def get_dependency(session: AsyncSession, dependency_id: str) -> DependencyRead:
    dependency = await repository.get_dependency(session, dependency_id)
    if dependency is None:
        raise _not_found("dependency", dependency_id)
    return DependencyRead.model_validate(dependency)


@checkpoint
async def delete_project_data(session: AsyncSession, project_id: str) -> None:
    """Delete Artifact-owned rows inside the projects-router transaction."""
    await repository.delete_by_project(session, project_id)


async def create_structured(
    session: AsyncSession,
    *,
    project_id: str,
    artifact_type: str,
    title: str,
    blocks: list[dict[str, object]],
) -> ArtifactRead:
    """Public cross-domain creation boundary without exposing Artifact internal schemas."""
    return await create(
        session,
        ArtifactCreate.model_validate(
            {"project_id": project_id, "type": artifact_type, "title": title, "blocks": blocks}
        ),
    )


async def create_block_dependencies(
    session: AsyncSession,
    *,
    source_artifact_id: str,
    source_block_ids: list[str],
    dependent_artifact_id: str,
    dependency_type: str = "derived_from",
) -> list[DependencyRead]:
    """Create directed dependencies for selected current source blocks."""
    return [
        await create_dependency(
            session,
            DependencyCreate(
                source_artifact_id=source_artifact_id,
                source_block_id=block_id,
                dependent_artifact_id=dependent_artifact_id,
                dependency_type=dependency_type,
            ),
        )
        for block_id in source_block_ids
    ]


async def edit_structured_block(
    session: AsyncSession,
    *,
    project_id: str,
    artifact_id: str,
    block_id: str,
    content: str,
    semantic: dict[str, object] | None = None,
) -> ArtifactRead:
    artifact = await get(session, artifact_id)
    if artifact.project_id != project_id:
        raise _invalid(
            "artifact 不属于请求项目",
            "candidate target 与 project_id 不一致",
            "只接受同项目 artifact block",
            artifact_id=artifact_id,
        )
    return await edit_block(
        session, artifact_id, block_id, BlockEdit(content=content, semantic=semantic)
    )
