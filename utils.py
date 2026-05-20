"""Utility helpers: preprocessing, persistence, and formatting."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

ISO_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?\S*\s*")
SYSLOG_TS_RE = re.compile(r"^[A-Z][a-z]{2}\s+\d+\s+\d{2}:\d{2}:\d{2}\s+")
MULTISPACE_RE = re.compile(r"\s+")
SERVICE_RE = re.compile(r"([a-zA-Z0-9_.@-]+\.service)")


def clean_log_line(raw: str) -> str:
    """Strip timestamp noise and normalize spaces."""
    text = ISO_TS_RE.sub("", raw)
    text = SYSLOG_TS_RE.sub("", text)
    return MULTISPACE_RE.sub(" ", text).strip().lower()


def extract_service_name(message: str) -> Optional[str]:
    """Extract systemd service name from log text."""
    match = SERVICE_RE.search(message)
    return match.group(1) if match else None


def score_blob(scores: dict[str, float]) -> str:
    """Serialize score dictionary compactly."""
    return json.dumps(scores, separators=(",", ":"), sort_keys=True)


class SQLiteStore:
    """Minimal SQLite storage for logs, detections, and fix actions."""

    def __init__(self, db_path: Path) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._initialize()

    def _initialize(self) -> None:
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS raw_logs ("
                "id INTEGER PRIMARY KEY, ts TEXT, source TEXT, message TEXT)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS detections ("
                "id TEXT PRIMARY KEY, ts TEXT, source TEXT, error_type TEXT,"
                "confidence REAL, message TEXT, recommendation TEXT, scores TEXT)"
            )
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS actions ("
                "id INTEGER PRIMARY KEY, ts TEXT, detection_id TEXT,"
                "action TEXT, success INTEGER, output TEXT)"
            )

    def insert_raw_log(self, ts: str, source: str, message: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO raw_logs(ts, source, message) VALUES (?, ?, ?)",
                (ts, source, message),
            )

    def insert_detection(self, payload: dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO detections"
                "(id, ts, source, error_type, confidence, message, recommendation, scores) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    payload["id"],
                    payload["timestamp"],
                    payload["source"],
                    payload["error_type"],
                    payload["confidence"],
                    payload["raw_log"],
                    payload["recommendation"],
                    score_blob(payload["scores"]),
                ),
            )

    def insert_action(
        self, ts: str, detection_id: str, action: str, success: bool, output: str
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO actions(ts, detection_id, action, success, output) "
                "VALUES (?, ?, ?, ?, ?)",
                (ts, detection_id, action, int(success), output),
            )

    def recent_detections(self, limit: int = 20) -> list[dict[str, Any]]:
        query = (
            "SELECT id, ts, source, error_type, confidence, message, recommendation "
            "FROM detections ORDER BY ts DESC LIMIT ?"
        )
        rows = self._conn.execute(query, (limit,)).fetchall()
        return [self._row_to_detection(row) for row in rows]

    def _row_to_detection(self, row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "timestamp": row[1],
            "source": row[2],
            "error_type": row[3],
            "confidence": row[4],
            "raw_log": row[5],
            "recommendation": row[6],
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()
