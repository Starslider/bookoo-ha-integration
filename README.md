# Bookoo Home Assistant Espresso Stack

This repository connects Bookoo espresso hardware to Home Assistant, records espresso shots, and provides live/analysis dashboards.

Primary target setup:

```text
Bookoo Smart Scale Mini  -> Home Assistant Bluetooth -> HA entities -> InfluxDB/Grafana
Bookoo Espresso Monitor  -> Home Assistant Bluetooth -> HA entities -> Shot Lab
```

The ESP32 MQTT bridge is included as a fallback if direct Home Assistant Bluetooth is unreliable.

## Contents

```text
custom_components/bookoo_direct/     Home Assistant Bluetooth integration
apps/shot_lab/                       Shot recorder, live UI, analysis app
grafana/dashboards/                  Importable Grafana live shot dashboard
docs/grafana.md                      Grafana and InfluxDB setup notes
src/                                 Optional ESP32 MQTT bridge firmware
include/                             ESP32 bridge configuration/protocol headers
scripts/deploy_ha_integration.sh     Manual HA custom component deploy helper
hacs.json                            HACS custom repository metadata
```

## Features

Home Assistant integration:

- Direct BLE connection through Home Assistant's Bluetooth stack
- Bookoo Smart Scale Mini sensors:
  - weight
  - timer
  - flow
  - battery
- Bookoo Smart Scale Mini buttons:
  - tare
  - start timer
  - stop timer
  - reset timer
  - tare and start
- Bookoo Espresso Monitor sensors:
  - pressure
  - battery

Shot Lab:

- Live machine-side shot view
- Configurable target yield and input dose
- Config page for Home Assistant entity IDs and shot detection thresholds
- Sensor status page showing latest values and freshness
- Automatic shot detection
- SQLite shot/sample storage
- Shot history and shot detail pages
- Basic extraction analysis and adjustment suggestions
- Mock mode for UI testing without hardware
- Optional InfluxDB shot-summary export for Grafana annotations/tables

Grafana:

- Importable live shot dashboard
- Live pressure, flow, weight, and timer panels
- Recent Shot Lab summaries when Influx export is enabled

## Recommended Architecture

For a Home Assistant Pi 5 near the espresso machine:

```text
Bookoo devices
  -> Pi 5 Bluetooth
  -> Home Assistant Bookoo Direct integration
  -> InfluxDB/Grafana for live dashboard
  -> Shot Lab for shot records and analysis
```

Use the ESP32 bridge only if Bluetooth from the Pi is unstable or out of range.

Important: BLE devices usually allow only one active client connection. Disconnect the Bookoo mobile app while Home Assistant or the ESP32 bridge is connected.

## Home Assistant Integration

The integration lives in:

```text
custom_components/bookoo_direct
```

### Manual Install

Copy the integration into your Home Assistant config directory:

```text
config/
  custom_components/
    bookoo_direct/
```

From this repo:

```sh
scripts/deploy_ha_integration.sh /path/to/homeassistant/config
```

Examples:

```sh
scripts/deploy_ha_integration.sh /config
scripts/deploy_ha_integration.sh /mnt/homeassistant/config
```

Then:

1. Restart Home Assistant.
2. Go to `Settings -> Devices & services`.
3. Click `Add integration`.
4. Search for `Bookoo Direct`.
5. Add the scale and EM when discovered.

### Bluetooth Discovery And Manual Address

Home Assistant should discover Bookoo devices automatically through its Bluetooth integration. If setup does not show the EM or scale, add it manually with the Bluetooth address.

In this project, the value you need for manual setup is the BLE Bluetooth address/MAC, for example:

```text
AA:BB:CC:DD:EE:FF
```

Ways to find it:

- Home Assistant Bluetooth page/logs
- nRF Connect mobile app
- LightBlue mobile app
- `bluetoothctl scan on` on Linux
- the helper script in this repo

Run the helper scanner on a machine with Bluetooth:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install bleak
python scripts/scan_bookoo_ble.py --seconds 20
```

Print all nearby BLE devices:

```sh
python scripts/scan_bookoo_ble.py --seconds 20 --all
```

Use the printed `Address` value in the Bookoo Direct manual setup form and select the correct device type.

### HACS Install

Once this repo is pushed to GitHub, the Home Assistant integration can be installed as a HACS custom repository.

In HACS:

```text
HACS -> Custom repositories -> Add repository URL -> Category: Integration
```

Then install `Bookoo Direct`, restart Home Assistant, and add the integration from:

```text
Settings -> Devices & services -> Add integration -> Bookoo Direct
```

HACS installs only the Home Assistant integration. It does not install Shot Lab, Grafana dashboards, or the ESP32 firmware.

## Home Assistant Entities

Expected entity examples after setup:

```text
sensor.bookoo_smart_scale_mini_weight
sensor.bookoo_smart_scale_mini_timer
sensor.bookoo_smart_scale_mini_flow
sensor.bookoo_smart_scale_mini_battery
sensor.bookoo_espresso_monitor_pressure
sensor.bookoo_espresso_monitor_battery
```

Actual entity IDs may differ depending on device names. Use Home Assistant's entity registry to confirm them, then configure Shot Lab and Grafana accordingly.

The Espresso Monitor is currently pressure + battery only. The published Bookoo EM protocol does not document temperature data, so this project does not expose a temperature entity until that is verified.

## Shot Lab

Shot Lab is a standalone Python web app in:

```text
apps/shot_lab
```

It subscribes to Home Assistant's WebSocket API, watches the Bookoo entities, detects shot start/end, records every sample into SQLite, and serves a local web UI.

### Run

Create a Home Assistant long-lived access token, then:

```sh
cd apps/shot_lab
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your-long-lived-token"
uvicorn bookoo_shot_lab.app:app --host 0.0.0.0 --port 8099
```

Open:

```text
http://localhost:8099
http://localhost:8099/live
http://localhost:8099/config
```

### Configuration

Shot Lab has a web configuration page:

```text
http://localhost:8099/config
```

Configure:

- input dose
- target yield
- pressure entity ID
- weight entity ID
- flow entity ID
- timer entity ID
- pressure threshold for shot start
- idle timeout for shot end

The config page also shows sensor status:

- latest value
- last update time
- status: `ok`, `stale`, `offline`, or `waiting`
- current mode: `Mock` or `Live`

### Environment Variables

Core:

```sh
HA_URL="http://homeassistant.local:8123"
HA_TOKEN="your-long-lived-token"
BOOKOO_SHOT_DB="bookoo_shots.sqlite3"
BOOKOO_RECIPE_FILE="bookoo_recipe.json"
BOOKOO_SETTINGS_FILE="bookoo_settings.json"
```

Defaults for entity IDs:

```sh
BOOKOO_PRESSURE_ENTITY="sensor.bookoo_em_pressure"
BOOKOO_WEIGHT_ENTITY="sensor.bookoo_scale_weight"
BOOKOO_FLOW_ENTITY="sensor.bookoo_scale_flow"
BOOKOO_TIMER_ENTITY="sensor.bookoo_scale_timer"
```

Shot detection defaults:

```sh
BOOKOO_PRESSURE_START_BAR=0.5
BOOKOO_SHOT_IDLE_SECONDS=4
```

Mock/live mode:

```sh
BOOKOO_MOCK_MODE=true
```

`BOOKOO_MOCK_MODE` is set automatically by the mock live script. Leave it unset for live Home Assistant mode.

### Mock Testing

Generate SQLite shot history without hardware:

```sh
cd apps/shot_lab
export HA_TOKEN="mock-token"
python scripts/generate_mock_data.py --shots 12
uvicorn bookoo_shot_lab.app:app --host 0.0.0.0 --port 8099
```

Run a fake live shot stream:

```sh
cd apps/shot_lab
export HA_TOKEN="mock-token"
python scripts/mock_live_stream.py
```

Open:

```text
http://localhost:8099/live
```

## Grafana And InfluxDB

If Home Assistant already writes sensor state to InfluxDB, import:

```text
grafana/dashboards/bookoo-live-shot.json
```

Dashboard defaults:

```text
time range: now-2m to now
refresh: 1s
```

After import:

1. Select your InfluxDB datasource.
2. Adjust dashboard variables for your real Home Assistant `entity_id` tag values.
3. Open the dashboard in kiosk mode on a tablet or display near the machine.

See:

```text
docs/grafana.md
grafana/README.md
```

### Optional Shot Lab Influx Export

Shot Lab can write one summary point per completed shot into InfluxDB:

```sh
export BOOKOO_INFLUX_ENABLED=true
export BOOKOO_INFLUX_HOST="influxdb.local"
export BOOKOO_INFLUX_PORT=8086
export BOOKOO_INFLUX_DATABASE="homeassistant"
export BOOKOO_INFLUX_USERNAME=""
export BOOKOO_INFLUX_PASSWORD=""
```

Measurement:

```text
bookoo_shots
```

Fields include:

```text
shot_id
duration_s
final_weight_g
max_pressure_bar
avg_pressure_bar
avg_flow_g_s
input_dose_g
target_yield_g
brew_ratio
yield_error_g
pressure_range_bar
sample_count
suggestion
```

Backfill existing SQLite shots:

```sh
cd apps/shot_lab
PYTHONPATH=. python scripts/export_influx.py
```

Generate mock Influx data for Grafana:

```sh
cd apps/shot_lab
export HA_TOKEN="mock-token"
export BOOKOO_INFLUX_ENABLED=true
export BOOKOO_INFLUX_HOST="influxdb.local"
export BOOKOO_INFLUX_PORT=8086
export BOOKOO_INFLUX_DATABASE="homeassistant"
python scripts/generate_mock_data.py --shots 12 --live --influx
```

## Optional ESP32 MQTT Bridge

The ESP32 bridge is an alternative data path:

```text
Bookoo devices -> ESP32 BLE -> MQTT -> Home Assistant / InfluxDB / Grafana
```

Use it if direct Home Assistant Bluetooth is unreliable.

Supported board profile:

```text
m5stack-atom
```

Firmware files:

```text
platformio.ini
src/main.cpp
include/config.example.h
include/bookoo_protocol.h
```

Build:

```sh
pio run -t upload
pio device monitor
```

Before building:

```sh
cp include/config.example.h include/config.h
```

Configure WiFi/MQTT and, ideally, static BLE addresses:

```cpp
#define WIFI_SSID "your-wifi"
#define WIFI_PASSWORD "your-wifi-password"
#define MQTT_HOST "192.168.1.10"

#define BOOKOO_SCALE_ADDRESS "aa:bb:cc:dd:ee:ff"
#define BOOKOO_EM_ADDRESS "11:22:33:44:55:66"
```

MQTT topics:

```text
bookoo/bridge/status
bookoo/scale/state
bookoo/scale/command
bookoo/em/state
```

Scale command payloads:

```text
tare
start_timer
stop_timer
reset_timer
tare_and_start
```

The EM is treated as a sensor only.

## BLE Protocol Notes

The implementation follows Bookoo's published protocol notes:

- Scale service `0x0FFE`
- Scale weight characteristic `0xFF11`
- Scale command characteristic `0xFF12`
- EM service `0x0FFF`
- EM extraction data characteristic `0xFF02`

EM temperature is not implemented because it is not documented in the public EM protocol.

## Troubleshooting

Device not discovered:

- Make sure Bluetooth is enabled in Home Assistant.
- Keep the Bookoo app disconnected.
- Move the Pi/adapter closer to the machine.
- Restart the Bookoo device and Home Assistant.

Entities exist but Shot Lab does not update:

- Open `/config`.
- Confirm the entity IDs match Home Assistant exactly.
- Check sensor status freshness.
- Confirm `HA_URL` and `HA_TOKEN`.

Grafana panels are empty:

- Confirm HA is writing these entities into InfluxDB.
- Use Grafana Explore to inspect measurement names.
- Adjust dashboard variables for entity IDs.
- Adjust queries if your Influx schema differs from the default HA schema.

Shot detection is wrong:

- Tune pressure start threshold on `/config`.
- Tune idle seconds on `/config`.
- Confirm the scale timer entity updates during extraction.

## Development Checks

Python syntax checks:

```sh
python3 -m compileall custom_components/bookoo_direct apps/shot_lab/bookoo_shot_lab apps/shot_lab/scripts
```

Grafana JSON validation:

```sh
python3 -m json.tool grafana/dashboards/bookoo-live-shot.json
```

## Current Limitations

- The Home Assistant integration has not been runtime-tested against real Bookoo hardware in this workspace.
- EM temperature is not exposed because public protocol documentation only confirms pressure and battery.
- Shot Lab is currently a standalone Python app. It is not yet packaged as a Home Assistant add-on.
- The ESP32 bridge is optional and should not be connected to the same BLE devices at the same time as Home Assistant.
