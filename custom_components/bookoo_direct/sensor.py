"""Sensor entities for Bookoo Direct."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPressure, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import BookooEmClient, BookooScaleClient
from .const import CONF_DEVICE_TYPE, DEVICE_TYPE_EM, DEVICE_TYPE_SCALE
from .coordinator import BookooConfigEntry
from .entity import BookooEntity


@dataclass(frozen=True, kw_only=True)
class BookooSensorDescription(SensorEntityDescription):
    """Bookoo sensor description."""

    value_fn: Callable[[BookooScaleClient | BookooEmClient], int | float | None]


SCALE_SENSORS: tuple[BookooSensorDescription, ...] = (
    BookooSensorDescription(
        key="weight",
        translation_key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement="g",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda client: client.reading.weight_g if isinstance(client, BookooScaleClient) and client.reading else None,
    ),
    BookooSensorDescription(
        key="timer",
        translation_key="timer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda client: client.reading.timer_s if isinstance(client, BookooScaleClient) and client.reading else None,
    ),
    BookooSensorDescription(
        key="flow",
        translation_key="flow",
        native_unit_of_measurement="g/s",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda client: client.reading.flow_g_s if isinstance(client, BookooScaleClient) and client.reading else None,
    ),
    BookooSensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda client: client.reading.battery_pct if isinstance(client, BookooScaleClient) and client.reading else None,
    ),
)

EM_SENSORS: tuple[BookooSensorDescription, ...] = (
    BookooSensorDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.BAR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda client: client.reading.pressure_bar if isinstance(client, BookooEmClient) and client.reading else None,
    ),
    BookooSensorDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda client: client.reading.battery_pct if isinstance(client, BookooEmClient) and client.reading else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BookooConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bookoo sensors."""
    del hass
    coordinator = entry.runtime_data
    descriptions = SCALE_SENSORS if entry.data[CONF_DEVICE_TYPE] == DEVICE_TYPE_SCALE else EM_SENSORS
    async_add_entities(BookooSensor(coordinator, description) for description in descriptions)


class BookooSensor(BookooEntity, SensorEntity):
    """Bookoo sensor."""

    entity_description: BookooSensorDescription

    def __init__(
        self,
        coordinator,
        description: BookooSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int | float | None:
        """Return native value."""
        if self.coordinator.client is None:
            return None
        return self.entity_description.value_fn(self.coordinator.client)
