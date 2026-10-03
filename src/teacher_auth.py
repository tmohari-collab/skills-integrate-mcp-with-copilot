"""Credential and signed-session helpers for teacher authentication."""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from typing import Any

PASSWORD_ITERATIONS = 600_000
PASSWORD_SALT_BYTES = 16
PASSWORD_HASH_BYTES = 32
_DUMMY_SALT = bytes.fromhex("b8c4d931e56a071f2d904a63c7e18f20")
_DUMMY_PASSWORD = b"teacher-account-not-found"
_DUMMY_HASH = hashlib.pbkdf2_hmac(
    "sha256",
    _DUMMY_PASSWORD,
    _DUMMY_SALT,
    PASSWORD_ITERATIONS,
    dklen=PASSWORD_HASH_BYTES,
)


def hash_password(password: str) -> tuple[str, str]:
    """Return a random salt and PBKDF2-SHA256 digest, both hex-encoded."""
    salt = secrets.token_bytes(PASSWORD_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
        dklen=PASSWORD_HASH_BYTES,
    )
    return salt.hex(), digest.hex()


def load_teacher_credentials(path: Path) -> list[dict[str, str]]:
    """Load and validate the checked-in teacher credential file."""
    contents = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(contents, dict) or not isinstance(
        contents.get("teachers"), list
    ):
        raise ValueError("Teacher credential file must contain a teachers list")

    teachers: list[dict[str, str]] = []
    usernames: set[str] = set()
    for entry in contents["teachers"]:
        if not isinstance(entry, dict):
            raise ValueError("Teacher credential entries must be objects")
        username = entry.get("username")
        salt_hex = entry.get("salt")
        password_hash_hex = entry.get("password_hash")
        if not all(isinstance(value, str) and value for value in
                   (username, salt_hex, password_hash_hex)):
            raise ValueError("Teacher credential entries are incomplete")
        if username in usernames:
            raise ValueError("Teacher usernames must be unique")
        try:
            salt = bytes.fromhex(salt_hex)
            password_hash = bytes.fromhex(password_hash_hex)
        except ValueError as error:
            raise ValueError("Teacher credential values must be valid hex") from error
        if len(salt) != PASSWORD_SALT_BYTES:
            raise ValueError("Teacher credential salt has an invalid length")
        if len(password_hash) != PASSWORD_HASH_BYTES:
            raise ValueError("Teacher password hash has an invalid length")

        usernames.add(username)
        teachers.append({
            "username": username,
            "salt": salt_hex,
            "password_hash": password_hash_hex,
        })
    return teachers


def password_matches(password: str, teacher: dict[str, str] | None) -> bool:
    """Check a password while doing comparable work for unknown usernames."""
    if teacher is None:
        salt = _DUMMY_SALT
        expected = _DUMMY_HASH
    else:
        salt = bytes.fromhex(teacher["salt"])
        expected = bytes.fromhex(teacher["password_hash"])

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
        dklen=PASSWORD_HASH_BYTES,
    )
    matches = hmac.compare_digest(actual, expected)
    return teacher is not None and matches


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_session_token(
    username: str,
    secret: bytes,
    max_age: int,
    *,
    now: int | None = None,
) -> str:
    """Create an expiring HMAC-signed session token."""
    issued_at = int(time.time()) if now is None else now
    payload = json.dumps(
        {"username": username, "expires": issued_at + max_age},
        separators=(",", ":"),
    ).encode("utf-8")
    encoded_payload = _encode(payload)
    signature = hmac.new(
        secret,
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_encode(signature)}"


def read_session_token(
    token: str | None,
    secret: bytes,
    *,
    now: int | None = None,
) -> str | None:
    """Return the signed-in username, or None for an invalid/expired token."""
    if not token:
        return None
    try:
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
        signature = _decode(encoded_signature)
        expected_signature = hmac.new(
            secret,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected_signature):
            return None

        payload: Any = json.loads(_decode(encoded_payload))
        if not isinstance(payload, dict):
            return None
        username = payload.get("username")
        expires = payload.get("expires")
        if (
            not isinstance(username, str)
            or not username
            or not isinstance(expires, int)
        ):
            return None
        current_time = int(time.time()) if now is None else now
        if expires <= current_time:
            return None
        return username
    except (ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError):
        return None
