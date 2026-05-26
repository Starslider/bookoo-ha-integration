# Bookoo Grafana

Import:

```text
grafana/dashboards/bookoo-live-shot.json
```

After import:

1. Select your InfluxDB datasource in the dashboard variable.
2. Adjust the entity ID variables to match Home Assistant's actual `entity_id` tag values.
3. Set display device URL to kiosk mode.

Kiosk URL pattern:

```text
https://grafana.example.com/d/bookoo-live-shot/bookoo-live-shot?orgId=1&refresh=1s&from=now-2m&to=now&kiosk
```

The dashboard expects Home Assistant's classic InfluxDB schema where unit measurements are stored in measurements such as:

```text
bar
g
g/s
s
```

It also reads optional Shot Lab summaries from:

```text
bookoo_shots
```

If your Home Assistant InfluxDB schema differs, inspect the actual measurements in Grafana Explore and adjust the panel queries.

## Mock Data

Generate test data for the dashboard:

```sh
cd apps/shot_lab
export HA_TOKEN="mock-token"
export BOOKOO_INFLUX_ENABLED=true
export BOOKOO_INFLUX_HOST="influxdb.local"
export BOOKOO_INFLUX_PORT=8086
export BOOKOO_INFLUX_DATABASE="homeassistant"
python scripts/generate_mock_data.py --shots 12 --live --influx
```

Then open the dashboard with:

```text
from=now-2m
to=now
refresh=1s
```
