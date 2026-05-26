# Grafana / InfluxDB Setup

Use this if Home Assistant is already connected to InfluxDB and Grafana.

## Data Flow

```text
Bookoo Smart Scale Mini -> Home Assistant Bluetooth -> HA entities -> InfluxDB -> Grafana
Bookoo Espresso Monitor -> Home Assistant Bluetooth -> HA entities -> InfluxDB -> Grafana
```

## Home Assistant InfluxDB Configuration

Add the Bookoo entities to your existing `influxdb:` include list. Adjust entity IDs after Home Assistant creates them.

```yaml
influxdb:
  include:
    entities:
      - sensor.bookoo_smart_scale_mini_weight
      - sensor.bookoo_smart_scale_mini_flow
      - sensor.bookoo_smart_scale_mini_timer
      - sensor.bookoo_smart_scale_mini_battery
      - sensor.bookoo_espresso_monitor_pressure
      - sensor.bookoo_espresso_monitor_battery
```

If you already include all sensors, no HA config change is needed.

## Current Shot Dashboard

Create a Grafana dashboard with a short relative time range:

```text
now-2m to now
```

Suggested panels:

- Pressure, time series, unit `bar`
- Weight, time series, unit `g`
- Flow, time series, unit `g/s`
- Timer, stat panel, unit `s`
- Current pressure, stat panel, unit `bar`
- Current yield, stat panel, unit `g`

Set refresh to:

```text
1s
```

## InfluxQL Examples

These examples match the classic Home Assistant InfluxDB schema.

Pressure:

```sql
SELECT mean("value")
FROM "bar"
WHERE ("entity_id" = 'bookoo_espresso_monitor_pressure')
  AND $timeFilter
GROUP BY time($__interval) fill(previous)
```

Weight:

```sql
SELECT mean("value")
FROM "g"
WHERE ("entity_id" = 'bookoo_smart_scale_mini_weight')
  AND $timeFilter
GROUP BY time($__interval) fill(previous)
```

Flow:

```sql
SELECT mean("value")
FROM "g/s"
WHERE ("entity_id" = 'bookoo_smart_scale_mini_flow')
  AND $timeFilter
GROUP BY time($__interval) fill(previous)
```

Timer:

```sql
SELECT last("value")
FROM "s"
WHERE ("entity_id" = 'bookoo_smart_scale_mini_timer')
  AND $timeFilter
```

Depending on your HA InfluxDB configuration, measurements may instead be `°C`, `state`, `sensor`, or entity-name based. Use Grafana Explore to inspect the actual measurement names after a test shot.

## Flux Examples

If you use InfluxDB 2 / Flux:

Pressure:

```flux
from(bucket: "homeassistant")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "bar")
  |> filter(fn: (r) => r["entity_id"] == "bookoo_espresso_monitor_pressure")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
```

Weight:

```flux
from(bucket: "homeassistant")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "g")
  |> filter(fn: (r) => r["entity_id"] == "bookoo_smart_scale_mini_weight")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
```

Flow:

```flux
from(bucket: "homeassistant")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "g/s")
  |> filter(fn: (r) => r["entity_id"] == "bookoo_smart_scale_mini_flow")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)
```

## Machine-Side Display

For a dedicated display near the machine:

- open the Grafana dashboard on a tablet
- set the dashboard to kiosk mode
- set refresh to `1s`
- set time range to `now-2m to now`

Grafana kiosk URL pattern:

```text
https://grafana.example.com/d/<dashboard_uid>/<slug>?orgId=1&refresh=1s&from=now-2m&to=now&kiosk
```

## Shot History

InfluxDB is good for live curves and history. For espresso-specific shot records, keep using `apps/shot_lab` as the structured shot log, or extend it later to write shot summary annotations back into Grafana.

The Shot Lab app now supports writing one `bookoo_shots` point per completed shot into InfluxDB. Enable it with:

```sh
export BOOKOO_INFLUX_ENABLED=true
export BOOKOO_INFLUX_HOST="influxdb.local"
export BOOKOO_INFLUX_PORT=8086
export BOOKOO_INFLUX_DATABASE="homeassistant"
```

Import the starter Grafana dashboard:

```text
grafana/dashboards/bookoo-live-shot.json
```

After import, select your InfluxDB datasource and adjust the entity ID variables at the top of the dashboard.

For file provisioning, see:

```text
grafana/provisioning-dashboard-provider.example.yaml
```
