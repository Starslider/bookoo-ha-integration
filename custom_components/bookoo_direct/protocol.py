"""Bookoo BLE protocol decoding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ScaleReading:
    """Decoded Smart Scale Mini reading."""

    timer_s: float
    weight_g: float
    flow_g_s: float
    battery_pct: int
    standby_min: int
    buzzer_gear: int
    flow_smoothing: bool


@dataclass(slots=True)
class EmReading:
    """Decoded Espresso Monitor reading."""

    pressure_bar: float
    battery_pct: int


def checksum_ok(data: bytes) -> bool:
    """Return whether the packet's XOR checksum is valid."""
    if len(data) < 2:
        return False

    checksum = 0
    for byte in data[:-1]:
        checksum ^= byte
    return checksum == data[-1]


def _u24(high: int, mid: int, low: int) -> int:
    return (high << 16) | (mid << 8) | low


def _signed(value: int, sign: int) -> int:
    return -value if sign == 1 else value


def decode_scale(data: bytes) -> ScaleReading | None:
    """Decode a Smart Scale Mini notification packet."""
    if len(data) != 20 or data[0] != 0x03 or data[1] != 0x0B:
        return None
    if not checksum_ok(data):
        return None

    timer_ms = _u24(data[2], data[3], data[4])
    weight_raw = _u24(data[7], data[8], data[9])
    flow_raw = (data[11] << 8) | data[12]
    standby_min = (data[14] << 8) | data[15]

    return ScaleReading(
        timer_s=timer_ms / 1000,
        weight_g=_signed(weight_raw, data[6]) / 100,
        flow_g_s=_signed(flow_raw, data[10]) / 100,
        battery_pct=data[13],
        standby_min=standby_min,
        buzzer_gear=data[16],
        flow_smoothing=data[17] == 1,
    )


def decode_em(data: bytes) -> EmReading | None:
    """Decode an Espresso Monitor notification packet."""
    if len(data) < 10 or data[0] != 0x02 or data[1] != 0x1B:
        return None

    pressure_raw = (data[4] << 8) | data[5]
    return EmReading(
        pressure_bar=pressure_raw / 100,
        battery_pct=data[6],
    )
