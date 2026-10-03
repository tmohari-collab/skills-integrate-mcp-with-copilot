# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Teacher sign-in to register or unregister students
- Public viewing of activity participants

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Add each teacher account. The password is entered interactively and only its
   PBKDF2-SHA256 hash is written to `src/teachers.json`. Commit and deploy that
   updated file with the backend; never store a plaintext password in it.

   ```
   python -m src.manage_teachers teacher-username
   ```

3. Set a persistent session-signing key of at least 32 bytes. For example:

   ```
   export SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
   ```

   For HTTPS deployments, also set `COOKIE_SECURE=true`. Do not commit the
   session key. When `SESSION_SECRET` is unset, the app uses a temporary key
   and logs a warning; sessions then do not survive restarts or work between
   multiple workers.

4. Run the application:

   ```
   uvicorn src.app:app --reload
   ```

5. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc
   - Activities page: http://localhost:8000/

Teachers can manage student registrations after signing in through the account
icon. Everyone can still view the activity lists and registered participants.
The `/activities/{activity_name}/signup` and `/activities/{activity_name}/unregister`
endpoints require a valid teacher session.

Run the authentication tests with:

```
python -m unittest discover -s tests -v
```

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/auth/login`                                                     | Sign in with a teacher username and password                        |
| GET    | `/auth/session`                                                   | Check the current teacher session                                   |
| POST   | `/auth/logout`                                                    | Sign out the current teacher                                        |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Register a student (teacher session required)                       |
| DELETE | `/activities/{activity_name}/unregister?email=student@mergington.edu` | Unregister a student (teacher session required)                  |

## Data Model

The application uses a simple data model with meaningful identifiers:

1. **Activities** - Uses activity name as identifier:

   - Description
   - Schedule
   - Maximum number of participants allowed
   - List of student emails who are signed up

2. **Students** - Uses email as identifier:
   - Name
   - Grade level

All data is stored in memory, which means data will be reset when the server restarts.
