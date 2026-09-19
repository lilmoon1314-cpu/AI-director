"""R1 navigation reads preserve hierarchy ownership and stable paging."""

from fastapi.testclient import TestClient


def test_navigation_scope_paging_and_documents(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "Navigation"}).json()["id"]
    other = client.post("/api/projects", json={"name": "Other"}).json()["id"]
    series = [
        client.post(
            "/api/workflow/series",
            json={
                "project_id": project,
                "title": title,
            },
        ).json()["id"]
        for title in ("First", "Second")
    ]
    assert client.get("/api/workflow/series", params={"project_id": other}).json() == []
    page = client.get("/api/workflow/series", params={"project_id": project, "limit": 1}).json()
    next_page = client.get(
        "/api/workflow/series",
        params={
            "project_id": project,
            "limit": 1,
            "offset": 1,
        },
    ).json()
    assert {page[0]["id"], next_page[0]["id"]} == set(series)
    assert page[0]["id"] != next_page[0]["id"]
    episodes = [
        client.post(
            "/api/workflow/episodes",
            json={
                "project_id": project,
                "series_id": series[0],
                "position": position,
                "title": f"Episode {position}",
            },
        ).json()["id"]
        for position in (2, 0, 1)
    ]
    params = {"project_id": project, "series_id": series[0]}
    listed = client.get("/api/workflow/episodes", params=params).json()
    assert [item["position"] for item in listed] == [0, 1, 2]
    assert (
        client.get("/api/workflow/episodes", params={**params, "limit": 1, "offset": 1}).json()[0][
            "position"
        ]
        == 1
    )
    assert (
        client.get(f"/api/workflow/episodes/{episodes[0]}", params=params).json()["id"]
        == episodes[0]
    )
    assert (
        client.get(
            f"/api/workflow/episodes/{episodes[0]}", params={**params, "series_id": series[1]}
        ).status_code
        == 404
    )
    for path, query in [
        (f"/api/workflow/series/{series[0]}", {"project_id": other}),
        ("/api/workflow/episodes", {"project_id": other, "series_id": series[0]}),
        (f"/api/workflow/episodes/{episodes[0]}", {"project_id": other, "series_id": series[0]}),
        ("/api/production/documents", {"project_id": other, "episode_id": episodes[0]}),
    ]:
        assert client.get(path, params=query).status_code in (404, 422)
    document = client.post(
        "/api/production/documents",
        json={
            "project_id": project,
            "episode_id": episodes[0],
            "document_type": "screenplay",
            "title": "Draft",
            "blocks": [{"block_type": "action", "content": "Arrival"}],
        },
    )
    assert document.status_code == 201, document.text
    docs = client.get(
        "/api/production/documents", params={"project_id": project, "episode_id": episodes[0]}
    )
    assert [item["id"] for item in docs.json()] == [document.json()["id"]]
    assert (
        client.get(
            "/api/production/documents", params={"project_id": project, "episode_id": episodes[1]}
        ).json()
        == []
    )
    assert (
        client.get("/api/workflow/series", params={"project_id": project, "limit": 101}).status_code
        == 422
    )
    assert (
        client.get("/api/workflow/series", params={"project_id": project, "offset": -1}).status_code
        == 422
    )
    assert client.get("/api/workflow/series", params={"project_id": "missing"}).status_code == 404
