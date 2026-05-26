"""
BulkWave Pro - SQLite Database Layer
"""

import sqlite3
import os
from pathlib import Path
from utils.helpers import get_data_dir, now_timestamp


DEFAULT_SETTINGS = {
    "country_code": "91",
    "min_delay": "3",
    "max_delay": "7",
    "theme": "dark",
    "auto_retry": "true",
    "max_retries": "2",
    "turbo_mode": "false",
    "session_path": "",          # resolved at runtime
    "browser_path": "auto",
    "sending_hour_start": "9",
    "sending_hour_end": "21",
}

_DB_PATH = None


def _get_db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = get_data_dir() / "BulkWave.db"
    return _DB_PATH


class Database:
    """Thin wrapper around SQLite; one instance shared app-wide."""

    def __init__(self):
        self.db_path = str(_get_db_path())

    # ─── Connection ───────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ─── Initialisation ───────────────────────────────────────────────────────

    def initialize(self):
        """Create tables and seed default settings on first run."""
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS campaigns (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    name            TEXT    NOT NULL,
                    status          TEXT    DEFAULT 'pending',
                    total_contacts  INTEGER DEFAULT 0,
                    sent_count      INTEGER DEFAULT 0,
                    failed_count    INTEGER DEFAULT 0,
                    message         TEXT,
                    has_image       INTEGER DEFAULT 0,
                    excel_file      TEXT,
                    created_at      TEXT,
                    completed_at    TEXT
                );

                CREATE TABLE IF NOT EXISTS contact_results (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id     INTEGER,
                    phone           TEXT,
                    name            TEXT,
                    status          TEXT,
                    error_message   TEXT,
                    sent_at         TEXT,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
                );

                CREATE TABLE IF NOT EXISTS templates (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    name        TEXT NOT NULL,
                    content     TEXT,
                    created_at  TEXT
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key     TEXT PRIMARY KEY,
                    value   TEXT
                );

                CREATE TABLE IF NOT EXISTS app_logs (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    level       TEXT,
                    message     TEXT,
                    timestamp   TEXT,
                    campaign_id INTEGER
                );
                """
            )
            self._seed_settings(conn)

    def _seed_settings(self, conn: sqlite3.Connection):
        """Insert default settings only when a key does not already exist."""
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )

    # ─── Settings ─────────────────────────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, str(value)),
            )

    def get_all_settings(self) -> dict:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
            return {r["key"]: r["value"] for r in rows}

    def save_settings(self, settings_dict: dict):
        with self._connect() as conn:
            for key, value in settings_dict.items():
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, str(value)),
                )

    # ─── Campaigns ────────────────────────────────────────────────────────────

    def create_campaign(
        self,
        name: str,
        message: str,
        total_contacts: int,
        has_image: bool = False,
        excel_file: str = "",
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO campaigns
                   (name, message, total_contacts, has_image, excel_file, created_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, 'running')""",
                (name, message, total_contacts, int(has_image), excel_file, now_timestamp()),
            )
            return cursor.lastrowid

    def update_campaign(self, campaign_id: int, **kwargs):
        if not kwargs:
            return
        fields = ", ".join(f"{k}=?" for k in kwargs)
        values = list(kwargs.values()) + [campaign_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE campaigns SET {fields} WHERE id=?", values
            )

    def complete_campaign(self, campaign_id: int, status: str = "completed"):
        self.update_campaign(campaign_id, status=status, completed_at=now_timestamp())

    def get_campaigns(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM campaigns ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_campaign(self, campaign_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM campaigns WHERE id=?", (campaign_id,)
            ).fetchone()
            return dict(row) if row else None

    def delete_campaign(self, campaign_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM contact_results WHERE campaign_id=?", (campaign_id,))
            conn.execute("DELETE FROM campaigns WHERE id=?", (campaign_id,))

    # ─── Contact Results ──────────────────────────────────────────────────────

    def save_contact_result(
        self,
        campaign_id: int,
        phone: str,
        name: str,
        status: str,
        error_message: str = "",
    ):
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO contact_results
                   (campaign_id, phone, name, status, error_message, sent_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (campaign_id, phone, name, status, error_message, now_timestamp()),
            )

    def get_failed_contacts(self, campaign_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM contact_results WHERE campaign_id=? AND status='failed'",
                (campaign_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_contact_results(self, campaign_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM contact_results WHERE campaign_id=?", (campaign_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ─── Templates ────────────────────────────────────────────────────────────

    def save_template(self, name: str, content: str) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO templates (name, content, created_at) VALUES (?, ?, ?)",
                (name, content, now_timestamp()),
            )
            return cursor.lastrowid

    def get_templates(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM templates ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_template(self, template_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM templates WHERE id=?", (template_id,))

    # ─── App Logs ─────────────────────────────────────────────────────────────

    def add_log(self, level: str, message: str, campaign_id: int = None):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO app_logs (level, message, timestamp, campaign_id) VALUES (?, ?, ?, ?)",
                (level, message, now_timestamp(), campaign_id),
            )

    def get_logs(self, limit: int = 500, level: str = None) -> list[dict]:
        with self._connect() as conn:
            if level and level != "ALL":
                rows = conn.execute(
                    "SELECT * FROM app_logs WHERE level=? ORDER BY id DESC LIMIT ?",
                    (level, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM app_logs ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def clear_logs(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM app_logs")

    # ─── Stats ────────────────────────────────────────────────────────────────

    def get_overall_stats(self) -> dict:
        with self._connect() as conn:
            total_campaigns = conn.execute(
                "SELECT COUNT(*) as c FROM campaigns"
            ).fetchone()["c"]
            totals = conn.execute(
                "SELECT SUM(sent_count) as sent, SUM(failed_count) as failed FROM campaigns"
            ).fetchone()
            sent = totals["sent"] or 0
            failed = totals["failed"] or 0
            total_msgs = sent + failed
            success_rate = round((sent / total_msgs * 100), 1) if total_msgs > 0 else 0.0
            return {
                "total_campaigns": total_campaigns,
                "total_sent": sent,
                "total_failed": failed,
                "success_rate": success_rate,
            }
