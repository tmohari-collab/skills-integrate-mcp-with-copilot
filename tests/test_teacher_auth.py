import json
import tempfile
import unittest
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException, Response
from starlette.requests import Request

from src import app as app_module
from src.app import LoginRequest
from src.manage_teachers import add_teacher
from src.teacher_auth import (
    create_session_token,
    load_teacher_credentials,
    password_matches,
    read_session_token,
)


class TeacherCredentialTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.credentials_path = Path(self.temp_dir.name) / "teachers.json"
        self.credentials_path.write_text('{"teachers": []}\n', encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_teacher_stores_password_hash_not_plaintext(self):
        password = "a long teacher passphrase"
        add_teacher("teacher-a", password, self.credentials_path)

        content = self.credentials_path.read_text(encoding="utf-8")
        self.assertNotIn(password, content)
        teacher = load_teacher_credentials(self.credentials_path)[0]
        self.assertEqual(teacher["username"], "teacher-a")
        self.assertTrue(password_matches(password, teacher))
        self.assertFalse(password_matches("incorrect", teacher))

    def test_add_teacher_rejects_duplicate_username(self):
        add_teacher("teacher-a", "a long teacher passphrase", self.credentials_path)
        with self.assertRaisesRegex(ValueError, "already exists"):
            add_teacher(
                "teacher-a",
                "another long teacher passphrase",
                self.credentials_path,
            )

    def test_invalid_credential_file_is_rejected(self):
        self.credentials_path.write_text(
            json.dumps({"teachers": [{"username": "teacher-a"}]}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "incomplete"):
            load_teacher_credentials(self.credentials_path)

    def test_unknown_username_does_not_authenticate(self):
        self.assertFalse(password_matches("some password", None))


class TeacherSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.credentials_path = Path(self.temp_dir.name) / "teachers.json"
        self.credentials_path.write_text('{"teachers": []}\n', encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_session_token_accepts_valid_session_and_rejects_tampering(self):
        secret = b"x" * 32
        token = create_session_token("teacher-a", secret, 60, now=100)

        self.assertEqual(read_session_token(token, secret, now=120), "teacher-a")
        self.assertIsNone(read_session_token(token + "x", secret, now=120))
        self.assertIsNone(read_session_token(token, secret, now=160))
        self.assertIsNone(read_session_token(None, secret, now=120))

    def test_login_sets_http_only_signed_session_cookie(self):
        password = "a long teacher passphrase"
        add_teacher("teacher-a", password, self.credentials_path)
        secret = b"x" * 32
        with (
            patch.object(app_module, "TEACHERS_FILE", self.credentials_path),
            patch.object(app_module, "SESSION_SECRET_BYTES", secret),
        ):
            response = Response()
            result = app_module.login(
                LoginRequest(username="teacher-a", password=password),
                response,
            )

        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        session_cookie = cookie[app_module.SESSION_COOKIE]
        self.assertEqual(result, {"authenticated": True, "username": "teacher-a"})
        self.assertTrue(session_cookie["httponly"])
        self.assertEqual(session_cookie["samesite"], "strict")
        self.assertEqual(
            read_session_token(session_cookie.value, secret),
            "teacher-a",
        )

    def test_login_rejects_invalid_password(self):
        with patch.object(app_module, "TEACHERS_FILE", self.credentials_path):
            with self.assertRaises(HTTPException) as raised:
                app_module.login(
                    LoginRequest(username="unknown", password="wrong password"),
                    Response(),
                )
        self.assertEqual(raised.exception.status_code, 401)

    def test_protected_routes_require_teacher_dependency(self):
        protected_paths = {
            "/activities/{activity_name}/signup",
            "/activities/{activity_name}/unregister",
        }
        routes = {
            route.path: route
            for route in app_module.app.routes
            if route.path in protected_paths
        }
        self.assertEqual(set(routes), protected_paths)
        for route in routes.values():
            self.assertTrue(
                any(
                    dependency.call is app_module.require_teacher
                    for dependency in route.dependant.dependencies
                )
            )

    def test_teacher_dependency_rejects_missing_session(self):
        request = Request({
            "type": "http",
            "method": "POST",
            "path": "/activities/Chess%20Club/signup",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        })
        with self.assertRaises(HTTPException) as raised:
            app_module.require_teacher(request)
        self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
