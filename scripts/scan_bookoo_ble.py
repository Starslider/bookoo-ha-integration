#!/usr/bin/env python3
"""Scan nearby BLE devices and print likely Bookoo device addresses."""

from __future__ import annotations

import argparse
import asyncio

from bleak import BleakScanner

BOOKOO_SCALE_SERVICE = "00000ffe-0000-1000-8000-00805f9b34fb"
BOOKOO_EM_SERVICE = "00000fff-0000-1000-8000-00805f9b34fb"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scan for Bookoo BLE devices.")
    parser.add_argument("--seconds", type=float, default=15, help="Scan duration.")
    parser.add_argument("--all", action="store_true", help="Print all BLE devices.")
    args = parser.parse_args()

    print(f"Scanning for {args.seconds:g}s...")
    devices = await BleakScanner.discover(timeout=args.seconds, return_adv=True)

    rows = []
    for address, (device, advertisement) in sorted(devices.items()):
        name = device.name or advertisement.local_name or ""
        services = {service.lower() for service in advertisement.service_uuids}
        is_scale = BOOKOO_SCALE_SERVICE in services
        is_em = BOOKOO_EM_SERVICE in services
        is_bookoo_name = "bookoo" in name.lower()
        if not args.all and not (is_scale or is_em or is_bookoo_name):
            continue

        if is_scale:
            kind = "Smart Scale Mini"
        elif is_em:
            kind = "Espresso Monitor"
        elif is_bookoo_name:
            kind = "Bookoo candidate"
        else:
            kind = "Other"

        rows.append(
            {
                "address": address,
                "name": name or "(no name)",
                "rssi": advertisement.rssi,
                "kind": kind,
                "services": ", ".join(sorted(services)) or "-",
            }
        )

    if not rows:
        print("No Bookoo-looking BLE devices found.")
        print("Make sure the Bookoo app is disconnected and the device is awake.")
        return

    for row in rows:
        print()
        print(f"{row['kind']}")
        print(f"  Address:  {row['address']}")
        print(f"  Name:     {row['name']}")
        print(f"  RSSI:     {row['rssi']}")
        print(f"  Services: {row['services']}")

    print()
    print("Use the Address value as the manual Bluetooth address in Home Assistant.")


if __name__ == "__main__":
    asyncio.run(main())
