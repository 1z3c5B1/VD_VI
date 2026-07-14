import sqlite3
import hashlib
import secrets
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "users.db"

ADMIN_PASSWORD = "Vadim20150011"
FREE_COINS = 10


def _get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            pass_hash TEXT,
            coins INTEGER DEFAULT 10,
            pro INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT UNIQUE,
            user_id INTEGER,
            is_admin INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT UNIQUE,
            type TEXT,
            value INTEGER DEFAULT 0,
            used_by INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    for col in ["coins", "pro", "banned"]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT {0 if col != 'coins' else FREE_COINS}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return conn


def register(username: str, password: str) -> dict:
    conn = _get_db()
    try:
        pass_hash = hashlib.sha256(password.encode()).hexdigest()
        conn.execute(
            "INSERT INTO users (username, pass_hash, coins) VALUES (?, ?, ?)",
            (username, pass_hash, FREE_COINS),
        )
        conn.commit()
        user = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        token = secrets.token_hex(16)
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
        conn.commit()
        return {"success": True, "token": token, "username": username, "coins": FREE_COINS, "pro": 0}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Имя уже занято"}
    finally:
        conn.close()


def login(username: str, password: str) -> dict:
    conn = _get_db()
    try:
        pass_hash = hashlib.sha256(password.encode()).hexdigest()
        user = conn.execute(
            "SELECT id, banned, coins, pro FROM users WHERE username = ? AND pass_hash = ?",
            (username, pass_hash),
        ).fetchone()
        if not user:
            return {"success": False, "error": "Неверное имя или пароль"}
        if user["banned"]:
            return {"success": False, "error": "Аккаунт заблокирован"}
        token = secrets.token_hex(16)
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
        conn.commit()
        return {
            "success": True,
            "token": token,
            "username": username,
            "coins": user["coins"],
            "pro": user["pro"],
        }
    finally:
        conn.close()


def verify_token(token: str) -> dict:
    conn = _get_db()
    try:
        row = conn.execute(
            "SELECT u.username, u.id, u.coins, u.pro, u.banned, s.is_admin "
            "FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.token = ?",
            (token,),
        ).fetchone()
        if row:
            if row["banned"]:
                return {"valid": False, "error": "Аккаунт заблокирован"}
            return {
                "valid": True,
                "username": row["username"],
                "user_id": row["id"],
                "coins": row["coins"],
                "pro": row["pro"],
                "is_admin": bool(row["is_admin"]),
            }
        return {"valid": False}
    finally:
        conn.close()


def admin_login(token: str, password: str) -> dict:
    if password != ADMIN_PASSWORD:
        return {"success": False, "error": "Неверный пароль админки"}
    conn = _get_db()
    try:
        conn.execute("UPDATE sessions SET is_admin = 1 WHERE token = ?", (token,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def deduct_coins(user_id: int, amount: int) -> dict:
    conn = _get_db()
    try:
        user = conn.execute("SELECT coins, pro FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return {"success": False, "error": "User not found"}
        if user["pro"]:
            return {"success": True, "coins": user["coins"] or 0, "unlimited": True}
        current = user["coins"] if user["coins"] is not None else FREE_COINS
        if current < amount:
            return {"success": False, "error": f"Нужно {amount} VD Coins, у тебя {current}. Пополни или купи PRO."}
        conn.execute("UPDATE users SET coins = ? WHERE id = ?", (current - amount, user_id))
        conn.commit()
        new_coins = conn.execute("SELECT coins FROM users WHERE id = ?", (user_id,)).fetchone()["coins"]
        return {"success": True, "coins": new_coins}
    finally:
        conn.close()


def use_promo_code(code: str, user_id: int) -> dict:
    conn = _get_db()
    try:
        promo = conn.execute("SELECT * FROM promo_codes WHERE code = ?", (code,)).fetchone()
        if not promo:
            return {"success": False, "error": "Промокод не найден"}
        if promo["used_by"] and promo["used_by"] != 0:
            return {"success": False, "error": "Промокод уже использован"}

        if promo["type"] == "coins":
            conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (promo["value"], user_id))
        elif promo["type"] == "pro":
            conn.execute("UPDATE users SET pro = 1 WHERE id = ?", (user_id,))
        elif promo["type"] == "ban":
            conn.execute("UPDATE users SET banned = 1 WHERE id = ?", (user_id,))
            conn.commit()
            return {"success": False, "error": "Аккаунт заблокирован"}

        conn.execute("UPDATE promo_codes SET used_by = ? WHERE code = ?", (user_id, code))
        conn.commit()
        user = conn.execute("SELECT coins, pro FROM users WHERE id = ?", (user_id,)).fetchone()
        return {"success": True, "coins": user["coins"], "pro": user["pro"]}
    finally:
        conn.close()


def is_admin(token: str) -> bool:
    user = verify_token(token)
    return user.get("valid") and user.get("is_admin")


def admin_get_users(token: str) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    try:
        rows = conn.execute("SELECT id, username, coins, pro, banned FROM users").fetchall()
        return {"success": True, "users": [dict(r) for r in rows]}
    finally:
        conn.close()


def admin_get_promos(token: str) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    try:
        rows = conn.execute("SELECT * FROM promo_codes ORDER BY rowid DESC").fetchall()
        return {"success": True, "promos": [dict(r) for r in rows]}
    finally:
        conn.close()


def admin_create_promo(token: str, code: str, promo_type: str, value: int = 0) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO promo_codes (code, type, value, created_at) VALUES (?, ?, ?, ?)",
            (code.upper(), promo_type, value, datetime.now().isoformat()),
        )
        conn.commit()
        return {"success": True}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Промокод уже существует"}
    finally:
        conn.close()


def admin_delete_promo(token: str, code: str) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    try:
        conn.execute("DELETE FROM promo_codes WHERE code = ?", (code,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def admin_ban_user(token: str, user_id: int) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    try:
        conn.execute("UPDATE users SET banned = 1 WHERE id = ?", (user_id,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def admin_unban_user(token: str, user_id: int) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    try:
        conn.execute("UPDATE users SET banned = 0 WHERE id = ?", (user_id,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def admin_set_coins(token: str, user_id: int, coins: int) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    try:
        conn.execute("UPDATE users SET coins = ? WHERE id = ?", (coins, user_id))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def admin_toggle_pro(token: str, user_id: int) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    try:
        user = conn.execute("SELECT pro FROM users WHERE id = ?", (user_id,)).fetchone()
        new_val = 0 if user["pro"] else 1
        conn.execute("UPDATE users SET pro = ? WHERE id = ?", (new_val, user_id))
        conn.commit()
        return {"success": True, "pro": new_val}
    finally:
        conn.close()


def admin_delete_user(token: str, user_id: int) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    try:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()
