# -*- coding: utf-8 -*-
"""
مدیریت دیتابیس SQLite.
رایگان، بدون نیاز به نصب سرور جدا، و کاملا مناسب سرور شما.
"""
import sqlite3
import threading
from datetime import datetime
import config

# قفل برای جلوگیری از تداخل دسترسی همزمان ربات و پنل
_lock = threading.Lock()


def get_conn():
    conn = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")  # امکان خواندن/نوشتن همزمان
    return conn


def init_db():
    """ساخت جدول‌ها در اولین اجرا."""
    with _lock, get_conn() as conn:
        c = conn.cursor()

        # جدول کاربران
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id        INTEGER PRIMARY KEY,
            full_name      TEXT,
            phone          TEXT,
            points         INTEGER DEFAULT 0,
            referral_code  TEXT UNIQUE,
            referred_by    INTEGER,
            joined_at      TEXT,
            state          TEXT DEFAULT 'new'
        )""")

        # جدول مسابقه‌ها
        c.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            team1         TEXT NOT NULL,
            team2         TEXT NOT NULL,
            start_time    TEXT NOT NULL,   -- شروع پاسخ‌دهی (yyyy-mm-dd HH:MM)
            close_time    TEXT NOT NULL,   -- پایان پاسخ‌دهی
            result        TEXT,            -- win / lose  (نتیجه نهایی)
            is_finished   INTEGER DEFAULT 0,
            created_at    TEXT
        )""")

        # جدول پاسخ‌ها (هر کاربر برای هر بازی یک پاسخ)
        c.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            match_id    INTEGER,
            answer      TEXT,    -- win / lose
            awarded     INTEGER DEFAULT 0,
            created_at  TEXT,
            UNIQUE(user_id, match_id)
        )""")

        # جدول تنظیمات متنی (قوانین و ...)
        c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key    TEXT PRIMARY KEY,
            value  TEXT
        )""")

        conn.commit()

    # مقدار پیش‌فرض قوانین
    if get_setting("rules") is None:
        set_setting("rules",
            "📜 قوانین مسابقه پیش‌بینی جام جهانی ۲۰۲۶:\n\n"
            "۱) برای هر بازی پیش‌بینی کنید که تیم اول برنده می‌شود یا می‌بازد.\n"
            "۲) پاسخ درست = ۱۰ امتیاز.\n"
            "۳) فقط در بازه‌ی زمانی تعیین‌شده می‌توانید پاسخ دهید.\n"
            "۴) پس از پایان هر بازی نتیجه اعلام و امتیازها واریز می‌شود.\n"
            "۵) با دعوت هر دوست = ۱۰ امتیاز هدیه.\n"
            "۶) در پایان هر مرحله بین نفرات برتر قرعه‌کشی و جایزه نقدی اهدا می‌شود.\n\n"
            "موفق باشید! ⚽")


# ---------- توابع کاربران ----------
def get_user(user_id):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_user(user_id, referral_code, referred_by=None):
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, referral_code, referred_by, joined_at, state) "
            "VALUES (?,?,?,?, 'ask_name')",
            (user_id, referral_code, referred_by, datetime.now().isoformat()))
        conn.commit()


def update_user(user_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [user_id]
    with _lock, get_conn() as conn:
        conn.execute(f"UPDATE users SET {cols} WHERE user_id=?", vals)
        conn.commit()


def add_points(user_id, amount):
    with _lock, get_conn() as conn:
        conn.execute("UPDATE users SET points = points + ? WHERE user_id=?", (amount, user_id))
        conn.commit()


def get_user_by_refcode(code):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE referral_code=?", (code,)).fetchone()
        return dict(row) if row else None


def count_referrals(user_id):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) c FROM users WHERE referred_by=?", (user_id,)).fetchone()
        return row["c"]


def all_users():
    with _lock, get_conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY points DESC").fetchall()
        return [dict(r) for r in rows]


# ---------- توابع مسابقه‌ها ----------
def add_match(team1, team2, start_time, close_time):
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT INTO matches (team1, team2, start_time, close_time, created_at) VALUES (?,?,?,?,?)",
            (team1, team2, start_time, close_time, datetime.now().isoformat()))
        conn.commit()


def get_match(match_id):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
        return dict(row) if row else None


def all_matches():
    with _lock, get_conn() as conn:
        rows = conn.execute("SELECT * FROM matches ORDER BY start_time").fetchall()
        return [dict(r) for r in rows]


def active_matches():
    """بازی‌هایی که هنوز تمام نشده‌اند (برای نمایش در ربات)."""
    with _lock, get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM matches WHERE is_finished=0 ORDER BY start_time").fetchall()
        return [dict(r) for r in rows]


def delete_match(match_id):
    with _lock, get_conn() as conn:
        conn.execute("DELETE FROM matches WHERE id=?", (match_id,))
        conn.execute("DELETE FROM predictions WHERE match_id=?", (match_id,))
        conn.commit()


def update_match(match_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [match_id]
    with _lock, get_conn() as conn:
        conn.execute(f"UPDATE matches SET {cols} WHERE id=?", vals)
        conn.commit()


# ---------- توابع پیش‌بینی ----------
def get_prediction(user_id, match_id):
    with _lock, get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM predictions WHERE user_id=? AND match_id=?",
            (user_id, match_id)).fetchone()
        return dict(row) if row else None


def save_prediction(user_id, match_id, answer):
    with _lock, get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO predictions (id, user_id, match_id, answer, awarded, created_at) "
            "VALUES ((SELECT id FROM predictions WHERE user_id=? AND match_id=?), ?,?,?,0,?)",
            (user_id, match_id, user_id, match_id, answer, datetime.now().isoformat()))
        conn.commit()


def award_match_points(match_id, result, points):
    """
    به همه‌ی کسانی که پاسخ درست داده‌اند و هنوز امتیاز نگرفته‌اند، امتیاز می‌دهد.
    خروجی: تعداد برندگان.
    """
    winners = 0
    with _lock, get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM predictions WHERE match_id=? AND answer=? AND awarded=0",
            (match_id, result)).fetchall()
        for r in rows:
            conn.execute("UPDATE users SET points = points + ? WHERE user_id=?",
                         (points, r["user_id"]))
            conn.execute("UPDATE predictions SET awarded=1 WHERE id=?", (r["id"],))
            winners += 1
        conn.commit()
    return winners

# ---------- نفرات برتر ----------
def top_users(limit=10):
    """لیست نفرات برتر بر اساس امتیاز (فقط کاربرانی که ثبت‌نام کامل کرده‌اند)."""
    with _lock, get_conn() as conn:
        rows = conn.execute(
            "SELECT full_name, points FROM users "
            "WHERE state='done' AND points > 0 "
            "ORDER BY points DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def all_user_ids():
    """شناسه همه کاربرانی که ثبت‌نام کامل کرده‌اند (برای پیام همگانی)."""
    with _lock, get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM users WHERE state='done'").fetchall()
        return [r["user_id"] for r in rows]

# ---------- تنظیمات متنی ----------
def get_setting(key):
    with _lock, get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def set_setting(key, value):
    with _lock, get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        conn.commit()
