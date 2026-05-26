"""Button entities for Bookoo Direct."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import BookooEmClient, BookooScaleClient
from .const import CONF_DEVICE_TYPE, DEVICE_TYPE_SCALE
from .coordinator import BookooConfigEntry
from .entity import BookooEntity


@dataclass(frozen=True, kw_only=True)
class BookooButtonDescription(ButtonEntityDescription):
    """Bookoo button description."""

    press_fn: Callable[[BookooScaleClient | BookooEmClient], Awaitable[None]]


SCALE_BUTTONS: tuple[BookooButtonDescription, ...] = (
    BookooButtonDescription(
        key="tare",
        translation_key="tare",
        press_fn=lambda client: client.tare(),
    ),
    BookooButtonDescription(
        key="start_timer",
        translation_key="start_timer",
        press_fn=lambda client: client.start_timer(),
    ),
    BookooButtonDescription(
        key="stop_timer",
        translation_key="stop_timer",
        press_fn=lambda client: client.stop_timer(),
    ),
    BookooButtonDescription(
        key="reset_timer",
        translation_key="reset_timer",
        press_fn=lambda client: client.reset_timer(),
    ),
    BookooButtonDescription(
        key="tare_and_start",
        translation_key="tare_and_start",
        press_fn=lambda client: client.tare_and_start(),
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: BookooConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bookoo buttons."""
    del hass
    if entry.data[CONF_DEVICE_TYPE] != DEVICE_TYPE_SCALE:
        return

    coordinator = entry.runtime_data
    async_add_entities(BookooButton(coordinator, description) for description in SCALE_BUTTONS)


class BookooButton(BookooEntity, ButtonEntity):
    """Bookoo button."""

    entity_description: BookooButtonDescription

    def __init__(
        self,
        coordinator,
        description: BookooButtonDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Press the button."""
        if self.coordinator.client is None:
            await self.coordinator.async_request_refresh()
        if self.coordinator.client is None:
            return
        await self.entity_description.press_fn(self.coordinator.client)
