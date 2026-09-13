"""R6 Atomic Skills validation, audit, and confirmed-write acceptance."""

from fastapi.testclient import TestClient


def _scope(client: TestClient, name: str = "Skills") -> tuple[str, str, str]:
    project_id = client.post("/api/projects", json={"name": name}).json()["id"]
    series_id = client.post(
        "/api/workflow/series", json={"project_id": project_id, "title": "S"}
    ).json()["id"]
    episode_id = client.post(
        "/api/workflow/episodes",
        json={"project_id": project_id, "series_id": series_id, "position": 0, "title": "E"},
    ).json()["id"]
    scene_id = client.post(
        "/api/workflow/scene-plans",
        json={
            "project_id": project_id,
            "episode_id": episode_id,
            "position": 0,
            "time_context": "day",
            "scene_goal": "talk",
            "character_goal": "learn",
            "conflict": "doubt",
            "turn": "truth",
            "exit_change": "trust",
            "target_duration": 30,
        },
    ).json()["id"]
    return project_id, episode_id, scene_id


def _screenplay(
    client: TestClient, project_id: str, episode_id: str, scene_id: str
) -> tuple[dict[str, object], dict[str, object]]:
    document = client.post(
        "/api/production/documents",
        json={
            "project_id": project_id,
            "episode_id": episode_id,
            "scene_id": scene_id,
            "document_type": "screenplay",
            "title": "Scene",
            "blocks": [{"block_type": "dialogue", "content": "Hello", "semantic": {}}],
        },
    ).json()
    artifact = client.get(f"/api/artifacts/{document['artifact_id']}").json()
    return dict(document), dict(artifact)


def _dialogue_payload(
    project_id: str, block_id: str, artifact_id: str, content: str
) -> dict[str, object]:
    return {
        "project_id": project_id,
        "scope_type": "block",
        "scope_id": block_id,
        "context": {
            "selected_blocks": [block_id],
            "adjacent_blocks": [],
            "speaker_voice_profile": {},
            "scene_objective": "talk",
            "scene_entry_state": {},
        },
        "input": {"facts": ["known"], "protected_spans": ["name"]},
        "candidate": {
            "artifact_id": artifact_id,
            "block_id": block_id,
            "content": content,
            "semantic": {"tone": "warm"},
            "facts": ["known"],
            "protected_spans": ["name"],
        },
    }


def test_registry_context_permissions_and_gate(client: TestClient) -> None:
    project_id, _, scene_id = _scope(client)
    skills = client.get("/api/skills")
    assert skills.status_code == 200
    assert len(skills.json()) == 10

    missing = client.post(
        "/api/skills/audience.audit/execute",
        json={
            "project_id": project_id,
            "scope_type": "scene",
            "scope_id": scene_id,
            "context": {},
            "input": {},
            "candidate": {"result": {}},
        },
    )
    assert missing.status_code == 422
    denied = client.post(
        "/api/skills/audience.audit/execute",
        json={
            "project_id": project_id,
            "scope_type": "scene",
            "scope_id": scene_id,
            "context": {
                "revealed_claims": [],
                "approved_screenplay": [],
                "audience_knowledge": [],
                "hidden_truth": ["secret"],
            },
            "input": {},
            "candidate": {"result": {}},
        },
    )
    assert denied.status_code == 422

    gate_id = client.post(
        "/api/workflow/gates",
        json={
            "project_id": project_id,
            "scope_type": "scene",
            "scope_id": scene_id,
            "stage": "review",
            "requirements": [{"key": "screenplay_approved", "expected": True}],
        },
    ).json()["id"]
    blocked = client.post(
        "/api/skills/continuity.check/execute",
        json={
            "project_id": project_id,
            "scope_type": "scene",
            "scope_id": scene_id,
            "context": {"screenplay_blocks": [], "state_snapshot": {}},
            "input": {},
            "candidate": {"result": {}},
            "gate_id": gate_id,
            "gate_facts": {"screenplay_approved": False},
        },
    )
    assert blocked.status_code == 422


def test_dialogue_candidate_reject_accept_and_validators(client: TestClient) -> None:
    project_id, episode_id, scene_id = _scope(client, "Dialogue")
    _, artifact = _screenplay(client, project_id, episode_id, scene_id)
    block_id = artifact["current_revision"]["blocks"][0]["id"]
    artifact_id = str(artifact["id"])

    changed_fact = _dialogue_payload(project_id, block_id, artifact_id, "Natural")
    changed_fact["candidate"]["facts"] = ["invented"]
    assert (
        client.post("/api/skills/dialogue.humanize/execute", json=changed_fact).status_code == 422
    )

    pending = client.post(
        "/api/skills/dialogue.humanize/execute",
        json=_dialogue_payload(project_id, block_id, artifact_id, "Natural"),
    )
    assert pending.status_code == 201, pending.text
    assert pending.json()["status"] == "pending"
    assert pending.json()["impact"]["requires_confirmation"] is True
    assert (
        client.get(f"/api/artifacts/{artifact_id}").json()["current_revision"]["blocks"][0][
            "content"
        ]
        == "Hello"
    )
    rejected = client.post(
        f"/api/skills/candidates/{pending.json()['id']}/reject", json={"project_id": project_id}
    )
    assert rejected.json()["status"] == "rejected"
    assert (
        client.post(
            f"/api/skills/candidates/{pending.json()['id']}/accept", json={"project_id": project_id}
        ).status_code
        == 409
    )

    accepted_candidate = client.post(
        "/api/skills/dialogue.humanize/execute",
        json=_dialogue_payload(project_id, block_id, artifact_id, "Natural"),
    ).json()
    accepted = client.post(
        f"/api/skills/candidates/{accepted_candidate['id']}/accept",
        json={"project_id": project_id},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    revised = client.get(f"/api/artifacts/{artifact_id}").json()
    assert revised["current_revision"]["revision_no"] == 2
    assert revised["current_revision"]["blocks"][0]["content"] == "Natural"


def test_production_candidate_accept_and_project_isolation(client: TestClient) -> None:
    project_id, episode_id, scene_id = _scope(client, "Production skill")
    other_project, _, _ = _scope(client, "Other")
    screenplay, artifact = _screenplay(client, project_id, episode_id, scene_id)
    source_block = artifact["current_revision"]["blocks"][0]["id"]
    execute = client.post(
        "/api/skills/production.breakdown/execute",
        json={
            "project_id": project_id,
            "scope_type": "scene",
            "scope_id": scene_id,
            "context": {"screenplay_blocks": artifact["current_revision"]["blocks"]},
            "input": {},
            "candidate": {
                "production_document": {
                    "episode_id": episode_id,
                    "scene_id": scene_id,
                    "document_type": "production_breakdown",
                    "title": "Breakdown",
                    "source_document_id": screenplay["id"],
                    "source_block_ids": [source_block],
                    "blocks": [
                        {
                            "block_type": "scene",
                            "content": "resources",
                            "semantic": {
                                "scene_id": scene_id,
                                "cast": [],
                                "location": "room",
                                "props": [],
                                "asset_refs": [],
                            },
                        }
                    ],
                }
            },
        },
    )
    assert execute.status_code == 201, execute.text
    cross = client.post(
        f"/api/skills/candidates/{execute.json()['id']}/accept",
        json={"project_id": other_project},
    )
    assert cross.status_code == 422
    accepted = client.post(
        f"/api/skills/candidates/{execute.json()['id']}/accept",
        json={"project_id": project_id},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["committed_ref"].startswith("pdoc-")
