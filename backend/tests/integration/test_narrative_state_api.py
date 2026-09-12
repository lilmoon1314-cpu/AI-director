"""Cross-layer acceptance for R3 Narrative State Core."""

from typing import Any

from fastapi.testclient import TestClient


def _project(client: TestClient, name: str = "R3") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _entity(client: TestClient, project_id: str, name: str, kind: str = "character") -> str:
    response = client.post(
        "/api/entities",
        json={"project_id": project_id, "type": kind, "name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _relation(client: TestClient, project_id: str) -> str:
    source = _entity(client, project_id, "A")
    target = _entity(client, project_id, "B")
    response = client.post(
        "/api/relations",
        json={"project_id": project_id, "source": source, "target": target, "type": "ally"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _timepoint(client: TestClient, project_id: str, sequence_no: int) -> str:
    response = client.post(
        "/api/narrative-state/timepoints",
        json={"project_id": project_id, "sequence_no": sequence_no, "scene_id": "future-scene-ref"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _event(client: TestClient, **overrides: Any) -> dict[str, Any]:
    payload = {
        "project_id": overrides.pop("project_id"),
        "subject_type": overrides.pop("subject_type"),
        "subject_id": overrides.pop("subject_id"),
        "attribute_key": overrides.pop("attribute_key"),
        "operation": "set",
        "value": "stable",
        "timepoint_id": overrides.pop("timepoint_id"),
        "cause_type": "user_edit",
        "cause_ref": "r3-test",
        **overrides,
    }
    response = client.post("/api/narrative-state/events", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_event_reducer_provenance_history_and_immutable_snapshot(client: TestClient) -> None:
    project_id = _project(client)
    relation_id = _relation(client, project_id)
    tp1 = _timepoint(client, project_id, 1)
    tp2 = _timepoint(client, project_id, 2)
    artifact = client.post(
        "/api/artifacts",
        json={
            "project_id": project_id,
            "type": "screenplay",
            "title": "Episode",
            "blocks": [{"block_type": "scene", "content": "They reconcile."}],
        },
    ).json()
    first = _event(
        client,
        project_id=project_id,
        subject_type="relationship",
        subject_id=relation_id,
        attribute_key="trust",
        timepoint_id=tp1,
        operation="set",
        value=0.25,
        cause_type="screenplay",
        cause_ref="scene-1",
        source_artifact_id=artifact["id"],
        source_revision_id=artifact["current_revision"]["id"],
    )
    assert first["event"]["before_json"] is None
    assert first["current"]["value_json"] == 0.25
    assert first["current"]["version"] == 1

    snapshot = client.post(
        "/api/narrative-state/snapshots",
        json={
            "project_id": project_id,
            "scope_type": "scene_exit",
            "scope_id": "scene-1",
            "timepoint_id": tp1,
        },
    ).json()
    second = _event(
        client,
        project_id=project_id,
        subject_type="relationship",
        subject_id=relation_id,
        attribute_key="trust",
        timepoint_id=tp2,
        operation="transition",
        expected_before=0.25,
        value=0.8,
        compensates_event_id=first["event"]["id"],
    )
    assert second["event"]["before_json"] == 0.25
    assert second["current"]["value_json"] == 0.8
    assert second["current"]["version"] == 2
    assert (
        client.get(f"/api/narrative-state/events/{first['event']['id']}").json() == first["event"]
    )
    historical = client.get(f"/api/narrative-state/snapshots/{snapshot['id']}").json()
    assert historical == snapshot
    assert historical["snapshot_json"][0]["value"] == 0.25


def test_list_reducer_operations_and_conflict(client: TestClient) -> None:
    project_id = _project(client)
    character_id = _entity(client, project_id, "Carrier")
    tp1 = _timepoint(client, project_id, 1)
    tp2 = _timepoint(client, project_id, 2)
    tp3 = _timepoint(client, project_id, 3)
    _event(
        client,
        project_id=project_id,
        subject_type="entity",
        subject_id=character_id,
        attribute_key="condition",
        timepoint_id=tp1,
        value=["tired"],
    )
    added = _event(
        client,
        project_id=project_id,
        subject_type="entity",
        subject_id=character_id,
        attribute_key="condition",
        timepoint_id=tp2,
        operation="add",
        value="injured",
    )
    assert added["current"]["value_json"] == ["tired", "injured"]
    removed = _event(
        client,
        project_id=project_id,
        subject_type="entity",
        subject_id=character_id,
        attribute_key="condition",
        timepoint_id=tp3,
        operation="remove",
        value="tired",
    )
    assert removed["current"]["value_json"] == ["injured"]
    duplicate_timepoint = client.post(
        "/api/narrative-state/timepoints",
        json={"project_id": project_id, "sequence_no": 3},
    )
    assert duplicate_timepoint.status_code == 409
    regressed = client.post(
        "/api/narrative-state/events",
        json={
            "project_id": project_id,
            "subject_type": "entity",
            "subject_id": character_id,
            "attribute_key": "condition",
            "operation": "set",
            "value": ["impossible past rewrite"],
            "timepoint_id": tp1,
            "cause_type": "user_edit",
            "cause_ref": "past",
        },
    )
    assert regressed.status_code == 422
    conflict = client.post(
        "/api/narrative-state/events",
        json={
            "project_id": project_id,
            "subject_type": "entity",
            "subject_id": character_id,
            "attribute_key": "condition",
            "operation": "transition",
            "value": [],
            "expected_before": ["wrong"],
            "timepoint_id": tp3,
            "cause_type": "user_edit",
            "cause_ref": "bad-cas",
        },
    )
    assert conflict.status_code == 409


def test_claim_and_knowledge_keep_author_character_and_audience_separate(
    client: TestClient,
) -> None:
    project_id = _project(client)
    character_id = _entity(client, project_id, "Detective")
    tp1 = _timepoint(client, project_id, 1)
    tp2 = _timepoint(client, project_id, 2)
    claim = client.post(
        "/api/narrative-state/claims",
        json={
            "project_id": project_id,
            "subject_ref": "item-key",
            "predicate": "opens",
            "object_json": {"door": "vault"},
            "truth_status": "true",
            "author_note": "Hidden from the audience",
        },
    ).json()
    character = client.post(
        "/api/narrative-state/knowledge-states",
        json={
            "project_id": project_id,
            "knower_type": "character",
            "knower_id": character_id,
            "claim_id": claim["id"],
            "status": "knows",
            "confidence": 1,
            "acquired_timepoint_id": tp1,
            "source_ref": "witnessed",
        },
    )
    audience_first = client.post(
        "/api/narrative-state/knowledge-states",
        json={
            "project_id": project_id,
            "knower_type": "audience",
            "claim_id": claim["id"],
            "status": "suspects",
            "confidence": 0.4,
            "acquired_timepoint_id": tp1,
            "source_ref": "visual-clue",
        },
    ).json()
    audience_second = client.post(
        "/api/narrative-state/knowledge-states",
        json={
            "project_id": project_id,
            "knower_type": "audience",
            "claim_id": claim["id"],
            "status": "misled",
            "confidence": 0.8,
            "acquired_timepoint_id": tp2,
            "source_ref": "false-reveal",
        },
    ).json()
    assert character.status_code == 201
    assert "author_note" not in character.json()
    current = client.get(
        "/api/narrative-state/knowledge-states/current",
        params={"project_id": project_id, "claim_id": claim["id"], "knower_type": "audience"},
    ).json()
    assert current == audience_second
    assert current["id"] != audience_first["id"]


def test_cross_project_provenance_is_rejected_and_project_delete_cascades(
    client: TestClient,
) -> None:
    first_project = _project(client, "First")
    second_project = _project(client, "Second")
    character_id = _entity(client, first_project, "First character")
    timepoint_id = _timepoint(client, first_project, 1)
    foreign_artifact = client.post(
        "/api/artifacts",
        json={
            "project_id": second_project,
            "type": "screenplay",
            "title": "Foreign",
            "blocks": [{"block_type": "scene", "content": "Hidden"}],
        },
    ).json()
    rejected = client.post(
        "/api/narrative-state/events",
        json={
            "project_id": first_project,
            "subject_type": "entity",
            "subject_id": character_id,
            "attribute_key": "condition",
            "operation": "set",
            "value": "safe",
            "timepoint_id": timepoint_id,
            "cause_type": "screenplay",
            "cause_ref": "foreign",
            "source_artifact_id": foreign_artifact["id"],
            "source_revision_id": foreign_artifact["current_revision"]["id"],
        },
    )
    assert rejected.status_code == 422
    accepted = _event(
        client,
        project_id=first_project,
        subject_type="entity",
        subject_id=character_id,
        attribute_key="condition",
        timepoint_id=timepoint_id,
        value="safe",
    )
    assert client.delete(f"/api/projects/{first_project}").status_code == 204
    assert client.get(f"/api/narrative-state/events/{accepted['event']['id']}").status_code == 404


def test_migrated_relationship_fields_stay_event_backed_in_both_write_paths(
    client: TestClient,
) -> None:
    project_id = _project(client)
    source = _entity(client, project_id, "Source")
    target = _entity(client, project_id, "Target")
    relation = client.post(
        "/api/relations",
        json={
            "project_id": project_id,
            "source": source,
            "target": target,
            "type": "ally",
            "trust": 0.2,
        },
    ).json()
    params = {
        "project_id": project_id,
        "subject_type": "relationship",
        "subject_id": relation["id"],
        "attribute_key": "trust",
    }
    seeded = client.get("/api/narrative-state/current", params=params).json()
    assert seeded["value_json"] == 0.2
    assert seeded["version"] == 1

    timepoint_id = _timepoint(client, project_id, 1)
    temporal = _event(
        client,
        project_id=project_id,
        subject_type="relationship",
        subject_id=relation["id"],
        attribute_key="trust",
        timepoint_id=timepoint_id,
        value=0.8,
    )
    assert temporal["current"]["version"] == 2
    assert client.get(f"/api/relations/{relation['id']}").json()["trust"] == 0.8

    patched = client.patch(f"/api/relations/{relation['id']}", json={"trust": 0.6})
    assert patched.status_code == 200, patched.text
    current = client.get("/api/narrative-state/current", params=params).json()
    assert current["value_json"] == 0.6
    assert current["version"] == 3
    latest_event = client.get(f"/api/narrative-state/events/{current['last_event_id']}").json()
    assert latest_event["cause_ref"] == "relations_api_compatibility"
    assert latest_event["timepoint_id"] == timepoint_id
