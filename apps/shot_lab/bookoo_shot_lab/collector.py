"""Home Assistant WebSocket collector."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

import websockets

from .analyzer import analyze_shot
from .config import Config
from .influx import ShotInfluxWriter
from .recipe import RecipeStore
from .settings import SettingsStore
from .storage import Sample, Storage

_LOGGER = logging.getLogger(__name__)


@dataclass
class CurrentValues:
    """Latest entity values."""

    pressure_bar: float | None = None
    weight_g: float | None = None
    flow_g_s: float | None = None
    timer_s: float | None = None


class ShotCollector:
    """Collect shot samples from Home Assistant state changes."""

    def __init__(
        self,
        config: Config,
        storage: Storage,
        influx: ShotInfluxWriter | None = None,
        recipe_store: RecipeStore | None = None,
        settings_store: SettingsStore | None = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.influx = influx
        self.recipe_store = recipe_store
        self.settings_store = settings_store
        self.values = CurrentValues()
        self.last_seen: dict[str, float] = {}
        self.current_samples: list[Sample] = []
        self.last_active_at = 0.0
        self.running = False

    async def run_forever(self) -> None:
        """Maintain the Home Assistant WebSocket subscription."""
        while True:
            try:
                await self._run_once()
            except Exception:
                _LOGGER.exception("Home Assistant collector crashed; reconnecting")
                await asyncio.sleep(5)

    async def _run_once(self) -> None:
        ws_url = self.config.ha_url.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_url}/api/websocket"
        async with websockets.connect(ws_url) as websocket:
            auth_required = json.loads(await websocket.recv())
            if auth_required.get("type") != "auth_required":
                raise RuntimeError(f"Unexpected HA auth message: {auth_required}")

            await websocket.send(json.dumps({"type": "auth", "access_token": self.config.ha_token}))
            auth_result = json.loads(await websocket.recv())
            if auth_result.get("type") != "auth_ok":
                raise RuntimeError(f"Home Assistant auth failed: {auth_result}")

            await websocket.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))
            subscribed = json.loads(await websocket.recv())
            if not subscribed.get("success"):
                raise RuntimeError(f"Home Assistant subscription failed: {subscribed}")

            async for raw_message in websocket:
                message = json.loads(raw_message)
                if message.get("type") != "event":
                    continue
                self._handle_event(message["event"])

    def _handle_event(self, event: dict) -> None:
        entity_id = event["data"].get("entity_id")
        new_state = event["data"].get("new_state") or {}
        state = new_state.get("state")

        value = _float_or_none(state)
        if value is None:
            return

        settings = self.settings_store.load() if self.settings_store is not None else None
        pressure_entity = settings.pressure_entity if settings is not None else self.config.pressure_entity
        weight_entity = settings.weight_entity if settings is not None else self.config.weight_entity
        flow_entity = settings.flow_entity if settings is not None else self.config.flow_entity
        timer_entity = settings.timer_entity if settings is not None else self.config.timer_entity

        if entity_id == pressure_entity:
            self.values.pressure_bar = value
            self.last_seen["pressure"] = time.time()
        elif entity_id == weight_entity:
            self.values.weight_g = value
            self.last_seen["weight"] = time.time()
        elif entity_id == flow_entity:
            self.values.flow_g_s = value
            self.last_seen["flow"] = time.time()
        elif entity_id == timer_entity:
            self.values.timer_s = value
            self.last_seen["timer"] = time.time()
        else:
            return

        self._maybe_record_sample(time.time())

    def current_status(self) -> dict:
        """Return the current live state for the web app."""
        return {
            "running": self.running,
            "sample_count": len(self.current_samples),
            "last_active_at": self.last_active_at or None,
            "pressure_bar": self.values.pressure_bar,
            "weight_g": self.values.weight_g,
            "flow_g_s": self.values.flow_g_s,
            "timer_s": self.values.timer_s,
            "last_seen": self.last_seen,
            "samples": [
                {
                    "timestamp": sample.timestamp,
                    "pressure_bar": sample.pressure_bar,
                    "weight_g": sample.weight_g,
                    "flow_g_s": sample.flow_g_s,
                    "timer_s": sample.timer_s,
                }
                for sample in self.current_samples[-600:]
            ],
        }

    def _maybe_record_sample(self, now: float) -> None:
        settings = self.settings_store.load() if self.settings_store is not None else None
        pressure_start_bar = settings.pressure_start_bar if settings is not None else self.config.pressure_start_bar
        shot_idle_seconds = settings.shot_idle_seconds if settings is not None else self.config.shot_idle_seconds
        active = (
            (self.values.pressure_bar is not None and self.values.pressure_bar >= pressure_start_bar)
            or (self.values.timer_s is not None and self.values.timer_s > 0.2)
        )

        if active:
            self.running = True
            self.last_active_at = now
            self.current_samples.append(
                Sample(
                    timestamp=now,
                    pressure_bar=self.values.pressure_bar,
                    weight_g=self.values.weight_g,
                    flow_g_s=self.values.flow_g_s,
                    timer_s=self.values.timer_s,
                )
            )
            return

        if self.running and now - self.last_active_at >= shot_idle_seconds:
            recipe = self.recipe_store.load() if self.recipe_store is not None else None
            shot_id = self.storage.save_shot(
                self.current_samples,
                input_dose_g=recipe.input_dose_g if recipe is not None else None,
                target_yield_g=recipe.target_yield_g if recipe is not None else None,
            )
            if shot_id is not None:
                _LOGGER.info("Saved Bookoo shot %s with %s samples", shot_id, len(self.current_samples))
                if self.influx is not None:
                    shot = self.storage.get_shot(shot_id)
                    samples = self.storage.get_samples(shot_id)
                    if shot is not None:
                        self.influx.write_shot(shot_id, shot, analyze_shot(shot, samples))
            self.running = False
            self.current_samples = []


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
