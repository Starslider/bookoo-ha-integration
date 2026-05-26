"""BLE clients for Bookoo devices."""

from __future__ import annotations

import logging
from collections.abc import Callable

from bleak import BleakClient, BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

from .const import (
    BOOKOO_EM_DATA_UUID,
    BOOKOO_SCALE_COMMAND_UUID,
    BOOKOO_SCALE_WEIGHT_UUID,
    SCALE_CMD_RESET_TIMER,
    SCALE_CMD_START_TIMER,
    SCALE_CMD_STOP_TIMER,
    SCALE_CMD_TARE,
    SCALE_CMD_TARE_AND_START,
)
from .protocol import EmReading, ScaleReading, decode_em, decode_scale

_LOGGER = logging.getLogger(__name__)


class BookooBleClient:
    """Base BLE client."""

    notify_uuid: str
    command_uuid: str

    def __init__(
        self,
        device: BLEDevice,
        name: str,
        update_callback: Callable[[], None],
    ) -> None:
        self.device = device
        self.address = device.address
        self.name = name
        self._update_callback = update_callback
        self._client: BleakClient | None = None
        self.connected = False

    async def connect(self) -> None:
        """Connect and subscribe to notifications."""
        if self.connected and self._client is not None and self._client.is_connected:
            return

        self._client = BleakClient(
            self.device,
            disconnected_callback=self._disconnected,
        )
        await self._client.connect()
        await self._client.start_notify(self.notify_uuid, self._notification)
        self.connected = True
        self._update_callback()

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        self.connected = False
        if self._client is not None and self._client.is_connected:
            await self._client.disconnect()

    async def write_command(self, payload: bytes) -> None:
        """Write a command to the device."""
        await self.connect()
        if self._client is None:
            raise BleakError("Client unavailable")
        await self._client.write_gatt_char(self.command_uuid, payload, response=False)

    def _disconnected(self, _client: BleakClient) -> None:
        self.connected = False
        self._update_callback()

    def _notification(
        self,
        _characteristic: BleakGATTCharacteristic,
        data: bytearray,
    ) -> None:
        raise NotImplementedError


class BookooScaleClient(BookooBleClient):
    """Smart Scale Mini BLE client."""

    notify_uuid = BOOKOO_SCALE_WEIGHT_UUID
    command_uuid = BOOKOO_SCALE_COMMAND_UUID

    reading: ScaleReading | None = None

    def _notification(
        self,
        _characteristic: BleakGATTCharacteristic,
        data: bytearray,
    ) -> None:
        reading = decode_scale(bytes(data))
        if reading is None:
            _LOGGER.debug("Ignoring invalid scale packet from %s: %s", self.address, data.hex())
            return

        self.reading = reading
        self._update_callback()

    async def tare(self) -> None:
        await self.write_command(SCALE_CMD_TARE)

    async def start_timer(self) -> None:
        await self.write_command(SCALE_CMD_START_TIMER)

    async def stop_timer(self) -> None:
        await self.write_command(SCALE_CMD_STOP_TIMER)

    async def reset_timer(self) -> None:
        await self.write_command(SCALE_CMD_RESET_TIMER)

    async def tare_and_start(self) -> None:
        await self.write_command(SCALE_CMD_TARE_AND_START)


class BookooEmClient(BookooBleClient):
    """Espresso Monitor BLE client."""

    notify_uuid = BOOKOO_EM_DATA_UUID

    reading: EmReading | None = None

    def _notification(
        self,
        _characteristic: BleakGATTCharacteristic,
        data: bytearray,
    ) -> None:
        reading = decode_em(bytes(data))
        if reading is None:
            _LOGGER.debug("Ignoring invalid EM packet from %s: %s", self.address, data.hex())
            return

        self.reading = reading
        self._update_callback()
