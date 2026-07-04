"""PPT 渲染任务接口测试。"""

from unittest.mock import patch

from app.store import save_project


def _create_project(project_id: str):
    """辅助函数：创建一个最小测试项目。"""
    save_project(project_id, {
        "id": project_id,
        "title": "测试项目",
        "outline": [],
        "template": None,
        "slides": [],
        "output_path": None,
    })


def test_create_job_success(client):
    _create_project("proj-001")

    with patch("app.routers.jobs.render_ppt_task") as mock_task:
        r = client.post("/api/jobs", json={"project_id": "proj-001"})

    assert r.status_code == 201
    data = r.json()
    assert data["project_id"] == "proj-001"
    assert data["status"] == "pending"
    assert "id" in data
    mock_task.delay.assert_called_once()


def test_create_job_project_not_found(client):
    r = client.post("/api/jobs", json={"project_id": "non-existent-proj"})
    assert r.status_code == 404


def test_get_job_success(client):
    _create_project("proj-002")

    with patch("app.routers.jobs.render_ppt_task"):
        create_resp = client.post("/api/jobs", json={"project_id": "proj-002"})
    job_id = create_resp.json()["id"]

    r = client.get(f"/api/jobs/{job_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == job_id
    assert data["project_id"] == "proj-002"


def test_get_job_not_found(client):
    r = client.get("/api/jobs/non-existent-id")
    assert r.status_code == 404


def test_list_jobs_returns_created_jobs(client):
    _create_project("proj-003")
    _create_project("proj-004")

    with patch("app.routers.jobs.render_ppt_task"):
        client.post("/api/jobs", json={"project_id": "proj-003"})
        client.post("/api/jobs", json={"project_id": "proj-004"})

    r = client.get("/api/jobs")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_jobs_pagination(client):
    for i in range(5):
        pid = f"proj-{i}"
        _create_project(pid)
        with patch("app.routers.jobs.render_ppt_task"):
            client.post("/api/jobs", json={"project_id": pid})

    r = client.get("/api/jobs?limit=2&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2


def test_create_job_with_input_data(client):
    _create_project("proj-005")

    with patch("app.routers.jobs.render_ppt_task") as mock_task:
        r = client.post(
            "/api/jobs",
            json={"project_id": "proj-005", "input_data": '{"pages": 10}'},
        )

    assert r.status_code == 201
    data = r.json()
    assert data["input_data"] == '{"pages": 10}'
    mock_task.delay.assert_called_once()
