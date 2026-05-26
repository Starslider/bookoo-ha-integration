#!/usr/bin/env python3
"""Generate mock Bookoo shot data for local app and Grafana testing."""

from __future__ import annotations

import argparse
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bookoo_shot_lab.analyzer import analyze_shot
from bookoo_shot_lab.config import load_config
from bookoo_shot_lab.influx import ShotInfluxWriter
from bookoo_shot_lab.recipe import RecipeStore
from bookoo_shot_lab.storage import Sample, Storage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", type=int, default=8)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--spacing-minutes", type=float, default=20)
    parser.add_argument("--live", action="store_true", help="Generate the latest shot ending at the current time.")
    parser.add_argument("--influx", action="store_true", help="Also write mock raw sensor points and shot summaries to InfluxDB.")
    args = parser.parse_args()

    config = load_config()
    storage = Storage(config.db_path)
    recipe = RecipeStore(config.recipe_path).load()
    influx_writer = ShotInfluxWriter(config)

    now = time.time()
    first_start = now - ((args.shots - 1) * args.spacing_minutes * 60)
    saved = 0

    for index in range(args.shots):
        if args.live and index == args.shots - 1:
            started_at = now - 18
        else:
            started_at = first_start + index * args.spacing_minutes * 60

        samples = generate_shot(
            started_at=started_at,
            duration_s=random.uniform(24, 34),
            interval_s=args.interval,
            target_yield_g=random.uniform(32, 44),
            peak_pressure_bar=random.uniform(7.5, 10.5),
        )
        shot_id = storage.save_shot(
            samples,
            input_dose_g=recipe.input_dose_g,
            target_yield_g=recipe.target_yield_g,
        )
        if shot_id is None:
            continue

        saved += 1
        shot = storage.get_shot(shot_id)
        saved_samples = storage.get_samples(shot_id)
        if shot is None:
            continue

        if args.influx:
            if not influx_writer.enabled:
                raise SystemExit("Set BOOKOO_INFLUX_ENABLED=true and Influx env vars before using --influx.")
            write_raw_sensor_points(config, influx_writer, samples)
            influx_writer.write_shot(shot_id, shot, analyze_shot(shot, saved_samples))

    print(f"Generated {saved} mock shots in {config.db_path}")


def generate_shot(
    started_at: float,
    duration_s: float,
    interval_s: float,
    target_yield_g: float,
    peak_pressure_bar: float,
) -> list[Sample]:
    """Generate one plausible espresso shot."""
    sample_count = max(2, int(duration_s / interval_s) + 1)
    samples: list[Sample] = []
    previous_weight = 0.0

    for i in range(sample_count):
        elapsed = i * interval_s
        progress = min(elapsed / duration_s, 1)

        ramp = min(progress / 0.22, 1)
        tail = 1 - max(progress - 0.72, 0) * 0.35
        pressure = peak_pressure_bar * smoothstep(ramp) * tail
        pressure += random.uniform(-0.18, 0.18)
        pressure = max(0.0, pressure)

        flow_shape = 0.35 + 0.85 * math.sin(progress * math.pi)
        flow = max(0.0, (target_yield_g / duration_s) * flow_shape + random.uniform(-0.12, 0.12))

        weight = min(target_yield_g, previous_weight + flow * interval_s)
        if progress < 0.08:
            weight = max(0.0, weight - 0.2)
        previous_weight = weight

        samples.append(
            Sample(
                timestamp=started_at + elapsed,
                pressure_bar=round(pressure, 2),
                weight_g=round(weight, 2),
                flow_g_s=round(flow, 2),
                timer_s=round(elapsed, 2),
            )
        )

    return samples


def write_raw_sensor_points(config, influx_writer: ShotInfluxWriter, samples: list[Sample]) -> None:
    """Write Home Assistant-like raw sensor points into InfluxDB."""
    if influx_writer.client is None:
        return

    points = []
    entity_measurements = [
        ("bar", entity_tag(config.pressure_entity), "pressure_bar"),
        ("g", entity_tag(config.weight_entity), "weight_g"),
        ("g/s", entity_tag(config.flow_entity), "flow_g_s"),
        ("s", entity_tag(config.timer_entity), "timer_s"),
    ]

    for sample in samples:
        values = {
            "pressure_bar": sample.pressure_bar,
            "weight_g": sample.weight_g,
            "flow_g_s": sample.flow_g_s,
            "timer_s": sample.timer_s,
        }
        for measurement, entity_id, value_key in entity_measurements:
            value = values[value_key]
            if value is None:
                continue
            points.append(
                {
                    "measurement": measurement,
                    "tags": {
                        "entity_id": entity_id,
                    },
                    "time": int(sample.timestamp * 1_000_000_000),
                    "fields": {
                        "value": float(value),
                    },
                }
            )

    influx_writer.client.write_points(points, time_precision="n")


def entity_tag(entity_id: str) -> str:
    """Convert a Home Assistant entity id to the Influx entity_id tag."""
    return entity_id.split(".", 1)[1] if "." in entity_id else entity_id


def smoothstep(x: float) -> float:
    """Smooth ramp from 0 to 1."""
    x = min(max(x, 0), 1)
    return x * x * (3 - 2 * x)


if __name__ == "__main__":
    main()
