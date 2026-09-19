"""V4-R2 acceptance through HTTP and real SQLite transactions."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import get_session_factory


def project(client: TestClient) -> str:
    return client.post("/api/projects", json={"name": "Lineage acceptance"}).json()["id"]


def artifact(client: TestClient, project_id: str, *contents: str) -> dict:
    response = client.post(
        "/api/artifacts",
        json={
            "project_id": project_id,
            "type": "screenplay",
            "title": "Acceptance",
            "blocks": [{"block_type": "action", "content": c} for c in contents],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def ref(art: dict, block: int | None = None) -> dict:
    return {
        "type": "artifact" if block is None else "artifact_block",
        "id": art["id"] if block is None else art["current_revision"]["blocks"][block]["id"],
        "revision_ref": art["current_revision"]["id"],
    }


def base(project_id: str) -> str:
    return f"/api/projects/{project_id}/lineage"


def edge(
    client: TestClient,
    pid: str,
    src: dict,
    dst: dict,
    block: int = 0,
    policy: str = "hard_stale",
    validator: str | None = None,
) -> dict:
    response = client.post(
        base(pid) + "/edges",
        json={
            "upstream": ref(src, block),
            "downstream": ref(dst),
            "invalidation_policy": policy,
            "compatibility_validator": validator,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def edit(client: TestClient, art: dict, content: str, block: int = 0) -> dict:
    response = client.patch(
        f"/api/artifacts/{art['id']}/blocks/{ref(art, block)['id']}", json={"content": content}
    )
    assert response.status_code == 200, response.text
    return response.json()


def read(client: TestClient, art: dict) -> dict:
    response = client.get(f"/api/artifacts/{art['id']}")
    assert response.status_code == 200, response.text
    return response.json()


def proposal(client: TestClient, pid: str, src: dict, dst: dict, content: str) -> dict:
    response = client.post(
        base(pid) + "/proposals",
        json={
            "origin": ref(dst),
            "target": ref(src, 0),
            "content": content,
            "actor": "director",
            "rationale": "Observed staging requires this upstream action",
            "evidence": {"frame": 42},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def decide(client: TestClient, pid: str, prop: dict, decision: str = "accept"):
    return client.post(
        base(pid) + f"/proposals/{prop['id']}/decision",
        json={"decision": decision, "actor": "author", "rationale": "Reviewed source and staging"},
    )


def test_exact_impact_approval_and_transitive_freshness(client: TestClient):
    pid = project(client)
    src = artifact(client, pid, "B42 old", "B43 stable")
    dst = artifact(client, pid, "Shot B42")
    unrelated = artifact(client, pid, "Shot B43")
    child = artifact(client, pid, "Storyboard")
    dep = edge(client, pid, src, dst)
    edge(client, pid, src, unrelated, 1)
    edge(client, pid, dst, child)
    for status in ("review", "approved"):
        response = client.post(
            f"/api/artifacts/{dst['id']}/approval",
            json={
                "approval_status": status,
                "expected_revision_id": ref(dst)["revision_ref"],
                "actor": "author",
                "rationale": "Reviewed",
            },
        )
        assert response.status_code == 200, response.text
    impact = client.post(
        base(pid) + "/impact", json={"source": ref(src), "changed_block_ids": [ref(src, 0)["id"]]}
    ).json()
    assert [e["id"] for e in impact["edges"]] == [dep["id"]]
    assert impact["blocked_artifact_ids"] == [child["id"]]
    assert read(client, dst)["freshness"] == "VALID"  # preview is read-only
    src = edit(client, src, "B43 unrelated edit", 1)
    assert read(client, dst)["freshness"] == "VALID"
    src = edit(client, src, "B42 new")  # dependency baseline is now two revisions old
    assert read(client, dst)["approval_status"] == "approved"
    assert read(client, dst)["freshness"] == "STALE"
    assert read(client, child)["freshness"] == "BLOCKED"
    review = client.post(
        base(pid) + f"/edges/{dep['id']}/review",
        json={
            "decision": "still_valid",
            "actor": "author",
            "rationale": "Shot already accommodates change",
            "expected_upstream_revision_ref": ref(src)["revision_ref"],
            "expected_downstream_revision_ref": ref(dst)["revision_ref"],
        },
    )
    assert review.status_code == 200, review.text
    assert read(client, dst)["approval_status"] == "approved"
    assert read(client, dst)["freshness"] == read(client, child)["freshness"] == "VALID"
    history = client.get(base(pid) + "/edges").json()
    assert next(e for e in history if e["id"] == dep["id"])["state"] == "superseded"
    assert review.json()["supersedes_id"] == dep["id"]
    assert review.json()["downstream_revision_ref"] != ref(dst)["revision_ref"]


@pytest.mark.parametrize(
    ("policy", "validator", "expected"),
    [
        ("hard_stale", None, "STALE"),
        ("review_required", None, "STALE"),
        ("compatibility_check", "content_equal", "BLOCKED"),
        ("timing_revalidate", "timing_equal", "BLOCKED"),
        ("notice_only", None, "VALID"),
        ("none", None, "VALID"),
    ],
)
def test_invalidation_policies(client: TestClient, policy, validator, expected):
    pid = project(client)
    src, dst = artifact(client, pid, "Old"), artifact(client, pid, "Different")
    dep = edge(client, pid, src, dst, policy=policy, validator=validator)
    src = edit(client, src, "New")
    assert read(client, dst)["freshness"] == expected
    if expected == "BLOCKED":
        response = client.post(
            base(pid) + f"/edges/{dep['id']}/review",
            json={
                "decision": "still_valid",
                "actor": "author",
                "rationale": "Cannot bypass validator",
                "expected_upstream_revision_ref": ref(src)["revision_ref"],
                "expected_downstream_revision_ref": ref(dst)["revision_ref"],
            },
        )
        assert response.status_code == 422
        assert read(client, dst)["current_revision"]["revision_no"] == 1


def test_proposal_accept_validated_rebase_replay_and_history(client: TestClient):
    pid = project(client)
    src, dst = artifact(client, pid, "Walk"), artifact(client, pid, "Run")
    other = artifact(client, pid, "Other shot")
    dep = edge(client, pid, src, dst, validator="content_equal")
    edge(client, pid, src, other)
    prop = proposal(client, pid, src, dst, "Run")
    assert read(client, src)["current_revision"]["revision_no"] == 1
    result = decide(client, pid, prop)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "accepted"
    assert read(client, src)["current_revision"]["revision_no"] == 2
    assert read(client, dst)["current_revision"]["revision_no"] == 2
    assert read(client, dst)["freshness"] == "VALID"
    assert read(client, other)["freshness"] == "STALE"
    assert decide(client, pid, prop).json() == result.json()
    assert read(client, src)["current_revision"]["revision_no"] == 2
    assert decide(client, pid, prop, "reject").status_code == 409
    old = client.get(f"/api/artifacts/{src['id']}/revisions/{ref(src)['revision_ref']}").json()
    assert old["blocks"][0]["content"] == "Walk"
    events = client.get(base(pid) + "/reviews").json()
    assert len([e for e in events if e["action"] == "change_proposal_accepted"]) == 1
    assert any(
        e["action"] == "dependency_rebased" and e["details_json"]["previous_edge_id"] == dep["id"]
        for e in events
    )
    assert client.delete(f"/api/projects/{pid}").status_code == 204


def test_incompatible_proposal_remains_stale_and_rejection_has_no_write(client: TestClient):
    pid = project(client)
    src, dst = artifact(client, pid, "Walk"), artifact(client, pid, "Different staging")
    edge(client, pid, src, dst, validator="content_equal")
    rejected = proposal(client, pid, src, dst, "Reject this")
    assert decide(client, pid, rejected, "reject").status_code == 200
    assert read(client, src)["current_revision"]["revision_no"] == 1
    accepted = proposal(client, pid, src, dst, "Run")
    assert decide(client, pid, accepted).status_code == 200
    assert read(client, dst)["freshness"] == "STALE"
    assert read(client, dst)["current_revision"]["revision_no"] == 1


@pytest.mark.parametrize("changed", ["source", "origin"])
def test_proposal_conflict_rolls_back_claim_and_audit(client: TestClient, changed):
    pid = project(client)
    src, dst = artifact(client, pid, "Walk"), artifact(client, pid, "Run")
    edge(client, pid, src, dst, validator="content_equal")
    prop = proposal(client, pid, src, dst, "Run")
    edit(client, src if changed == "source" else dst, "Concurrent edit")
    before = client.get(base(pid) + "/reviews").json()
    assert decide(client, pid, prop).status_code == 409
    after = client.get(base(pid) + "/reviews").json()
    assert after == before
    assert client.get(base(pid) + "/proposals").json()[0]["status"] == "proposed"


def test_revert_is_new_revision_and_preserves_semantics(client: TestClient):
    pid = project(client)
    src, dst = artifact(client, pid, "v1"), artifact(client, pid, "Dependent")
    v1 = ref(src)["revision_ref"]
    src = edit(client, src, "v2")
    edge(client, pid, src, dst)
    response = client.post(
        f"/api/artifacts/{src['id']}/revert",
        json={
            "revision_id": v1,
            "expected_revision_id": ref(src)["revision_ref"],
            "actor": "author",
            "rationale": "Restore earlier action",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["current_revision"]["revision_no"] == 3
    assert response.json()["current_revision"]["blocks"][0]["content"] == "v1"
    old = client.get(f"/api/artifacts/{src['id']}/revisions/{ref(src)['revision_ref']}").json()
    assert old["blocks"][0]["content"] == "v2"
    assert read(client, dst)["freshness"] == "STALE"


def test_ownership_cycle_historical_baseline_and_legacy_cutover(client: TestClient):
    pid, other = project(client), project(client)
    src, dst = artifact(client, pid, "v1"), artifact(client, pid, "D")
    foreign = artifact(client, other, "Foreign")
    assert (
        client.post(
            base(pid) + "/edges", json={"upstream": ref(src, 0), "downstream": ref(foreign)}
        ).status_code
        == 422
    )
    forged = ref(src, 0) | {"revision_ref": ref(dst)["revision_ref"]}
    assert (
        client.post(
            base(pid) + "/edges", json={"upstream": forged, "downstream": ref(dst)}
        ).status_code
        == 404
    )
    edited = edit(client, src, "v2")
    dep = edge(client, pid, src, dst)  # historical source must start stale
    assert dep["state"] == "stale"
    assert (
        client.post(
            base(pid) + "/edges", json={"upstream": ref(dst, 0), "downstream": ref(edited)}
        ).status_code
        == 422
    )
    assert (
        client.post(
            base(other) + f"/edges/{dep['id']}/review",
            json={
                "decision": "still_valid",
                "actor": "author",
                "rationale": "Wrong project",
                "expected_upstream_revision_ref": ref(edited)["revision_ref"],
                "expected_downstream_revision_ref": ref(dst)["revision_ref"],
            },
        ).status_code
        == 404
    )
    legacy_dst = artifact(client, pid, "Legacy API")
    legacy = client.post(
        "/api/artifacts/dependencies",
        json={
            "source_artifact_id": src["id"],
            "source_block_id": ref(src, 0)["id"],
            "dependent_artifact_id": legacy_dst["id"],
        },
    )
    assert legacy.status_code == 201, legacy.text

    async def counts():
        async with get_session_factory()() as session:
            return (
                await session.scalar(text("SELECT count(*) FROM artifact_dependencies")),
                await session.scalar(text("SELECT count(*) FROM lineage_edges")),
            )

    assert asyncio.run(counts()) == (0, 2)


@pytest.mark.parametrize("boundary", ["target", "rebase"])
def test_accept_failure_rolls_back_every_owner(client: TestClient, monkeypatch, boundary):
    from app.artifacts import service as artifacts
    from app.core.exceptions import ConflictError
    from app.lineage import service as lineage

    pid = project(client)
    src, dst = artifact(client, pid, "Walk"), artifact(client, pid, "Run")
    edge(client, pid, src, dst, validator="content_equal")
    prop = proposal(client, pid, src, dst, "Run")
    before = client.get(base(pid) + "/reviews").json()
    if boundary == "target":
        original = artifacts.edit_structured_block

        async def fail_target(*args, **kwargs):
            await original(*args, **kwargs)
            raise ConflictError("Injected failure", "After target write", "Retry")

        monkeypatch.setattr(artifacts, "edit_structured_block", fail_target)
    else:
        original_audit = lineage.audit

        async def fail_rebase(*args, **kwargs):
            await original_audit(*args, **kwargs)
            if args[3] == "dependency_rebased":
                raise ConflictError("Injected failure", "After rebase write", "Retry")

        monkeypatch.setattr(lineage, "audit", fail_rebase)
    assert decide(client, pid, prop).status_code == 409
    assert read(client, src)["current_revision"]["revision_no"] == 1
    assert read(client, dst)["current_revision"]["revision_no"] == 1
    assert read(client, dst)["freshness"] == "VALID"
    assert client.get(base(pid) + "/proposals").json()[0]["status"] == "proposed"
    assert client.get(base(pid) + "/reviews").json() == before
    assert len(client.get(base(pid) + "/edges").json()) == 1


def test_concurrent_confirmations_commit_once(client: TestClient):
    from concurrent.futures import ThreadPoolExecutor

    pid = project(client)
    src, dst = artifact(client, pid, "Walk"), artifact(client, pid, "Run")
    edge(client, pid, src, dst, validator="content_equal")
    prop = proposal(client, pid, src, dst, "Run")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: decide(client, pid, prop), range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json() == results[1].json()
    assert read(client, src)["current_revision"]["revision_no"] == 2
    assert read(client, dst)["current_revision"]["revision_no"] == 2


def test_revert_downstream_requires_source_review(client: TestClient):
    pid = project(client)
    src, dst = artifact(client, pid, "Source"), artifact(client, pid, "Original")
    edge(client, pid, src, dst)
    updated = edit(client, dst, "New downstream")
    response = client.post(
        f"/api/artifacts/{dst['id']}/revert",
        json={
            "revision_id": ref(dst)["revision_ref"],
            "expected_revision_id": ref(updated)["revision_ref"],
            "actor": "author",
            "rationale": "Restore old staging and review sources",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["freshness"] == "STALE"
    assert response.json()["current_revision"]["revision_no"] == 3
