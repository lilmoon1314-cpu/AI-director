"""R2 end-to-end acceptance chain through public HTTP behavior."""

from fastapi.testclient import TestClient


def test_segment_edit_revision_diff_and_localized_stale(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "R2 E2E"}).json()

    def create(title: str, contents: list[str]) -> dict[str, object]:
        response = client.post(
            "/api/artifacts",
            json={
                "project_id": project["id"],
                "type": "screenplay",
                "title": title,
                "blocks": [{"block_type": "scene", "content": content} for content in contents],
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    source = create("Source", ["A0", "B0"])
    downstream_a = create("A output", ["A derived"])
    downstream_b = create("B output", ["B derived"])
    old_revision = source["current_revision"]  # type: ignore[index]
    block_a, block_b = old_revision["blocks"]  # type: ignore[index]

    dep_a = client.post(
        "/api/artifacts/dependencies",
        json={
            "source_artifact_id": source["id"],
            "source_block_id": block_a["id"],
            "dependent_artifact_id": downstream_a["id"],
        },
    ).json()
    dep_b = client.post(
        "/api/artifacts/dependencies",
        json={
            "source_artifact_id": source["id"],
            "source_block_id": block_b["id"],
            "dependent_artifact_id": downstream_b["id"],
        },
    ).json()

    edited = client.patch(
        f"/api/artifacts/{source['id']}/blocks/{block_a['id']}", json={"content": "A1"}
    ).json()
    diff = client.get(
        f"/api/artifacts/{source['id']}/diff",
        params={
            "from_revision_id": old_revision["id"],
            "to_revision_id": edited["current_revision"]["id"],
        },
    ).json()

    assert edited["id"] == source["id"]
    assert edited["current_revision"]["revision_no"] == 2
    assert diff["changed_block_ids"] == [block_a["id"]]
    assert client.get(f"/api/artifacts/dependencies/{dep_a['id']}").json()["is_stale"]
    assert not client.get(f"/api/artifacts/dependencies/{dep_b['id']}").json()["is_stale"]
