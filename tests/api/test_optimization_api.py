from fastapi.testclient import TestClient

from api.app import app


client = TestClient(app)


def optimization_payload():
    return {
        "station_id": "MAITRI",
        "resource_name": "diesel",
        "cargo_weight_tonnes": 1500,
        "current_datetime": "2026-10-01T00:00:00+00:00",
        "departure_dates": [
            "2026-11-15T00:00:00+00:00",
            "2026-12-01T00:00:00+00:00",
            "2026-12-15T00:00:00+00:00",
            "2027-01-01T00:00:00+00:00",
        ],
        "safety_buffer_days": 3,
        "max_alternatives": 3,
        "inventory": {
            "resource_name": "diesel",
            "current_quantity": 300000,
            "unit": "litres",
            "daily_consumption": 1800,
            "minimum_safety_threshold": 25000,
            "required_resupply_quantity": 60000,
        },
    }


def test_optimize_returns_success():
    response = client.post(
        "/api/optimize",
        json=optimization_payload(),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert "recommended_option" in data
    assert "alternatives" in data
    assert "infeasible_options" in data


def test_optimize_recommendation_is_feasible():
    response = client.post(
        "/api/optimize",
        json=optimization_payload(),
    )

    assert response.status_code == 200

    recommendation = response.json()["recommended_option"]

    assert recommendation["feasible"] is True
    assert recommendation["vessel_id"] == "V001"
    assert recommendation["route_id"] == "R001"
    assert recommendation["destination_station_id"] == "MAITRI"
    assert recommendation["cargo_weight_tonnes"] if "cargo_weight_tonnes" in recommendation else True


def test_optimize_has_valid_cost_and_fuel():
    response = client.post(
        "/api/optimize",
        json=optimization_payload(),
    )

    recommendation = response.json()["recommended_option"]

    assert recommendation["fuel_required_litres"] > 0
    assert recommendation["fuel_cost"] > 0
    assert recommendation["operating_cost"] > 0
    assert recommendation["total_cost"] > 0
    assert recommendation["cost_per_tonne"] > 0


def test_optimize_recommendation_arrives_before_safe_deadline():
    response = client.post(
        "/api/optimize",
        json=optimization_payload(),
    )

    recommendation = response.json()["recommended_option"]

    assert recommendation["arrival"] is not None
    assert recommendation["safety_margin_days"] > 0


def test_optimize_returns_alternatives():
    response = client.post(
        "/api/optimize",
        json=optimization_payload(),
    )

    data = response.json()

    assert len(data["alternatives"]) > 0

    for option in data["alternatives"]:
        assert option["feasible"] is True
        assert option["total_cost"] > 0


def test_optimize_reports_infeasible_options():
    response = client.post(
        "/api/optimize",
        json=optimization_payload(),
    )

    data = response.json()

    assert len(data["infeasible_options"]) > 0

    for option in data["infeasible_options"]:
        assert option["feasible"] is False
        assert option["rejection_reason"] is not None