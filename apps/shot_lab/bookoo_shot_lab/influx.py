"""Optional InfluxDB writer for Grafana shot summaries."""

from __future__ import annotations

import logging

from .config import Config

_LOGGER = logging.getLogger(__name__)


class ShotInfluxWriter:
    """Write shot summary points to InfluxDB 1.x-compatible APIs."""

    def __init__(self, config: Config) -> None:
        self.enabled = config.influx_enabled
        self.client: InfluxDBClient | None = None
        if not self.enabled:
            return

        try:
            from influxdb import InfluxDBClient
        except ImportError as ex:
            raise RuntimeError(
                "Install the influxdb package or disable BOOKOO_INFLUX_ENABLED."
            ) from ex

        self.client = InfluxDBClient(
            host=config.influx_host,
            port=config.influx_port,
            username=config.influx_username or None,
            password=config.influx_password or None,
            database=config.influx_database,
            ssl=config.influx_ssl,
            verify_ssl=config.influx_verify_ssl,
        )

    def write_shot(self, shot_id: int, shot: dict, analysis: dict) -> None:
        """Write one shot summary point."""
        if not self.enabled or self.client is None:
            return

        metrics = analysis["metrics"]
        suggestions = analysis["suggestions"]
        point = {
            "measurement": "bookoo_shots",
            "tags": {
                "shot_id": str(shot_id),
            },
            "time": int(shot["started_at"] * 1_000_000_000),
            "fields": {
                "shot_id": shot_id,
                "duration_s": float(shot["duration_s"]),
                "sample_count": int(shot["sample_count"]),
                "suggestion": " ".join(suggestions),
            },
        }

        for field in (
            "final_weight_g",
            "max_pressure_bar",
            "avg_pressure_bar",
            "avg_flow_g_s",
            "input_dose_g",
            "target_yield_g",
        ):
            if shot.get(field) is not None:
                point["fields"][field] = float(shot[field])

        if metrics.get("pressure_range_bar") is not None:
            point["fields"]["pressure_range_bar"] = float(metrics["pressure_range_bar"])
        if metrics.get("brew_ratio") is not None:
            point["fields"]["brew_ratio"] = float(metrics["brew_ratio"])
        if metrics.get("yield_error_g") is not None:
            point["fields"]["yield_error_g"] = float(metrics["yield_error_g"])

        try:
            self.client.write_points([point], time_precision="n")
        except Exception:
            _LOGGER.exception("Failed to write shot %s summary to InfluxDB", shot_id)
