# Bookoo Shot Lab

Standalone local app for recording and reviewing espresso shots from Home Assistant Bookoo entities.

The app connects to Home Assistant's WebSocket API, listens to state changes from the Bookoo pressure/weight/flow/timer sensors, detects shot start/end, stores every sample in SQLite, and serves a small web UI.

## Run

Create a Home Assistant long-lived access token, then run:

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
```

Live machine-side display:

```text
http://localhost:8099/live
```

The live page refreshes twice per second and shows the current pressure, yield, flow, timer, and live curves.

You can set the active target yield from the web UI. The active target is stored in:

```text
bookoo_recipe.json
```

Override the path:

```sh
export BOOKOO_RECIPE_FILE="/config/bookoo_recipe.json"
```

## Mock Data

Generate local SQLite shot history without hardware:

```sh
cd apps/shot_lab
export HA_TOKEN="mock-token"
python scripts/generate_mock_data.py --shots 12
uvicorn bookoo_shot_lab.app:app --host 0.0.0.0 --port 8099
```

Then open:

```text
http://localhost:8099
```

Run a fake live shot display:

```sh
cd apps/shot_lab
export HA_TOKEN="mock-token"
python scripts/mock_live_stream.py
```

Then open:

```text
http://localhost:8099/live
```

Mock vs live mode is controlled by `BOOKOO_MOCK_MODE`:

- live mode: run `uvicorn bookoo_shot_lab.app:app ...` with `BOOKOO_MOCK_MODE` unset
- mock mode: run `scripts/mock_live_stream.py`, which sets `BOOKOO_MOCK_MODE=true`

The current mode is visible on `/config` and returned by `/api/status`.

Generate mock data into InfluxDB for Grafana:

```sh
cd apps/shot_lab
export HA_TOKEN="mock-token"
export BOOKOO_INFLUX_ENABLED=true
export BOOKOO_INFLUX_HOST="influxdb.local"
export BOOKOO_INFLUX_PORT=8086
export BOOKOO_INFLUX_DATABASE="homeassistant"
python scripts/generate_mock_data.py --shots 12 --live --influx
```

The script writes Home Assistant-style raw measurements (`bar`, `g`, `g/s`, `s`) plus Shot Lab summaries (`bookoo_shots`).

## Entity Configuration

Defaults:

```sh
BOOKOO_PRESSURE_ENTITY=sensor.bookoo_em_pressure
BOOKOO_WEIGHT_ENTITY=sensor.bookoo_scale_weight
BOOKOO_FLOW_ENTITY=sensor.bookoo_scale_flow
BOOKOO_TIMER_ENTITY=sensor.bookoo_scale_timer
```

Override these if Home Assistant creates different entity IDs:

```sh
export BOOKOO_PRESSURE_ENTITY="sensor.bookoo_espresso_monitor_pressure"
export BOOKOO_WEIGHT_ENTITY="sensor.bookoo_smart_scale_mini_weight"
export BOOKOO_FLOW_ENTITY="sensor.bookoo_smart_scale_mini_flow"
export BOOKOO_TIMER_ENTITY="sensor.bookoo_smart_scale_mini_timer"
```

## Shot Detection

The app starts a shot when either:

- pressure is at or above `BOOKOO_PRESSURE_START_BAR`, default `0.5`
- scale timer is greater than `0.2s`

It ends a shot after `BOOKOO_SHOT_IDLE_SECONDS`, default `4`, without activity.

## Storage

Default database:

```text
bookoo_shots.sqlite3
```

Override:

```sh
export BOOKOO_SHOT_DB="/config/bookoo_shots.sqlite3"
```

## Optional Grafana Shot Summaries

Shot Lab can also write one summary point per shot into InfluxDB. This is useful for Grafana annotations and recent-shot tables.

For InfluxDB 1.x or a 1.x-compatible endpoint:

```sh
export BOOKOO_INFLUX_ENABLED=true
export BOOKOO_INFLUX_HOST="influxdb.local"
export BOOKOO_INFLUX_PORT=8086
export BOOKOO_INFLUX_DATABASE="homeassistant"
export BOOKOO_INFLUX_USERNAME=""
export BOOKOO_INFLUX_PASSWORD=""
```

The app writes measurement:

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
pressure_range_bar
sample_count
suggestion
```

To backfill existing SQLite shots into Influx:

```sh
PYTHONPATH=. python scripts/export_influx.py
```
