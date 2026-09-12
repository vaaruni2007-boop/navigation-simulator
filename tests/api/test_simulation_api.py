from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def create_started_mission():
    payload = {
        "station_id": "MAITRI",
        "vessel_id": "V001",
        "route_id": "R001",
        "cargo_weight_tonnes": 1500,
        "departure_datetime": "2026-12-01T00:00:00+00:00",
        "safety_buffer_days": 3,
    }

    create_response = client.post(
        "/api/mission",
        json=payload,
    )

    assert create_response.status_code == 200

    mission_id = create_response.json()["mission_id"]

    start_response = client.post(
        f"/api/mission/{mission_id}/start"
    )

    assert start_response.status_code == 200

    return mission_id, start_response.json()


def test_start_returns_initial_simulation_state():
    mission_id, data = create_started_mission()

    mission = data["mission"]

    assert mission_id.startswith("MISSION-")
    assert mission["status"] == "running"

    assert "simulation_datetime" in mission
    assert "vessel_position" in mission
    assert "vessel_progress" in mission
    assert "fuel_consumed_litres" in mission
    assert "fuel_remaining_litres" in mission
    assert "fuel_remaining_percent" in mission
    assert "estimated_total_fuel_litres" in mission
    assert "estimated_total_cost" in mission
    assert "inventory" in mission
    assert "environment" in mission
    assert "risk" in mission


def test_initial_simulation_values_are_correct():
    _, data = create_started_mission()

    mission = data["mission"]

    assert mission["simulation_datetime"] == "2026-12-01T00:00:00+00:00"

    assert mission["vessel_progress"] == 0.0

    assert mission["fuel_consumed_litres"] == 0.0
    assert mission["fuel_remaining_litres"] == 500000.0
    assert mission["fuel_remaining_percent"] == 100.0

    assert mission["vessel_position"]["latitude"] == 18.9679
    assert mission["vessel_position"]["longitude"] == 72.8347


def test_simulation_contains_inventory():
    _, data = create_started_mission()

    mission = data["mission"]

    assert "diesel" in mission["inventory"]
    assert mission["inventory"]["diesel"] == 300000.0


def test_simulation_contains_environment():
    _, data = create_started_mission()

    environment = data["mission"]["environment"]

    assert environment["weather_severity"] == 0.0
    assert environment["sea_ice_severity"] == 0.0
    assert environment["current_factor"] == 1.0
    assert environment["visibility_factor"] == 1.0
    assert environment["overall_severity"] == 0.0
    assert environment["active_event"] is None


def test_simulation_contains_safe_risk_state():
    _, data = create_started_mission()

    risk = data["mission"]["risk"]

    assert risk["overall_status"] == "SAFE"
    assert risk["arrival_status"] == "SAFE"
    assert risk["arrival_feasible"] is True
    assert risk["delay_days"] == 0.0
    assert risk["safety_margin_days"] > 0


def test_update_advances_simulation():
    mission_id, _ = create_started_mission()

    response = client.post(
        f"/api/mission/{mission_id}/update",
        json={
            "elapsed_seconds": 86400
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["mission_id"] == mission_id
    assert "mission" in data

    mission = data["mission"]

    assert mission["status"] == "running"
    assert mission["vessel_progress"] > 0
    assert mission["fuel_consumed_litres"] > 0
    assert mission["fuel_remaining_litres"] < 500000.0


def test_update_changes_position():
    mission_id, initial_data = create_started_mission()

    initial_position = initial_data["mission"]["vessel_position"]

    response = client.post(
        f"/api/mission/{mission_id}/update",
        json={
            "elapsed_seconds": 86400
        },
    )

    assert response.status_code == 200

    updated_position = response.json()["mission"]["vessel_position"]

    assert (
        updated_position["latitude"] != initial_position["latitude"]
        or updated_position["longitude"] != initial_position["longitude"]
    )


def test_update_before_start_returns_4xx():
    payload = {
        "station_id": "MAITRI",
        "vessel_id": "V001",
        "route_id": "R001",
        "cargo_weight_tonnes": 1500,
        "departure_datetime": "2026-12-01T00:00:00+00:00",
        "safety_buffer_days": 3,
    }

    create_response = client.post(
        "/api/mission",
        json=payload,
    )

    assert create_response.status_code == 200

    mission_id = create_response.json()["mission_id"]

    response = client.post(
        f"/api/mission/{mission_id}/update",
        json={
            "elapsed_seconds": 86400
        },
    )

    assert response.status_code in (400, 409, 422)