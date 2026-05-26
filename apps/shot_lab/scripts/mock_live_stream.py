#!/usr/bin/env python3
"""Run Shot Lab with a fake live collector for UI testing."""

from __future__ import annotations

import asyncio
import math
import random
import time
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["BOOKOO_MOCK_MODE"] = "true"

import uvicorn

from bookoo_shot_lab.app import app, collector
from bookoo_shot_lab.storage import Sample


async def fake_live_loop() -> None:
    """Continuously feed mock live samples into the app collector."""
    while True:
        start = time.time()
        collector.running = True
        collector.current_samples = []
        previous_weight = 0.0

        for step in range(70):
            now = time.time()
            elapsed = now - start
            progress = min(elapsed / 32, 1)
            pressure = max(0.0, 9.0 * smoothstep(min(progress / 0.22, 1)) * (1 - max(progress - 0.7, 0) * 0.4))
            flow = max(0.0, 1.4 + 0.7 * math.sin(progress * math.pi) + random.uniform(-0.08, 0.08))
            weight = min(42, previous_weight + flow * 0.5)
            previous_weight = weight

            collector.values.pressure_bar = round(pressure, 2)
            collector.values.flow_g_s = round(flow, 2)
            collector.values.weight_g = round(weight, 2)
            collector.values.timer_s = round(elapsed, 2)
            collector.last_active_at = now
            collector.last_seen["pressure"] = now
            collector.last_seen["weight"] = now
            collector.last_seen["flow"] = now
            collector.last_seen["timer"] = now
            collector.current_samples.append(
                Sample(
                    timestamp=now,
                    pressure_bar=collector.values.pressure_bar,
                    weight_g=collector.values.weight_g,
                    flow_g_s=collector.values.flow_g_s,
                    timer_s=collector.values.timer_s,
                )
            )
            await asyncio.sleep(0.5)

        collector.running = False
        await asyncio.sleep(6)


def smoothstep(x: float) -> float:
    x = min(max(x, 0), 1)
    return x * x * (3 - 2 * x)


@app.on_event("startup")
async def start_fake_live() -> None:
    asyncio.create_task(fake_live_loop())


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8099)
