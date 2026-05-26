"""Runtime app settings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import Config


@dataclass
class AppSettings:
    """Settings editable from the web UI."""

    pressure_entity: str
    weight_entity: str
    flow_entity: str
    timer_entity: str
    pressure_start_bar: float
    shot_idle_seconds: float


class SettingsStore:
    """Persist editable app settings in JSON."""

    def __init__(self, path: str, config: Config) -> None:
        self.path = Path(path)
        self.config = config

    def defaults(self) -> AppSettings:
        """Return default settings from environment configuration."""
        return AppSettings(
            pressure_entity=self.config.pressure_entity,
            weight_entity=self.config.weight_entity,
            flow_entity=self.config.flow_entity,
            timer_entity=self.config.timer_entity,
            pressure_start_bar=self.config.pressure_start_bar,
            shot_idle_seconds=self.config.shot_idle_seconds,
        )

    def load(self) -> AppSettings:
        """Load settings."""
        defaults = self.defaults()
        if not self.path.exists():
            return defaults

        data = json.loads(self.path.read_text())
        return AppSettings(
            pressure_entity=str(data.get("pressure_entity", defaults.pressure_entity)),
            weight_entity=str(data.get("weight_entity", defaults.weight_entity)),
            flow_entity=str(data.get("flow_entity", defaults.flow_entity)),
            timer_entity=str(data.get("timer_entity", defaults.timer_entity)),
            pressure_start_bar=float(data.get("pressure_start_bar", defaults.pressure_start_bar)),
            shot_idle_seconds=float(data.get("shot_idle_seconds", defaults.shot_idle_seconds)),
        )

    def save(self, settings: AppSettings) -> AppSettings:
        """Save settings."""
        self.path.write_text(json.dumps(asdict(settings), indent=2) + "\n")
        return settings
