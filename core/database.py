"""Attendance database (SQLite). One row per person per day."""
import csv
import sqlite3
from datetime import datetime

from core.config import DB_FILE

_SCHEMA = """CREATE TABLE IF NOT EXISTS attendance (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    date       TEXT NOT NULL,      -- YYYY-MM-DD
    first_seen TEXT NOT NULL,      -- check-in  (HH:MM:SS)
    last_seen  TEXT NOT NULL,      -- updated while the person stays in view
    UNIQUE(name, date)
)"""


def _connect():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    return conn


def _fetch(sql, params=()):
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def today():
    return datetime.now().strftime("%Y-%m-%d")


def mark_present(name):
    """Marks `name` present today. Returns True only on their FIRST sighting of the day."""
    now = datetime.now()
    day, t = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
    conn = _connect()
    try:
        with conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO attendance (name, date, first_seen, last_seen) VALUES (?,?,?,?)",
                (name, day, t, t))
            if cur.rowcount == 1:
                return True
            conn.execute("UPDATE attendance SET last_seen=? WHERE name=? AND date=?", (t, name, day))
            return False
    finally:
        conn.close()


def records_for_date(day):
    return _fetch("SELECT id, name, date, first_seen, last_seen FROM attendance "
                  "WHERE date=? ORDER BY first_seen", (day,))


def records_between(start, end):
    return _fetch("SELECT id, name, date, first_seen, last_seen FROM attendance "
                  "WHERE date BETWEEN ? AND ? ORDER BY date, first_seen", (start, end))


def add_record(name, day, first, last=None):
    """Manual entry (teacher override). Updates the check-in time if the row already exists."""
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "INSERT INTO attendance (name, date, first_seen, last_seen) VALUES (?,?,?,?) "
                "ON CONFLICT(name, date) DO UPDATE SET first_seen=excluded.first_seen",
                (name, day, first, last or first))
    finally:
        conn.close()


def delete_record(rec_id):
    conn = _connect()
    try:
        with conn:
            conn.execute("DELETE FROM attendance WHERE id=?", (rec_id,))
    finally:
        conn.close()


def duration_text(first, last):
    try:
        a = datetime.strptime(first, "%H:%M:%S")
        b = datetime.strptime(last, "%H:%M:%S")
    except (TypeError, ValueError):
        return "–"
    mins = int((b - a).total_seconds() // 60)
    if mins < 1:
        return "< 1 min"
    h, m = divmod(mins, 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def export_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:   # utf-8-sig: Excel opens it cleanly
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
