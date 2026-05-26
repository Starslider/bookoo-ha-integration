"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    """Runtime configuration."""

    ha_url: str
    ha_token: str
    db_path: str
    recipe_path: str
    settings_path: str
    pressure_entity: str
    weight_entity: str
    flow_entity: str
    timer_entity: str
    pressure_start_bar: float
    shot_idle_seconds: float
    influx_enabled: bool
    influx_host: str
    influx_port: int
    influx_database: str
    influx_username: str
    influx_password: str
    influx_ssl: bool
    influx_verify_ssl: bool


def load_config() -> Config:
    """Load configuration from environment variables."""
    ha_url = os.environ.get("HA_URL", "http://homeassistant.local:8123").rstrip("/")
    return Config(
        ha_url=ha_url,
        ha_token=os.environ["HA_TOKEN"],
        db_path=os.environ.get("BOOKOO_SHOT_DB", "bookoo_shots.sqlite3"),
        recipe_path=os.environ.get("BOOKOO_RECIPE_FILE", "bookoo_recipe.json"),
        settings_path=os.environ.get("BOOKOO_SETTINGS_FILE", "bookoo_settings.json"),
        pressure_entity=os.environ.get("BOOKOO_PRESSURE_ENTITY", "sensor.bookoo_em_pressure"),
        weight_entity=os.environ.get("BOOKOO_WEIGHT_ENTITY", "sensor.bookoo_scale_weight"),
        flow_entity=os.environ.get("BOOKOO_FLOW_ENTITY", "sensor.bookoo_scale_flow"),
        timer_entity=os.environ.get("BOOKOO_TIMER_ENTITY", "sensor.bookoo_scale_timer"),
        pressure_start_bar=float(os.environ.get("BOOKOO_PRESSURE_START_BAR", "0.5")),
        shot_idle_seconds=float(os.environ.get("BOOKOO_SHOT_IDLE_SECONDS", "4")),
        influx_enabled=os.environ.get("BOOKOO_INFLUX_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
        influx_host=os.environ.get("BOOKOO_INFLUX_HOST", "localhost"),
        influx_port=int(os.environ.get("BOOKOO_INFLUX_PORT", "8086")),
        influx_database=os.environ.get("BOOKOO_INFLUX_DATABASE", "homeassistant"),
        influx_username=os.environ.get("BOOKOO_INFLUX_USERNAME", ""),
        influx_password=os.environ.get("BOOKOO_INFLUX_PASSWORD", ""),
        influx_ssl=os.environ.get("BOOKOO_INFLUX_SSL", "false").lower() in {"1", "true", "yes", "on"},
        influx_verify_ssl=os.environ.get("BOOKOO_INFLUX_VERIFY_SSL", "true").lower() in {"1", "true", "yes", "on"},
    )

    # HA_URL examples:
    # http://homeassistant.local:8123
    # http://192.168.1.20:8123
