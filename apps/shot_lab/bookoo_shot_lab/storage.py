"""SQLite persistence."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Sample:
    """A single shot sample."""

    timestamp: float
    pressure_bar: float | None
    weight_g: float | None
    flow_g_s: float | None
    timer_s: float | None


class Storage:
    """SQLite storage for shots and samples."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists shots (
                  id integer primary key autoincrement,
                  started_at real not null,
                  ended_at real not null,
                  duration_s real not null,
                  final_weight_g real,
                  max_pressure_bar real,
                  avg_pressure_bar real,
                  avg_flow_g_s real,
                  sample_count integer not null,
                  input_dose_g real,
                  target_yield_g real,
                  notes text
                )
                """
            )
            conn.execute(
                """
                create table if not exists samples (
                  id integer primary key autoincrement,
                  shot_id integer not null references shots(id) on delete cascade,
                  timestamp real not null,
                  pressure_bar real,
                  weight_g real,
                  flow_g_s real,
                  timer_s real
                )
                """
            )
            self._ensure_column(conn, "shots", "input_dose_g", "real")
            self._ensure_column(conn, "shots", "target_yield_g", "real")

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table: str,
        column: str,
        definition: str,
    ) -> None:
        columns = {
            row["name"]
            for row in conn.execute(f"pragma table_info({table})").fetchall()
        }
        if column not in columns:
            conn.execute(f"alter table {table} add column {column} {definition}")

    def save_shot(
        self,
        samples: Iterable[Sample],
        input_dose_g: float | None = None,
        target_yield_g: float | None = None,
    ) -> int | None:
        """Persist one shot and return its id."""
        sample_list = list(samples)
        if len(sample_list) < 2:
            return None

        started_at = sample_list[0].timestamp
        ended_at = sample_list[-1].timestamp
        duration_s = ended_at - started_at
        pressures = [sample.pressure_bar for sample in sample_list if sample.pressure_bar is not None]
        flows = [sample.flow_g_s for sample in sample_list if sample.flow_g_s is not None]
        weights = [sample.weight_g for sample in sample_list if sample.weight_g is not None]

        with self._connect() as conn:
            cursor = conn.execute(
                """
                insert into shots (
                  started_at, ended_at, duration_s, final_weight_g,
                  max_pressure_bar, avg_pressure_bar, avg_flow_g_s,
                  sample_count, input_dose_g, target_yield_g
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    started_at,
                    ended_at,
                    duration_s,
                    weights[-1] if weights else None,
                    max(pressures) if pressures else None,
                    sum(pressures) / len(pressures) if pressures else None,
                    sum(flows) / len(flows) if flows else None,
                    len(sample_list),
                    input_dose_g,
                    target_yield_g,
                ),
            )
            shot_id = int(cursor.lastrowid)
            conn.executemany(
                """
                insert into samples (
                  shot_id, timestamp, pressure_bar, weight_g, flow_g_s, timer_s
                )
                values (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        shot_id,
                        sample.timestamp,
                        sample.pressure_bar,
                        sample.weight_g,
                        sample.flow_g_s,
                        sample.timer_s,
                    )
                    for sample in sample_list
                ],
            )
            return shot_id

    def list_shots(self, limit: int = 50) -> list[dict]:
        """Return recent shots."""
        with self._connect() as conn:
            rows = conn.execute(
                "select * from shots order by started_at desc limit ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_shot(self, shot_id: int) -> dict | None:
        """Return one shot."""
        with self._connect() as conn:
            row = conn.execute("select * from shots where id = ?", (shot_id,)).fetchone()
        return dict(row) if row else None

    def get_samples(self, shot_id: int) -> list[dict]:
        """Return samples for one shot."""
        with self._connect() as conn:
            rows = conn.execute(
                "select * from samples where shot_id = ? order by timestamp",
                (shot_id,),
            ).fetchall()
        return [dict(row) for row in rows]
