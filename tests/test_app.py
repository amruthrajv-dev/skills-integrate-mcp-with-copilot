from fastapi.testclient import TestClient

from src.app import create_app


def test_admin_login_and_activity_creation(tmp_path):
    app = create_app(db_path=str(tmp_path / "activities.db"))
    client = TestClient(app)

    login_response = client.post(
        "/admin/login",
        json={"username": "admin", "password": "admin123"},
    )

    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["token"]

    create_response = client.post(
        "/admin/activities",
        json={
            "name": "Robotics Club",
            "description": "Build robots and compete in the regional robotics challenge.",
            "schedule": "Wednesdays, 3:30 PM - 5:00 PM",
            "max_participants": 18,
            "participants": ["teacher@mergington.edu"],
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert create_response.status_code == 200, create_response.text
    activities = client.get("/activities").json()
    assert "Robotics Club" in activities
    assert activities["Robotics Club"]["max_participants"] == 18


def test_student_signup_persists(tmp_path):
    app = create_app(db_path=str(tmp_path / "activities.db"))
    client = TestClient(app)

    signup_response = client.post(
        "/activities/Chess Club/signup?email=student@mergington.edu"
    )

    assert signup_response.status_code == 200, signup_response.text

    activities = client.get("/activities").json()
    assert "student@mergington.edu" in activities["Chess Club"]["participants"]


def test_admin_summary_endpoint(tmp_path):
    app = create_app(db_path=str(tmp_path / "activities.db"))
    client = TestClient(app)

    login_response = client.post(
        "/admin/login",
        json={"username": "admin", "password": "admin123"},
    )
    token = login_response.json()["token"]

    summary_response = client.get(
        "/admin/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert summary_response.status_code == 200, summary_response.text
    payload = summary_response.json()
    assert payload["total_activities"] >= 1
    assert payload["total_students"] >= 1
    assert "activities" in payload
