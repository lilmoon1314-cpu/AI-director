"""One user-visible R3 continuity flow through the assembled API."""

from fastapi.testclient import TestClient


def test_screenplay_change_becomes_traceable_state_and_perspective_knowledge(
    client: TestClient,
) -> None:
    project = client.post("/api/projects", json={"name": "R3 E2E"}).json()
    character = client.post(
        "/api/entities",
        json={"project_id": project["id"], "type": "character", "name": "Witness"},
    ).json()
    artifact = client.post(
        "/api/artifacts",
        json={
            "project_id": project["id"],
            "type": "screenplay",
            "title": "Reveal",
            "blocks": [{"block_type": "scene", "content": "The witness finds the key."}],
        },
    ).json()
    timepoint = client.post(
        "/api/narrative-state/timepoints",
        json={"project_id": project["id"], "sequence_no": 10, "scene_id": "scene-reveal"},
    ).json()
    applied = client.post(
        "/api/narrative-state/events",
        json={
            "project_id": project["id"],
            "subject_type": "entity",
            "subject_id": character["id"],
            "attribute_key": "current_location",
            "operation": "set",
            "value": "vault",
            "timepoint_id": timepoint["id"],
            "cause_type": "screenplay",
            "cause_ref": "scene-reveal",
            "source_artifact_id": artifact["id"],
            "source_revision_id": artifact["current_revision"]["id"],
        },
    ).json()
    snapshot = client.post(
        "/api/narrative-state/snapshots",
        json={
            "project_id": project["id"],
            "scope_type": "scene_exit",
            "scope_id": "scene-reveal",
            "timepoint_id": timepoint["id"],
        },
    ).json()
    claim = client.post(
        "/api/narrative-state/claims",
        json={
            "project_id": project["id"],
            "subject_ref": "key",
            "predicate": "location",
            "object_json": "vault",
            "truth_status": "true",
            "author_note": "Do not reveal the second key.",
        },
    ).json()
    audience = client.post(
        "/api/narrative-state/knowledge-states",
        json={
            "project_id": project["id"],
            "knower_type": "audience",
            "claim_id": claim["id"],
            "status": "knows",
            "confidence": 1,
            "acquired_timepoint_id": timepoint["id"],
            "source_ref": artifact["current_revision"]["id"],
        },
    ).json()

    assert applied["event"]["source_revision_id"] == artifact["current_revision"]["id"]
    assert applied["current"]["value_json"] == "vault"
    assert snapshot["source_event_cursor"] == applied["event"]["id"]
    assert snapshot["snapshot_json"][0]["value"] == "vault"
    assert audience["status"] == "knows"
    assert "author_note" not in audience
