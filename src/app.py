"""
High School Management System API

A FastAPI application for viewing and signing up for extracurricular activities
at Mergington High School.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles


DEFAULT_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"],
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"],
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"],
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"],
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"],
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"],
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"],
    },
}

ADMIN_TOKENS: set[str] = set()


def get_db_path(db_path: str | None = None) -> Path:
    if db_path:
        return Path(db_path)
    return Path(__file__).resolve().parent / "activities.db"


def _serialize_participants(participants: Any) -> str:
    if participants is None:
        return "[]"
    if isinstance(participants, str):
        try:
            parsed = json.loads(participants)
            return json.dumps(parsed)
        except json.JSONDecodeError:
            return json.dumps([participants])
    return json.dumps(participants)


def _parse_participants(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return [str(item) for item in value]
    except json.JSONDecodeError:
        pass
    return []


def init_db(db_path: str | None = None) -> Path:
    path = get_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            name TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            schedule TEXT NOT NULL,
            max_participants INTEGER NOT NULL,
            participants TEXT NOT NULL DEFAULT '[]'
        )
        """
    )

    existing = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    if existing == 0:
        for name, details in DEFAULT_ACTIVITIES.items():
            conn.execute(
                "INSERT INTO activities (name, description, schedule, max_participants, participants) VALUES (?, ?, ?, ?, ?)",
                (
                    name,
                    details["description"],
                    details["schedule"],
                    details["max_participants"],
                    _serialize_participants(details["participants"]),
                ),
            )
    conn.commit()
    conn.close()
    return path


def fetch_activities(db_path: str | None = None) -> dict[str, dict[str, Any]]:
    path = get_db_path(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT name, description, schedule, max_participants, participants FROM activities ORDER BY name"
    ).fetchall()
    conn.close()

    activities: dict[str, dict[str, Any]] = {}
    for row in rows:
        activities[row["name"]] = {
            "description": row["description"],
            "schedule": row["schedule"],
            "max_participants": row["max_participants"],
            "participants": _parse_participants(row["participants"]),
        }
    return activities


def fetch_activity(db_path: str | None, activity_name: str) -> dict[str, Any] | None:
    activities = fetch_activities(db_path)
    return activities.get(activity_name)


def persist_activity(db_path: str | None, activity: dict[str, Any]) -> None:
    path = get_db_path(db_path)
    conn = sqlite3.connect(path)
    conn.execute(
        """
        INSERT INTO activities (name, description, schedule, max_participants, participants)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            description = excluded.description,
            schedule = excluded.schedule,
            max_participants = excluded.max_participants,
            participants = excluded.participants
        """,
        (
            activity["name"],
            activity["description"],
            activity["schedule"],
            activity["max_participants"],
            _serialize_participants(activity.get("participants", [])),
        ),
    )
    conn.commit()
    conn.close()


def require_admin(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization token required")

    token = authorization.split(" ", 1)[1].strip()
    if token not in ADMIN_TOKENS:
        raise HTTPException(status_code=401, detail="Invalid or expired admin token")
    return token


def create_app(db_path: str | None = None) -> FastAPI:
    resolved_db_path = str(init_db(db_path))
    app = FastAPI(
        title="Mergington High School API",
        description="API for viewing and signing up for extracurricular activities",
    )

    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).resolve().parent / "static")),
        name="static",
    )

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/static/index.html")

    @app.get("/activities")
    def get_activities() -> dict[str, dict[str, Any]]:
        return fetch_activities(resolved_db_path)

    @app.post("/activities/{activity_name}/signup")
    def signup_for_activity(activity_name: str, email: str) -> dict[str, str]:
        activities = fetch_activities(resolved_db_path)
        if activity_name not in activities:
            raise HTTPException(status_code=404, detail="Activity not found")

        activity = activities[activity_name]
        participants = activity["participants"]

        if email in participants:
            raise HTTPException(status_code=400, detail="Student is already signed up")

        if len(participants) >= activity["max_participants"]:
            raise HTTPException(status_code=400, detail="Activity is full")

        participants.append(email)
        activity["participants"] = participants
        activity["name"] = activity_name
        persist_activity(resolved_db_path, activity)
        return {"message": f"Signed up {email} for {activity_name}"}

    @app.delete("/activities/{activity_name}/unregister")
    def unregister_from_activity(activity_name: str, email: str) -> dict[str, str]:
        activities = fetch_activities(resolved_db_path)
        if activity_name not in activities:
            raise HTTPException(status_code=404, detail="Activity not found")

        activity = activities[activity_name]
        participants = activity["participants"]
        if email not in participants:
            raise HTTPException(status_code=400, detail="Student is not signed up for this activity")

        participants.remove(email)
        activity["participants"] = participants
        activity["name"] = activity_name
        persist_activity(resolved_db_path, activity)
        return {"message": f"Unregistered {email} from {activity_name}"}

    @app.post("/admin/login")
    def admin_login(payload: dict[str, str]) -> dict[str, str]:
        username = (payload.get("username") or "").strip()
        password = (payload.get("password") or "").strip()
        if username != "admin" or password != "admin123":
            raise HTTPException(status_code=401, detail="Invalid admin credentials")

        token = secrets.token_urlsafe(24)
        ADMIN_TOKENS.add(token)
        return {"token": token}

    @app.get("/admin/activities")
    def admin_get_activities(authorization: str | None = Header(default=None)) -> dict[str, dict[str, Any]]:
        require_admin(authorization)
        return fetch_activities(resolved_db_path)

    @app.get("/admin/dashboard")
    def admin_dashboard(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        require_admin(authorization)

        activities = fetch_activities(resolved_db_path)
        student_emails = set()
        activity_list: list[dict[str, Any]] = []
        for name, details in activities.items():
            participants = details.get("participants", [])
            for email in participants:
                student_emails.add(email)

            activity_list.append(
                {
                    "name": name,
                    "description": details.get("description", ""),
                    "schedule": details.get("schedule", ""),
                    "max_participants": details.get("max_participants", 0),
                    "participants_count": len(participants),
                }
            )

        recent_activity = sorted(
            activity_list,
            key=lambda item: item["participants_count"],
            reverse=True,
        )[:5]

        return {
            "total_activities": len(activity_list),
            "total_students": len(student_emails),
            "total_capacity": sum(item["max_participants"] for item in activity_list),
            "activities": activity_list,
            "recent_activity": recent_activity,
        }

    @app.post("/admin/activities")
    def admin_create_activity(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_admin(authorization)

        name = str(payload.get("name", "")).strip()
        if not name:
            raise HTTPException(status_code=400, detail="Activity name is required")

        activity_payload = {
            "name": name,
            "description": str(payload.get("description", "")),
            "schedule": str(payload.get("schedule", "")),
            "max_participants": int(payload.get("max_participants", 0) or 0),
            "participants": payload.get("participants", []),
        }

        if activity_payload["max_participants"] <= 0:
            raise HTTPException(status_code=400, detail="max_participants must be greater than zero")

        if len(activity_payload["participants"]) > activity_payload["max_participants"]:
            raise HTTPException(status_code=400, detail="Participants cannot exceed max capacity")

        persist_activity(resolved_db_path, activity_payload)
        return {"message": f"Created activity {name}", "activity": fetch_activity(resolved_db_path, name)}

    return app


app = create_app()
