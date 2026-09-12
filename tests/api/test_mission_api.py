from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def create_mission():
    payload = {
        "station_id": "MAITRI",
        "vessel_id": "V001",
        "route_id": "R001",
        "cargo_weight_tonnes": 1500,
        "departure_datetime": "2026-12-01T00:00:00+00:00",
        "safety_buffer_days": 3,
    }

    return client.post(
        "/api/mission",
        json=payload,
    )


def test_create_mission():
    response = create_mission()

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["mission_id"].startswith("MISSION-")
    assert "mission" in data

    mission = data["mission"]

    assert mission["status"] == "PLANNED"
    assert mission["station"]["id"] == "MAITRI"
    assert mission["vessel"]["id"] == "V001"
    assert mission["route"]["id"] == "R001"
    assert mission["cargo_weight_tonnes"] == 1500.0
    assert mission["progress_percent"] == 0.0


def test_get_mission():
    create_response = create_mission()

    assert create_response.status_code == 200

    mission_id = create_response.json()["mission_id"]

    response = client.get(
        f"/api/mission/{mission_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["mission_id"] == mission_id
    assert "mission" in data


def test_start_mission():
    create_response = create_mission()

    mission_id = create_response.json()["mission_id"]

    response = client.post(
        f"/api/mission/{mission_id}/start"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["mission_id"] == mission_id
    assert data["mission"]["status"] == "running"


def test_pause_mission():
    create_response = create_mission()

    mission_id = create_response.json()["mission_id"]

    start_response = client.post(
        f"/api/mission/{mission_id}/start"
    )

    assert start_response.status_code == 200

    response = client.post(
        f"/api/mission/{mission_id}/pause"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["mission_id"] == mission_id
    assert data["mission"]["status"] == "paused"


def test_resume_mission():
    create_response = create_mission()

    mission_id = create_response.json()["mission_id"]

    client.post(
        f"/api/mission/{mission_id}/start"
    )

    pause_response = client.post(
        f"/api/mission/{mission_id}/pause"
    )

    assert pause_response.status_code == 200

    response = client.post(
        f"/api/mission/{mission_id}/resume"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["mission_id"] == mission_id
    assert data["mission"]["status"] == "running"


def test_nonexistent_mission_get_returns_4xx():
    response = client.get(
        "/api/mission/MISSION-DOES-NOT-EXIST"
    )

    assert response.status_code in (400, 404)


def test_nonexistent_mission_start_returns_4xx():
    response = client.post(
        "/api/mission/MISSION-DOES-NOT-EXIST/start"
    )

    assert response.status_code in (400, 404)


def test_nonexistent_mission_pause_returns_4xx():
    response = client.post(
        "/api/mission/MISSION-DOES-NOT-EXIST/pause"
    )

    assert response.status_code in (400, 404)


def test_nonexistent_mission_resume_returns_4xx():
    response = client.post(
        "/api/mission/MISSION-DOES-NOT-EXIST/resume"
    )

    assert response.status_code in (400, 404)