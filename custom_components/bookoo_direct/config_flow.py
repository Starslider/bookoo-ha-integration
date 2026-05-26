"""Config flow for Bookoo Direct."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    BOOKOO_EM_SERVICE_UUID,
    BOOKOO_SCALE_SERVICE_UUID,
    CONF_DEVICE_TYPE,
    DEVICE_TYPE_EM,
    DEVICE_TYPE_SCALE,
    DOMAIN,
)


def _normalize_uuid(uuid: str) -> str:
    return uuid.lower()


def _device_type_from_service_info(
    service_info: BluetoothServiceInfoBleak,
) -> str | None:
    """Infer the Bookoo device type from advertised service UUIDs."""
    uuids = {_normalize_uuid(uuid) for uuid in service_info.service_uuids}
    if BOOKOO_SCALE_SERVICE_UUID in uuids:
        return DEVICE_TYPE_SCALE
    if BOOKOO_EM_SERVICE_UUID in uuids:
        return DEVICE_TYPE_EM
    return None


def _device_label(service_info: BluetoothServiceInfoBleak, device_type: str) -> str:
    label = "Smart Scale Mini" if device_type == DEVICE_TYPE_SCALE else "Espresso Monitor"
    name = service_info.name or "Bookoo"
    return f"{name} {label} ({service_info.address})"


class BookooDirectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bookoo Direct."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            service_info = self._discovered[address]
            device_type = _device_type_from_service_info(service_info)
            if device_type is None:
                return self.async_abort(reason="unsupported_device")

            await self.async_set_unique_id(format_mac(address))
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=_device_label(service_info, device_type).rsplit(" (", 1)[0],
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: service_info.name or "Bookoo",
                    CONF_DEVICE_TYPE: device_type,
                },
            )

        for service_info in async_discovered_service_info(self.hass):
            device_type = _device_type_from_service_info(service_info)
            if device_type is not None:
                self._discovered[service_info.address] = service_info

        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        options = [
            SelectOptionDict(
                value=address,
                label=_device_label(service_info, _device_type_from_service_info(service_info) or DEVICE_TYPE_SCALE),
            )
            for address, service_info in self._discovered.items()
        ]

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): SelectSelector(
                        SelectSelectorConfig(
                            options=options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_bluetooth(
        self,
        discovery_info: BluetoothServiceInfoBleak,
    ) -> ConfigFlowResult:
        """Handle Bluetooth discovery."""
        device_type = _device_type_from_service_info(discovery_info)
        if device_type is None:
            return self.async_abort(reason="unsupported_device")

        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {
            CONF_NAME: discovery_info.name or "Bookoo",
        }
        self._discovered[discovery_info.address] = discovery_info
        self._set_confirm_only()
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery."""
        address = next(iter(self._discovered))
        service_info = self._discovered[address]
        device_type = _device_type_from_service_info(service_info)
        if device_type is None:
            return self.async_abort(reason="unsupported_device")

        if user_input is not None:
            return self.async_create_entry(
                title=_device_label(service_info, device_type).rsplit(" (", 1)[0],
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: service_info.name or "Bookoo",
                    CONF_DEVICE_TYPE: device_type,
                },
            )

        return self.async_show_form(step_id="bluetooth_confirm")
