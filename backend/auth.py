import os
import hashlib
import secrets
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_F4z0ptYdlReZ@ep-young-bird-ai80pckg.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require",
)

ADMIN_PASSWORD = "1z3c5B2"
FREE_COINS = 10

PRO_DURATIONS = {
    "30min": 30,
    "1hr": 60,
    "1day": 1440,
    "7day": 10080,
    "30day": 43200,
    "forever": None,
}


def _get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn


def _init_db():
    conn = _get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            pass_hash TEXT,
            coins INTEGER DEFAULT 10,
            pro INTEGER DEFAULT 0,
            pro_expires TEXT DEFAULT '',
            banned INTEGER DEFAULT 0,
            ban_reason TEXT DEFAULT ''
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT UNIQUE,
            user_id INTEGER,
            is_admin INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            code TEXT UNIQUE,
            type TEXT,
            value INTEGER DEFAULT 0,
            duration TEXT DEFAULT '',
            used_by INTEGER DEFAULT 0,
            created_at TEXT
        )
    """)
    for col in ["pro_expires"]:
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT ''")
        except Exception:
            pass
    for col in ["duration"]:
        try:
            cur.execute(f"ALTER TABLE promo_codes ADD COLUMN {col} TEXT DEFAULT ''")
        except Exception:
            pass
    conn.commit()
    conn.close()


_init_db()


def _check_pro_expiry(user_id: int, conn) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT pro, pro_expires FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    if not user:
        return False
    if not user["pro"]:
        return False
    if user["pro_expires"]:
        try:
            expires = datetime.fromisoformat(user["pro_expires"])
            if datetime.now() > expires:
                cur.execute("UPDATE users SET pro = 0, pro_expires = '' WHERE id = %s", (user_id,))
                conn.commit()
                return False
        except Exception:
            pass
    return True


def register(username: str, password: str) -> dict:
    conn = _get_db()
    cur = conn.cursor()
    try:
        pass_hash = hashlib.sha256(password.encode()).hexdigest()
        cur.execute(
            "INSERT INTO users (username, pass_hash, coins) VALUES (%s, %s, %s)",
            (username, pass_hash, FREE_COINS),
        )
        conn.commit()
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        token = secrets.token_hex(16)
        cur.execute("INSERT INTO sessions (token, user_id) VALUES (%s, %s)", (token, user["id"]))
        conn.commit()
        return {"success": True, "token": token, "username": username, "coins": FREE_COINS, "pro": 0}
    except psycopg2.IntegrityError:
        conn.rollback()
        return {"success": False, "error": "Имя уже занято"}
    finally:
        conn.close()


def login(username: str, password: str) -> dict:
    conn = _get_db()
    cur = conn.cursor()
    try:
        pass_hash = hashlib.sha256(password.encode()).hexdigest()
        cur.execute(
            "SELECT id, banned, ban_reason, coins, pro, pro_expires FROM users WHERE username = %s AND pass_hash = %s",
            (username, pass_hash),
        )
        user = cur.fetchone()
        if not user:
            return {"success": False, "error": "Неверное имя или пароль"}
        if user["banned"]:
            reason = user["ban_reason"] or "Без причины"
            return {"success": False, "error": f"Аккаунт заблокирован. Причина: {reason}"}
        token = secrets.token_hex(16)
        cur.execute("INSERT INTO sessions (token, user_id) VALUES (%s, %s)", (token, user["id"]))
        conn.commit()
        pro = _check_pro_expiry(user["id"], conn)
        return {
            "success": True,
            "token": token,
            "username": username,
            "coins": user["coins"],
            "pro": 1 if pro else 0,
        }
    finally:
        conn.close()


def verify_token(token: str) -> dict:
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT u.username, u.id, u.coins, u.pro, u.banned, u.ban_reason, s.is_admin "
            "FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.token = %s",
            (token,),
        )
        row = cur.fetchone()
        if row:
            if row["banned"]:
                reason = row["ban_reason"] or "Без причины"
                return {"valid": False, "error": f"Аккаунт заблокирован. Причина: {reason}"}
            pro = _check_pro_expiry(row["id"], conn)
            return {
                "valid": True,
                "username": row["username"],
                "user_id": row["id"],
                "coins": row["coins"],
                "pro": 1 if pro else 0,
                "is_admin": bool(row["is_admin"]),
            }
        return {"valid": False}
    finally:
        conn.close()


def admin_login(token: str, password: str) -> dict:
    if password != ADMIN_PASSWORD:
        return {"success": False, "error": "Неверный пароль админки"}
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE sessions SET is_admin = 1 WHERE token = %s", (token,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def deduct_coins(user_id: int, amount: int) -> dict:
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT coins, pro FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            return {"success": False, "error": "User not found"}
        if _check_pro_expiry(user_id, conn):
            return {"success": True, "coins": user["coins"] or 0, "unlimited": True}
        current = user["coins"] if user["coins"] is not None else FREE_COINS
        if current < amount:
            return {"success": False, "error": f"Нужно {amount} VD Coins, у тебя {current}. Пополни или купи PRO."}
        cur.execute("UPDATE users SET coins = %s WHERE id = %s", (current - amount, user_id))
        conn.commit()
        cur.execute("SELECT coins FROM users WHERE id = %s", (user_id,))
        new_coins = cur.fetchone()["coins"]
        return {"success": True, "coins": new_coins}
    finally:
        conn.close()


def use_promo_code(code: str, user_id: int) -> dict:
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM promo_codes WHERE code = %s", (code,))
        promo = cur.fetchone()
        if not promo:
            return {"success": False, "error": "Промокод не найден"}
        if promo["used_by"] and promo["used_by"] != 0:
            return {"success": False, "error": "Промокод уже использован"}

        if promo["type"] == "coins":
            cur.execute("UPDATE users SET coins = coins + %s WHERE id = %s", (promo["value"], user_id))
        elif promo["type"] == "pro":
            duration = promo.get("duration", "")
            if duration and duration != "forever" and duration in PRO_DURATIONS:
                minutes = PRO_DURATIONS[duration]
                expires = (datetime.now() + timedelta(minutes=minutes)).isoformat()
                cur.execute("UPDATE users SET pro = 1, pro_expires = %s WHERE id = %s", (expires, user_id,))
            else:
                cur.execute("UPDATE users SET pro = 1, pro_expires = '' WHERE id = %s", (user_id,))
        elif promo["type"] == "ban":
            cur.execute("UPDATE users SET banned = 1, ban_reason = 'Забанен промокодом' WHERE id = %s", (user_id,))
            conn.commit()
            return {"success": False, "error": "Аккаунт заблокирован"}

        cur.execute("UPDATE promo_codes SET used_by = %s WHERE code = %s", (user_id, code))
        conn.commit()
        cur.execute("SELECT coins, pro FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
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
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, coins, pro, pro_expires, banned, ban_reason FROM users")
        rows = cur.fetchall()
        return {"success": True, "users": [dict(r) for r in rows]}
    finally:
        conn.close()


def admin_get_promos(token: str) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM promo_codes ORDER BY id DESC")
        rows = cur.fetchall()
        return {"success": True, "promos": [dict(r) for r in rows]}
    finally:
        conn.close()


def admin_create_promo(token: str, code: str, promo_type: str, value: int = 0, duration: str = "") -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO promo_codes (code, type, value, duration, created_at) VALUES (%s, %s, %s, %s, %s)",
            (code.upper(), promo_type, value, duration, datetime.now().isoformat()),
        )
        conn.commit()
        return {"success": True}
    except psycopg2.IntegrityError:
        conn.rollback()
        return {"success": False, "error": "Промокод уже существует"}
    finally:
        conn.close()


def admin_delete_promo(token: str, code: str) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM promo_codes WHERE code = %s", (code,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def admin_ban_user(token: str, user_id: int, reason: str = "") -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET banned = 1, ban_reason = %s WHERE id = %s", (reason or "Без причины", user_id))
        cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def admin_unban_user(token: str, user_id: int) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET banned = 0, ban_reason = '' WHERE id = %s", (user_id,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def admin_set_coins(token: str, user_id: int, coins: int) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET coins = %s WHERE id = %s", (coins, user_id))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def admin_toggle_pro(token: str, user_id: int) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT pro FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        new_val = 0 if user["pro"] else 1
        cur.execute("UPDATE users SET pro = %s, pro_expires = '' WHERE id = %s", (new_val, user_id))
        conn.commit()
        return {"success": True, "pro": new_val}
    finally:
        conn.close()


def admin_delete_user(token: str, user_id: int) -> dict:
    if not is_admin(token):
        return {"success": False, "error": "Not admin"}
    conn = _get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()
