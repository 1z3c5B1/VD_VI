import sqlite3
import hashlib
import secrets
import json
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "users.db"


def _get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, pass_hash TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS sessions (token TEXT UNIQUE, user_id INTEGER)")
    conn.commit()
    return conn


def register(username: str, password: str) -> dict:
    conn = _get_db()
    try:
        pass_hash = hashlib.sha256(password.encode()).hexdigest()
        conn.execute("INSERT INTO users (username, pass_hash) VALUES (?, ?)", (username, pass_hash))
        conn.commit()
        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        token = secrets.token_hex(16)
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
        conn.commit()
        return {"success": True, "token": token, "username": username}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Имя уже занято"}
    finally:
        conn.close()


def login(username: str, password: str) -> dict:
    conn = _get_db()
    try:
        pass_hash = hashlib.sha256(password.encode()).hexdigest()
        user = conn.execute("SELECT id FROM users WHERE username = ? AND pass_hash = ?", (username, pass_hash)).fetchone()
        if not user:
            return {"success": False, "error": "Неверное имя или пароль"}
        token = secrets.token_hex(16)
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
        conn.commit()
        return {"success": True, "token": token, "username": username}
    finally:
        conn.close()


def verify_token(token: str) -> dict:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT u.username, u.id FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.token = ?",
            (token,),
        ).fetchone()
        if row:
            return {"valid": True, "username": row["username"], "user_id": row["id"]}
        return {"valid": False}
    finally:
        conn.close()
