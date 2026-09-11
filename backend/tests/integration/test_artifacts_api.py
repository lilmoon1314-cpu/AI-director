"""Artifact Core public API integration evidence."""

from typing import Any

from fastapi.testclient import TestClient


def _create_project(client: TestClient, name: str = "R2 Project") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _create_screenplay(
    client: TestClient,
    project_id: str,
    title: str,
    contents: list[str],
) -> dict[str, Any]:
    response = client.post(
        "/api/artifacts",
        json={
            "project_id": project_id,
            "type": "screenplay",
            "title": title,
            "blocks": [{"block_type": "scene", "content": content} for content in contents],
        },
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


def test_screenplay_foundation_and_project_lifecycle(client: TestClient) -> None:
    project_id = _create_project(client)
    created = _create_screenplay(client, project_id, "Pilot", ["Scene A", "Scene B"])

    assert created["type"] == "screenplay"
    assert created["current_revision"]["revision_no"] == 1
    blocks = created["current_revision"]["blocks"]
    assert [block["position"] for block in blocks] == [0, 1]
    assert len({block["id"] for block in blocks}) == 2
    assert all(block["id"].startswith("blk-") for block in blocks)
    assert client.get(f"/api/artifacts/{created['id']}").json() == created

    deleted = client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 204, deleted.text
    missing = client.get(f"/api/artifacts/{created['id']}")
    assert missing.status_code == 404


def test_block_edit_creates_immutable_revision_and_local_diff(client: TestClient) -> None:
    project_id = _create_project(client)
    created = _create_screenplay(client, project_id, "Pilot", ["Old A", "Stable B"])
    artifact_id = created["id"]
    old_revision = created["current_revision"]
    block_a, block_b = old_revision["blocks"]

    edited_response = client.patch(
        f"/api/artifacts/{artifact_id}/blocks/{block_a['id']}",
        json={"content": "New A"},
    )
    assert edited_response.status_code == 200, edited_response.text
    edited = edited_response.json()
    new_revision = edited["current_revision"]
    assert edited["id"] == artifact_id
    assert new_revision["revision_no"] == 2
    assert [block["id"] for block in new_revision["blocks"]] == [block_a["id"], block_b["id"]]

    historical = client.get(f"/api/artifacts/{artifact_id}/revisions/{old_revision['id']}")
    assert historical.status_code == 200, historical.text
    assert [block["content"] for block in historical.json()["blocks"]] == [
        "Old A",
        "Stable B",
    ]

    diff = client.get(
        f"/api/artifacts/{artifact_id}/diff",
        params={
            "from_revision_id": old_revision["id"],
            "to_revision_id": new_revision["id"],
        },
    )
    assert diff.status_code == 200, diff.text
    body = diff.json()
    assert body["changed_block_ids"] == [block_a["id"]]
    assert {entry["block_id"]: entry["kind"] for entry in body["blocks"]} == {
        block_a["id"]: "modified",
        block_b["id"]: "unchanged",
    }


def test_localized_stale_only_invalidates_changed_block_branch(client: TestClient) -> None:
    project_id = _create_project(client)
    source = _create_screenplay(client, project_id, "Source", ["Branch A", "Branch B"])
    dependent_a = _create_screenplay(client, project_id, "Dependent A", ["Derived A"])
    dependent_b = _create_screenplay(client, project_id, "Dependent B", ["Derived B"])
    source_revision = source["current_revision"]
    block_a, block_b = source_revision["blocks"]

    dependency_ids: list[str] = []
    for block, dependent in ((block_a, dependent_a), (block_b, dependent_b)):
        response = client.post(
            "/api/artifacts/dependencies",
            json={
                "source_artifact_id": source["id"],
                "source_block_id": block["id"],
                "source_revision_id": source_revision["id"],
                "dependent_artifact_id": dependent["id"],
            },
        )
        assert response.status_code == 201, response.text
        dependency_ids.append(response.json()["id"])

    edited = client.patch(
        f"/api/artifacts/{source['id']}/blocks/{block_a['id']}",
        json={"content": "Branch A revised"},
    )
    assert edited.status_code == 200, edited.text
    new_revision_id = edited.json()["current_revision"]["id"]

    dependency_a = client.get(f"/api/artifacts/dependencies/{dependency_ids[0]}").json()
    dependency_b = client.get(f"/api/artifacts/dependencies/{dependency_ids[1]}").json()
    assert dependency_a["is_stale"] is True
    assert dependency_b["is_stale"] is False
    assert client.get(f"/api/artifacts/{dependent_a['id']}").json()["status"] == "stale"
    assert client.get(f"/api/artifacts/{dependent_b['id']}").json()["status"] == "draft"

    diff = client.get(
        f"/api/artifacts/{source['id']}/diff",
        params={
            "from_revision_id": source_revision["id"],
            "to_revision_id": new_revision_id,
        },
    ).json()
    assert diff["changed_block_ids"] == [block_a["id"]]
    assert (
        next(entry for entry in diff["blocks"] if entry["block_id"] == block_b["id"])["kind"]
        == "unchanged"
    )


def test_dependency_rejects_cross_project_ownership(client: TestClient) -> None:
    source_project = _create_project(client, "Source Project")
    other_project = _create_project(client, "Other Project")
    source = _create_screenplay(client, source_project, "Source", ["A"])
    dependent = _create_screenplay(client, other_project, "Dependent", ["B"])

    response = client.post(
        "/api/artifacts/dependencies",
        json={
            "source_artifact_id": source["id"],
            "source_block_id": source["current_revision"]["blocks"][0]["id"],
            "dependent_artifact_id": dependent["id"],
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
