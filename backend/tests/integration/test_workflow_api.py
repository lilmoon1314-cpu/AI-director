"""R4 Workflow Core cross-layer acceptance."""

from fastapi.testclient import TestClient


def _project(client: TestClient, name: str) -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_requirement_hierarchy_gate_and_mock_run(client: TestClient) -> None:
    project_id = _project(client, "Workflow")
    first = client.post(
        "/api/workflow/requirements",
        json={
            "project_id": project_id,
            "content": {"format": "vertical", "audience": "teen"},
        },
    )
    second = client.post(
        "/api/workflow/requirements",
        json={
            "project_id": project_id,
            "content": {"format": "vertical", "audience": "family"},
        },
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["version"] == 1
    assert second.json()["version"] == 2
    assert (
        client.get("/api/workflow/requirements/current", params={"project_id": project_id}).json()[
            "content"
        ]["audience"]
        == "family"
    )

    series = client.post("/api/workflow/series", json={"project_id": project_id, "title": "S1"})
    assert series.status_code == 201, series.text
    episode = client.post(
        "/api/workflow/episodes",
        json={
            "project_id": project_id,
            "series_id": series.json()["id"],
            "position": 0,
            "title": "Pilot",
            "outline": "Arrival",
        },
    )
    assert episode.status_code == 201, episode.text
    scene = client.post(
        "/api/workflow/scene-plans",
        json={
            "project_id": project_id,
            "episode_id": episode.json()["id"],
            "position": 0,
            "location_ref": "station",
            "time_context": "night",
            "characters": ["hero"],
            "scene_goal": "arrive",
            "character_goal": "hide",
            "conflict": "guard",
            "turn": "recognized",
            "reveal": "old badge",
            "exit_change": "must flee",
            "target_duration": 90,
            "required_setup": ["badge"],
            "required_payoff": ["pursuit"],
        },
    )
    assert scene.status_code == 201, scene.text
    assert scene.json()["required_payoff"] == ["pursuit"]

    gate = client.post(
        "/api/workflow/gates",
        json={
            "project_id": project_id,
            "scope_type": "episode",
            "scope_id": episode.json()["id"],
            "stage": "screenplay",
            "requirements": [
                {"key": "requirement_approved", "expected": True},
                {"key": "scene_plans_complete", "expected": True},
            ],
        },
    )
    assert gate.status_code == 201, gate.text
    blocked = client.post(
        f"/api/workflow/gates/{gate.json()['id']}/evaluate",
        json={
            "facts": {"requirement_approved": True, "scene_plans_complete": False},
        },
    )
    assert blocked.json()["passed"] is False
    assert [item["key"] for item in blocked.json()["unmet"]] == ["scene_plans_complete"]
    passed = client.post(
        f"/api/workflow/gates/{gate.json()['id']}/evaluate",
        json={
            "facts": {"requirement_approved": True, "scene_plans_complete": True},
        },
    )
    assert passed.json() == {"gate_id": gate.json()["id"], "passed": True, "unmet": []}

    run = client.post(
        "/api/workflow/runs",
        json={
            "project_id": project_id,
            "scope_type": "scene",
            "scope_id": scene.json()["id"],
            "skill_id": "screenplay.scene_write",
            "input": {"scene_plan_id": scene.json()["id"]},
        },
    )
    assert run.status_code == 201 and run.json()["status"] == "pending"
    done = client.post(
        f"/api/workflow/runs/{run.json()['id']}/mock-execute",
        json={
            "output": {"candidate": "not canonical"},
            "steps": [
                {"kind": "read", "detail": {"source": "scene_plan"}},
                {"kind": "candidate", "detail": {"writes": False}},
            ],
        },
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"
    assert [step["position"] for step in done.json()["steps"]] == [0, 1]


def test_workflow_project_isolation_order_conflicts_and_cleanup(client: TestClient) -> None:
    left = _project(client, "Left")
    right = _project(client, "Right")
    series = client.post(
        "/api/workflow/series", json={"project_id": left, "title": "Only left"}
    ).json()
    cross = client.post(
        "/api/workflow/episodes",
        json={
            "project_id": right,
            "series_id": series["id"],
            "position": 0,
            "title": "Wrong",
        },
    )
    assert cross.status_code == 422

    one = client.post(
        "/api/workflow/episodes",
        json={
            "project_id": left,
            "series_id": series["id"],
            "position": 0,
            "title": "One",
        },
    )
    assert one.status_code == 201
    duplicate = client.post(
        "/api/workflow/episodes",
        json={
            "project_id": left,
            "series_id": series["id"],
            "position": 0,
            "title": "Duplicate",
        },
    )
    assert duplicate.status_code == 409

    assert client.delete(f"/api/projects/{left}").status_code == 204
    missing = client.post(
        "/api/workflow/runs",
        json={
            "project_id": left,
            "scope_type": "episode",
            "scope_id": one.json()["id"],
            "skill_id": "mock",
            "input": {},
        },
    )
    assert missing.status_code == 404
