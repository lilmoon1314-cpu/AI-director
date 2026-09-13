"""R5 production document chain acceptance."""

from fastapi.testclient import TestClient


def _scope(client: TestClient, name: str = "Production") -> tuple[str, str, str]:
    project = client.post("/api/projects", json={"name": name}).json()
    series = client.post(
        "/api/workflow/series", json={"project_id": project["id"], "title": "S1"}
    ).json()
    episode = client.post(
        "/api/workflow/episodes",
        json={
            "project_id": project["id"],
            "series_id": series["id"],
            "position": 0,
            "title": "Pilot",
        },
    ).json()
    scene = client.post(
        "/api/workflow/scene-plans",
        json={
            "project_id": project["id"],
            "episode_id": episode["id"],
            "position": 0,
            "time_context": "day",
            "scene_goal": "meet",
            "character_goal": "learn",
            "conflict": "distrust",
            "turn": "clue",
            "exit_change": "alliance",
            "target_duration": 60,
        },
    ).json()
    return project["id"], episode["id"], scene["id"]


def _create(
    client: TestClient,
    project_id: str,
    episode_id: str,
    scene_id: str,
    document_type: str,
    block_type: str,
    semantic: dict[str, object],
    source: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "project_id": project_id,
        "episode_id": episode_id,
        "scene_id": scene_id,
        "document_type": document_type,
        "title": document_type,
        "blocks": [{"block_type": block_type, "content": document_type, "semantic": semantic}],
    }
    if source is not None:
        artifact = client.get(f"/api/artifacts/{source['artifact_id']}").json()
        payload["source_document_id"] = source["id"]
        payload["source_block_ids"] = [artifact["current_revision"]["blocks"][0]["id"]]
    response = client.post("/api/production/documents", json=payload)
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_complete_production_chain_and_semantic_snapshots(client: TestClient) -> None:
    project_id, episode_id, scene_id = _scope(client)
    screenplay = _create(client, project_id, episode_id, scene_id, "screenplay", "action", {})
    breakdown = _create(
        client,
        project_id,
        episode_id,
        scene_id,
        "production_breakdown",
        "scene",
        {
            "scene_id": scene_id,
            "cast": ["hero"],
            "location": "room",
            "props": ["key"],
            "asset_refs": [],
        },
        screenplay,
    )
    performance = _create(
        client,
        project_id,
        episode_id,
        scene_id,
        "performance_script",
        "beat",
        {
            "beat_id": "beat-1",
            "source_block_refs": ["screenplay"],
            "duration_target": 4,
            "action": "turn",
            "emotion": "fear",
        },
        breakdown,
    )
    shot = _create(
        client,
        project_id,
        episode_id,
        scene_id,
        "shot_plan",
        "shot",
        {
            "shot_id": "shot-1",
            "scene_id": scene_id,
            "beat_refs": ["beat-1"],
            "duration": 4,
            "framing": "medium",
            "subject_action": "turn",
        },
        performance,
    )
    storyboard = _create(
        client,
        project_id,
        episode_id,
        scene_id,
        "storyboard",
        "panel",
        {"shot_ref": "shot-1", "panel_prompt": "hero turns", "asset_refs": []},
        shot,
    )
    timeline = _create(
        client,
        project_id,
        episode_id,
        scene_id,
        "timeline",
        "clip",
        {"track_type": "shots", "source_ref": "shot-1", "start": 0, "duration": 4},
        storyboard,
    )
    artifact = client.get(f"/api/artifacts/{timeline['artifact_id']}")
    assert artifact.status_code == 200
    assert artifact.json()["type"] == "timeline"
    assert artifact.json()["current_revision"]["blocks"][0]["semantic"]["duration"] == 4


def test_order_validation_and_localized_stale_retains_downstream(client: TestClient) -> None:
    project_id, episode_id, scene_id = _scope(client, "Stale")
    screenplay = _create(client, project_id, episode_id, scene_id, "screenplay", "dialogue", {})
    source_artifact = client.get(f"/api/artifacts/{screenplay['artifact_id']}").json()
    block_id = source_artifact["current_revision"]["blocks"][0]["id"]

    skipped = client.post(
        "/api/production/documents",
        json={
            "project_id": project_id,
            "episode_id": episode_id,
            "scene_id": scene_id,
            "document_type": "shot_plan",
            "title": "bad",
            "source_document_id": screenplay["id"],
            "source_block_ids": [block_id],
            "blocks": [
                {
                    "block_type": "shot",
                    "content": "bad",
                    "semantic": {
                        "shot_id": "s",
                        "scene_id": scene_id,
                        "beat_refs": [],
                        "duration": 1,
                        "framing": "wide",
                        "subject_action": "wait",
                    },
                }
            ],
        },
    )
    assert skipped.status_code == 422

    breakdown = _create(
        client,
        project_id,
        episode_id,
        scene_id,
        "production_breakdown",
        "scene",
        {"scene_id": scene_id, "cast": [], "location": "room", "props": [], "asset_refs": []},
        screenplay,
    )
    edited = client.patch(
        f"/api/artifacts/{screenplay['artifact_id']}/blocks/{block_id}",
        json={"content": "changed", "semantic": {"note": "local"}},
    )
    assert edited.status_code == 200
    retained = client.get(f"/api/production/documents/{breakdown['id']}")
    assert retained.status_code == 200
    dependent = client.get(f"/api/artifacts/{breakdown['artifact_id']}").json()
    assert dependent["status"] == "stale"

    invalid = client.post(
        "/api/production/documents",
        json={
            "project_id": project_id,
            "episode_id": episode_id,
            "document_type": "performance_script",
            "title": "missing semantics",
            "source_document_id": breakdown["id"],
            "source_block_ids": [dependent["current_revision"]["blocks"][0]["id"]],
            "blocks": [{"block_type": "beat", "content": "incomplete", "semantic": {}}],
        },
    )
    assert invalid.status_code == 422
