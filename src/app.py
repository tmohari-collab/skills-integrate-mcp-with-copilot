"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import logging
import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from src.teacher_auth import (
    create_session_token,
    load_teacher_credentials,
    password_matches,
    read_session_token,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(current_dir, "static")),
          name="static")

TEACHERS_FILE = current_dir / "teachers.json"
SESSION_COOKIE = "teacher_session"
SESSION_MAX_AGE = 60 * 60
SESSION_SECRET = os.environ.get("SESSION_SECRET")
if SESSION_SECRET is None:
    SESSION_SECRET_BYTES = secrets.token_bytes(32)
    logger.warning(
        "SESSION_SECRET is not set; teacher sessions will not persist across "
        "server restarts or work across multiple workers."
    )
else:
    SESSION_SECRET_BYTES = SESSION_SECRET.encode("utf-8")
    if len(SESSION_SECRET_BYTES) < 32:
        raise ValueError("SESSION_SECRET must contain at least 32 bytes")

COOKIE_SECURE_VALUE = os.environ.get("COOKIE_SECURE", "false").lower()
if COOKIE_SECURE_VALUE not in {"true", "false"}:
    raise ValueError("COOKIE_SECURE must be either 'true' or 'false'")
COOKIE_SECURE = COOKIE_SECURE_VALUE == "true"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=1024)


def require_teacher(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE)
    username = read_session_token(token, SESSION_SECRET_BYTES)
    if username is None:
        raise HTTPException(status_code=401, detail="Teacher login required")
    return username


@app.post("/auth/login")
def login(credentials: LoginRequest, response: Response):
    """Authenticate a teacher and issue a signed, HTTP-only session cookie."""
    try:
        teachers = load_teacher_credentials(TEACHERS_FILE)
    except (OSError, ValueError) as error:
        logger.exception("Could not load teacher credentials")
        raise HTTPException(
            status_code=500,
            detail="Teacher credential configuration is unavailable",
        ) from error

    username = credentials.username.strip()
    teacher = next(
        (entry for entry in teachers if entry["username"] == username),
        None,
    )
    if not password_matches(credentials.password, teacher):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_session_token(username, SESSION_SECRET_BYTES, SESSION_MAX_AGE),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return {"authenticated": True, "username": username}


@app.get("/auth/session")
def get_session(request: Request):
    """Return the current teacher-session status without exposing credentials."""
    username = read_session_token(
        request.cookies.get(SESSION_COOKIE),
        SESSION_SECRET_BYTES,
    )
    return {"authenticated": username is not None, "username": username}


@app.post("/auth/logout")
def logout(response: Response):
    """Clear the teacher session cookie."""
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return {"authenticated": False}

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post(
    "/activities/{activity_name}/signup",
    dependencies=[Depends(require_teacher)],
)
def signup_for_activity(
    activity_name: str,
    email: str,
):
    """Register a student for an activity (teachers only)."""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete(
    "/activities/{activity_name}/unregister",
    dependencies=[Depends(require_teacher)],
)
def unregister_from_activity(
    activity_name: str,
    email: str,
):
    """Unregister a student from an activity (teachers only)."""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
