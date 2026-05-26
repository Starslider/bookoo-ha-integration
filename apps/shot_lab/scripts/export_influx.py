#!/usr/bin/env python3
"""Backfill Shot Lab SQLite shot summaries into InfluxDB."""

from __future__ import annotations

from bookoo_shot_lab.analyzer import analyze_shot
from bookoo_shot_lab.config import load_config
from bookoo_shot_lab.influx import ShotInfluxWriter
from bookoo_shot_lab.storage import Storage


def main() -> None:
    config = load_config()
    storage = Storage(config.db_path)
    writer = ShotInfluxWriter(config)
    if not writer.enabled:
        raise SystemExit("Set BOOKOO_INFLUX_ENABLED=true before exporting.")

    count = 0
    for shot in storage.list_shots(limit=10_000):
        samples = storage.get_samples(shot["id"])
        writer.write_shot(shot["id"], shot, analyze_shot(shot, samples))
        count += 1

    print(f"Exported {count} shots to InfluxDB")


if __name__ == "__main__":
    main()
