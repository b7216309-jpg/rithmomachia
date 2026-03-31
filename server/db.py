"""SQLite persistence for game history.

Stores completed game summaries so they survive server restarts.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

import os
_db_env = os.environ.get("DB_PATH")
DB_PATH = Path(_db_env) if _db_env else Path(__file__).resolve().parent.parent / "data" / "games.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_history (
                game_id TEXT PRIMARY KEY,
                started_at REAL NOT NULL,
                ended_at REAL,
                status TEXT NOT NULL,
                winner TEXT,
                victory_type TEXT DEFAULT 'none',
                move_count INTEGER DEFAULT 0,
                white_name TEXT DEFAULT 'White',
                black_name TEXT DEFAULT 'Black',
                white_type TEXT DEFAULT 'human',
                black_type TEXT DEFAULT 'human',
                white_captures TEXT DEFAULT '[]',
                black_captures TEXT DEFAULT '[]',
                summary TEXT DEFAULT ''
            )
        """)


def save_game_start(game_id: str, white_name: str, black_name: str,
                    white_type: str, black_type: str):
    with _conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO game_history
            (game_id, started_at, status, white_name, black_name, white_type, black_type)
            VALUES (?, ?, 'active', ?, ?, ?, ?)
        """, (game_id, time.time(), white_name, black_name, white_type, black_type))


def save_game_end(game_id: str, status: str, winner: Optional[str],
                  victory_type: str, move_count: int,
                  white_captures: list[int], black_captures: list[int],
                  summary: str):
    with _conn() as conn:
        conn.execute("""
            UPDATE game_history SET
                ended_at = ?, status = ?, winner = ?, victory_type = ?,
                move_count = ?, white_captures = ?, black_captures = ?,
                summary = ?
            WHERE game_id = ?
        """, (
            time.time(), status, winner, victory_type,
            move_count, json.dumps(white_captures), json.dumps(black_captures),
            summary, game_id,
        ))


def get_game_record(game_id: str) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM game_history WHERE game_id = ?", (game_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)


def list_games(limit: int = 50, offset: int = 0) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM game_history ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["white_captures"] = json.loads(d["white_captures"])
    d["black_captures"] = json.loads(d["black_captures"])
    return d
