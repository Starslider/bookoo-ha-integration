"""Data coordinator for Bookoo Direct."""

from __future__ import annotations

from datetime import timedelta
import logging

from bleak.exc import BleakError

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .client import BookooBleClient, BookooEmClient, BookooScaleClient
from .const import CONF_DEVICE_TYPE, DEVICE_TYPE_EM, DEVICE_TYPE_SCALE, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

type BookooConfigEntry = ConfigEntry[BookooCoordinator]


class BookooCoordinator(DataUpdateCoordinator[None]):
    """Coordinate a Bookoo BLE connection."""

    config_entry: BookooConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BookooConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            config_entry=entry,
        )
        self._entry = entry
        self.client: BookooBleClient | None = None

    async def _async_update_data(self) -> None:
        if self.client is None:
            device = async_ble_device_from_address(
                self.hass,
                self._entry.data[CONF_ADDRESS],
                connectable=True,
            )
            if device is None:
                _LOGGER.debug("Bookoo device not currently discoverable: %s", self._entry.data[CONF_ADDRESS])
                return

            name = self._entry.data.get(CONF_NAME) or device.name or "Bookoo"
            if self._entry.data[CONF_DEVICE_TYPE] == DEVICE_TYPE_SCALE:
                self.client = BookooScaleClient(device, name, self.async_update_listeners)
            elif self._entry.data[CONF_DEVICE_TYPE] == DEVICE_TYPE_EM:
                self.client = BookooEmClient(device, name, self.async_update_listeners)

        if self.client is None or self.client.connected:
            return

        try:
            await self.client.connect()
        except (BleakError, TimeoutError) as ex:
            _LOGGER.debug("Could not connect to Bookoo device %s: %s", self._entry.data[CONF_ADDRESS], ex)

    async def async_shutdown(self) -> None:
        """Disconnect the BLE client."""
        if self.client is not None:
            await self.client.disconnect()
