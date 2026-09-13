"""R6 end-to-end no-auto-write and project lifecycle evidence."""

from fastapi.testclient import TestClient


def test_atomic_skill_trace_confirmation_and_project_cleanup(client: TestClient) -> None:
    project_id = client.post("/api/projects", json={"name": "Atomic E2E"}).json()["id"]
    candidate = client.post(
        "/api/skills/requirement.refine/execute",
        json={
            "project_id": project_id,
            "scope_type": "project",
            "scope_id": project_id,
            "context": {"current_requirement": {"format": "vertical"}},
            "input": {},
            "candidate": {"result": {"format": "vertical", "duration": 60}},
        },
    )
    assert candidate.status_code == 201, candidate.text
    assert candidate.json()["status"] == "pending"
    assert candidate.json()["impact"]["writes"] == []

    accepted = client.post(
        f"/api/skills/candidates/{candidate.json()['id']}/accept",
        json={"project_id": project_id},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["committed_ref"] is None
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
