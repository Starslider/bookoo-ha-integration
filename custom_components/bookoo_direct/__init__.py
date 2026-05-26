"""Bookoo Direct integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import BookooConfigEntry, BookooCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: BookooConfigEntry) -> bool:
    """Set up Bookoo Direct from a config entry."""
    coordinator = BookooCoordinator(hass, entry)
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BookooConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.async_shutdown()
    return unload_ok
