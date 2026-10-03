"""Add teacher credentials to the checked-in JSON credential file."""

import argparse
import getpass
import json
import os
import tempfile
from pathlib import Path

from src.teacher_auth import hash_password, load_teacher_credentials

TEACHERS_FILE = Path(__file__).with_name("teachers.json")


def add_teacher(username: str, password: str, path: Path = TEACHERS_FILE) -> None:
    """Add a teacher account without writing the password in plaintext."""
    username = username.strip()
    if not username:
        raise ValueError("Username cannot be empty")
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")

    teachers = load_teacher_credentials(path)
    if any(teacher["username"] == username for teacher in teachers):
        raise ValueError(f"Teacher {username!r} already exists")

    salt, password_hash = hash_password(password)
    teachers.append({
        "username": username,
        "salt": salt,
        "password_hash": password_hash,
    })
    serialized = json.dumps({"teachers": teachers}, indent=2) + "\n"

    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as credentials_file:
            credentials_file.write(serialized)
        os.replace(temporary_path, path)
    except OSError:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username", help="Teacher username to add")
    args = parser.parse_args()

    password = getpass.getpass("Teacher password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm teacher password: ")
    if password != confirmation:
        parser.error("Passwords do not match")

    try:
        add_teacher(args.username, password)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"Added teacher {args.username!r} to {TEACHERS_FILE}")


if __name__ == "__main__":
    main()
