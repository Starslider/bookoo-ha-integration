"""Base entities for Bookoo Direct."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_TYPE, DEVICE_TYPE_EM, DOMAIN
from .coordinator import BookooCoordinator


class BookooEntity(CoordinatorEntity[BookooCoordinator]):
    """Base Bookoo entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BookooCoordinator, key: str) -> None:
        super().__init__(coordinator)
        model = (
            "Espresso Monitor"
            if coordinator.config_entry.data[CONF_DEVICE_TYPE] == DEVICE_TYPE_EM
            else "Smart Scale Mini"
        )
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id or coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.title,
            manufacturer="Bookoo",
            model=model,
        )

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.coordinator.client is not None and self.coordinator.client.connected
