"""Bookoo Shot Lab web app."""

from __future__ import annotations

import asyncio
import datetime as dt
import os

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse

from .analyzer import analyze_shot
from .collector import ShotCollector
from .config import load_config
from .influx import ShotInfluxWriter
from .recipe import Recipe, RecipeStore
from .settings import AppSettings, SettingsStore
from .storage import Storage

config = load_config()
storage = Storage(config.db_path)
influx_writer = ShotInfluxWriter(config)
recipe_store = RecipeStore(config.recipe_path)
settings_store = SettingsStore(config.settings_path, config)
collector = ShotCollector(config, storage, influx_writer, recipe_store, settings_store)
mock_mode = os.environ.get("BOOKOO_MOCK_MODE", "").lower() in {"1", "true", "yes", "on"}

app = FastAPI(title="Bookoo Shot Lab")


@app.on_event("startup")
async def startup() -> None:
    """Start the Home Assistant collector."""
    if mock_mode:
        return
    asyncio.create_task(collector.run_forever())


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    """Render the shot list."""
    shots = storage.list_shots()
    rows = "\n".join(
        f"""
        <tr>
          <td><a href="/shots/{shot['id']}">#{shot['id']}</a></td>
          <td>{_format_ts(shot['started_at'])}</td>
          <td>{shot['duration_s']:.1f}s</td>
          <td>{_fmt(shot['final_weight_g'], 'g')}</td>
          <td>{_fmt(shot['max_pressure_bar'], 'bar')}</td>
          <td>{_fmt(shot['avg_flow_g_s'], 'g/s')}</td>
          <td>{shot['sample_count']}</td>
        </tr>
        """
        for shot in shots
    )
    return _page(
        "Bookoo Shot Lab",
        f"""
        <h1>Bookoo Shot Lab</h1>
        <p class="muted">Recording from Home Assistant entities configured in the app environment.</p>
        <p><a href="/live">Open live shot view</a> · <a href="/config">Configuration</a></p>
        {_recipe_form("/")}
        <table>
          <thead>
            <tr>
              <th>Shot</th><th>Started</th><th>Duration</th><th>Yield</th><th>Max pressure</th><th>Avg flow</th><th>Samples</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        """,
    )


@app.get("/api/shots")
async def api_shots() -> list[dict]:
    """Return recent shots."""
    return storage.list_shots()


@app.get("/api/current")
async def api_current() -> dict:
    """Return current live shot state."""
    status = collector.current_status()
    recipe = recipe_store.load()
    status["input_dose_g"] = recipe.input_dose_g
    status["target_yield_g"] = recipe.target_yield_g
    if status["weight_g"] is not None:
        status["yield_remaining_g"] = recipe.target_yield_g - status["weight_g"]
    else:
        status["yield_remaining_g"] = None
    return status


@app.get("/api/status")
async def api_status() -> dict:
    """Return app configuration and sensor status."""
    return _status_payload()


@app.get("/api/recipe")
async def api_recipe() -> dict:
    """Return active recipe."""
    return recipe_store.load().__dict__


@app.post("/api/recipe")
async def api_set_recipe(input_dose_g: float = Form(18.0), target_yield_g: float = Form(...)) -> dict:
    """Set active target yield and optional input dose."""
    recipe = recipe_store.save(Recipe(input_dose_g=input_dose_g, target_yield_g=target_yield_g))
    return recipe.__dict__


@app.post("/recipe", response_class=HTMLResponse)
async def set_recipe(
    input_dose_g: float = Form(18.0),
    target_yield_g: float = Form(...),
    redirect_to: str = Form("/"),
) -> str:
    """Set recipe from HTML form."""
    recipe_store.save(Recipe(input_dose_g=input_dose_g, target_yield_g=target_yield_g))
    return """
    <!doctype html>
    <meta http-equiv="refresh" content="0; url={redirect_to}" />
    <a href="{redirect_to}">Back</a>
    """.format(redirect_to=redirect_to)


@app.get("/config", response_class=HTMLResponse)
async def config_page() -> str:
    """Render configuration page."""
    settings = settings_store.load()
    recipe = recipe_store.load()
    status_rows = _sensor_status_rows()
    return _page(
        "Configuration",
        f"""
        <div class="topbar">
          <a href="/live">Live shot</a>
          <a href="/">Shot history</a>
        </div>
        <h1>Configuration</h1>
        <p class="muted">Changes are saved immediately and used by the collector without restarting the app.</p>
        <div class="metrics">
          <div><span>Mode</span><strong>{'Mock' if mock_mode else 'Live'}</strong></div>
          <div><span>Home Assistant</span><strong>{config.ha_url}</strong></div>
          <div><span>Database</span><strong>{storage.path}</strong></div>
        </div>
        <form class="settings" method="post" action="/config">
          <section>
            <h2>Shot Target</h2>
            <div class="form-grid">
              <label>Input dose <input type="number" step="0.1" min="0" name="input_dose_g" value="{recipe.input_dose_g:.1f}"></label>
              <label>Target yield <input type="number" step="0.1" min="0" name="target_yield_g" value="{recipe.target_yield_g:.1f}"></label>
            </div>
          </section>
          <section>
            <h2>Home Assistant Entities</h2>
            <div class="form-grid wide">
              <label>Pressure entity <input name="pressure_entity" value="{settings.pressure_entity}"></label>
              <label>Weight entity <input name="weight_entity" value="{settings.weight_entity}"></label>
              <label>Flow entity <input name="flow_entity" value="{settings.flow_entity}"></label>
              <label>Timer entity <input name="timer_entity" value="{settings.timer_entity}"></label>
            </div>
          </section>
          <section>
            <h2>Shot Detection</h2>
            <div class="form-grid">
              <label>Pressure start bar <input type="number" step="0.1" min="0" name="pressure_start_bar" value="{settings.pressure_start_bar:.1f}"></label>
              <label>Idle seconds <input type="number" step="0.5" min="0.5" name="shot_idle_seconds" value="{settings.shot_idle_seconds:.1f}"></label>
            </div>
          </section>
          <button type="submit">Save configuration</button>
        </form>
        <h2>Sensor Status</h2>
        <table>
          <thead><tr><th>Sensor</th><th>Entity</th><th>Latest value</th><th>Last update</th><th>Status</th></tr></thead>
          <tbody>{status_rows}</tbody>
        </table>
        """,
    )


@app.post("/config", response_class=HTMLResponse)
async def save_config_page(
    input_dose_g: float = Form(18.0),
    target_yield_g: float = Form(...),
    pressure_entity: str = Form(...),
    weight_entity: str = Form(...),
    flow_entity: str = Form(...),
    timer_entity: str = Form(...),
    pressure_start_bar: float = Form(0.5),
    shot_idle_seconds: float = Form(4.0),
) -> str:
    """Save configuration page."""
    recipe_store.save(Recipe(input_dose_g=input_dose_g, target_yield_g=target_yield_g))
    settings_store.save(
        AppSettings(
            pressure_entity=pressure_entity.strip(),
            weight_entity=weight_entity.strip(),
            flow_entity=flow_entity.strip(),
            timer_entity=timer_entity.strip(),
            pressure_start_bar=pressure_start_bar,
            shot_idle_seconds=shot_idle_seconds,
        )
    )
    return """
    <!doctype html>
    <meta http-equiv="refresh" content="0; url=/config" />
    <a href="/config">Back</a>
    """


@app.get("/api/shots/{shot_id}")
async def api_shot(shot_id: int) -> dict:
    """Return one shot with samples and analysis."""
    shot = storage.get_shot(shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="Shot not found")
    samples = storage.get_samples(shot_id)
    return {"shot": shot, "samples": samples, "analysis": analyze_shot(shot, samples)}


@app.get("/shots/{shot_id}", response_class=HTMLResponse)
async def shot_detail(shot_id: int) -> str:
    """Render one shot."""
    shot = storage.get_shot(shot_id)
    if shot is None:
        raise HTTPException(status_code=404, detail="Shot not found")
    samples = storage.get_samples(shot_id)
    analysis = analyze_shot(shot, samples)
    chart_points = _chart_points(samples)
    suggestions = "".join(f"<li>{suggestion}</li>" for suggestion in analysis["suggestions"])
    return _page(
        f"Shot #{shot_id}",
        f"""
        <p><a href="/">Back to shots</a></p>
        <h1>Shot #{shot_id}</h1>
        <div class="metrics">
          <div><span>Duration</span><strong>{shot['duration_s']:.1f}s</strong></div>
          <div><span>Target yield</span><strong>{_fmt(shot.get('target_yield_g'), 'g')}</strong></div>
          <div><span>Yield</span><strong>{_fmt(shot['final_weight_g'], 'g')}</strong></div>
          <div><span>Yield error</span><strong>{_fmt(analysis['metrics'].get('yield_error_g'), 'g')}</strong></div>
          <div><span>Max pressure</span><strong>{_fmt(shot['max_pressure_bar'], 'bar')}</strong></div>
          <div><span>Avg flow</span><strong>{_fmt(shot['avg_flow_g_s'], 'g/s')}</strong></div>
          <div><span>Brew ratio</span><strong>{_ratio(analysis['metrics'].get('brew_ratio'))}</strong></div>
        </div>
        <svg viewBox="0 0 900 360" role="img" aria-label="Shot chart">
          <rect x="0" y="0" width="900" height="360" fill="#fafafa"/>
          <line x1="50" y1="310" x2="860" y2="310" stroke="#999"/>
          <line x1="50" y1="30" x2="50" y2="310" stroke="#999"/>
          <polyline points="{chart_points['pressure']}" fill="none" stroke="#c2410c" stroke-width="3"/>
          <polyline points="{chart_points['flow']}" fill="none" stroke="#0369a1" stroke-width="3"/>
          <polyline points="{chart_points['weight']}" fill="none" stroke="#15803d" stroke-width="3"/>
          <text x="60" y="55" fill="#c2410c">pressure</text>
          <text x="60" y="80" fill="#0369a1">flow</text>
          <text x="60" y="105" fill="#15803d">weight</text>
        </svg>
        <h2>Adjustment suggestions</h2>
        <ul>{suggestions}</ul>
        """,
    )


@app.get("/live", response_class=HTMLResponse)
async def live() -> str:
    """Render live shot display."""
    return _page(
        "Live Shot",
        """
        <div class="topbar">
          <a href="/">Shot history</a>
          <a href="/config">Configuration</a>
          <strong id="status">Waiting</strong>
        </div>
        <h1>Live Shot</h1>
        <div class="metrics live">
          <div><span>Pressure</span><strong id="pressure">n/a</strong></div>
          <div><span>Yield</span><strong id="weight">n/a</strong></div>
          <div><span>Target</span><strong id="target">n/a</strong></div>
          <div><span>Remaining</span><strong id="remaining">n/a</strong></div>
          <div><span>Flow</span><strong id="flow">n/a</strong></div>
          <div><span>Timer</span><strong id="timer">n/a</strong></div>
        </div>
        """
        + _recipe_form("/live")
        + """
        <svg id="chart" viewBox="0 0 900 360" role="img" aria-label="Live shot chart">
          <rect x="0" y="0" width="900" height="360" fill="#fafafa"/>
          <line x1="50" y1="310" x2="860" y2="310" stroke="#999"/>
          <line x1="50" y1="30" x2="50" y2="310" stroke="#999"/>
          <polyline id="pressureLine" fill="none" stroke="#c2410c" stroke-width="3"/>
          <polyline id="flowLine" fill="none" stroke="#0369a1" stroke-width="3"/>
          <polyline id="weightLine" fill="none" stroke="#15803d" stroke-width="3"/>
          <text x="60" y="55" fill="#c2410c">pressure</text>
          <text x="60" y="80" fill="#0369a1">flow</text>
          <text x="60" y="105" fill="#15803d">weight</text>
        </svg>
        <script>
          function fmt(value, unit, digits = 2) {
            if (value === null || value === undefined) return "n/a";
            return Number(value).toFixed(digits) + " " + unit;
          }
          function points(samples, key, maxValue) {
            if (!samples.length) return "";
            const start = samples[0].timestamp;
            const end = samples[samples.length - 1].timestamp;
            const duration = Math.max(end - start, 1);
            return samples
              .filter((sample) => sample[key] !== null && sample[key] !== undefined)
              .map((sample) => {
                const x = 50 + ((sample.timestamp - start) / duration) * 810;
                const y = 310 - Math.min(Math.max(sample[key] / maxValue, 0), 1) * 260;
                return `${x.toFixed(1)},${y.toFixed(1)}`;
              })
              .join(" ");
          }
          async function refresh() {
            const response = await fetch("/api/current", { cache: "no-store" });
            const data = await response.json();
            document.getElementById("status").textContent = data.running ? "Recording" : "Waiting";
            document.getElementById("pressure").textContent = fmt(data.pressure_bar, "bar");
            document.getElementById("weight").textContent = fmt(data.weight_g, "g");
            document.getElementById("target").textContent = fmt(data.target_yield_g, "g");
            document.getElementById("remaining").textContent = fmt(data.yield_remaining_g, "g");
            document.getElementById("flow").textContent = fmt(data.flow_g_s, "g/s");
            document.getElementById("timer").textContent = fmt(data.timer_s, "s", 1);
            document.getElementById("pressureLine").setAttribute("points", points(data.samples, "pressure_bar", 12));
            document.getElementById("flowLine").setAttribute("points", points(data.samples, "flow_g_s", 5));
            document.getElementById("weightLine").setAttribute("points", points(data.samples, "weight_g", 60));
          }
          refresh();
          setInterval(refresh, 500);
        </script>
        """,
    )


def _chart_points(samples: list[dict]) -> dict[str, str]:
    if not samples:
        return {"pressure": "", "flow": "", "weight": ""}

    start = samples[0]["timestamp"]
    end = samples[-1]["timestamp"]
    duration = max(end - start, 1)

    def x(sample: dict) -> float:
        return 50 + ((sample["timestamp"] - start) / duration) * 810

    def series(key: str, max_value: float) -> str:
        points = []
        for sample in samples:
            value = sample.get(key)
            if value is None:
                continue
            y = 310 - min(max(value / max_value, 0), 1) * 260
            points.append(f"{x(sample):.1f},{y:.1f}")
        return " ".join(points)

    return {
        "pressure": series("pressure_bar", 12),
        "flow": series("flow_g_s", 5),
        "weight": series("weight_g", 60),
    }


def _page(title: str, body: str) -> str:
    return f"""
    <!doctype html>
    <html class="dark">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{title}</title>
        <style>
          :root {{
            color-scheme: dark;
            --bg: #111111;
            --panel: #1b1b1b;
            --panel-2: #242424;
            --line: #343434;
            --text: #f3f0ea;
            --muted: #a7a29a;
            --accent: #f59e0b;
            --pressure: #fb7185;
            --flow: #38bdf8;
            --weight: #34d399;
          }}
          * {{ box-sizing: border-box; }}
          body {{
            min-height: 100vh;
            margin: 0;
            padding: 28px;
            background: radial-gradient(circle at top left, #232018 0, var(--bg) 420px);
            color: var(--text);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          }}
          h1 {{ margin: 18px 0 8px; font-size: clamp(34px, 5vw, 64px); letter-spacing: 0; }}
          h2 {{ margin-top: 28px; }}
          table {{ border-collapse: collapse; width: 100%; overflow: hidden; border-radius: 8px; background: var(--panel); }}
          th, td {{ border-bottom: 1px solid var(--line); padding: 12px; text-align: left; }}
          th {{ background: var(--panel-2); color: var(--muted); font-weight: 600; }}
          tr:last-child td {{ border-bottom: 0; }}
          a {{ color: #7dd3fc; text-decoration: none; }}
          a:hover {{ text-decoration: underline; }}
          .muted {{ color: var(--muted); }}
          .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
            margin: 20px 0;
          }}
          .metrics div {{
            min-height: 98px;
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px;
            background: linear-gradient(180deg, var(--panel-2), var(--panel));
          }}
          .metrics span {{ display: block; color: var(--muted); font-size: 13px; }}
          .metrics strong {{ display: block; margin-top: 6px; font-size: 26px; font-weight: 750; }}
          .metrics.live {{ grid-template-columns: repeat(6, minmax(130px, 1fr)); }}
          .metrics.live strong {{ font-size: clamp(28px, 4vw, 52px); line-height: 1; }}
          .topbar {{ display: flex; justify-content: space-between; align-items: center; gap: 16px; }}
          .topbar strong {{
            border: 1px solid var(--line);
            border-radius: 999px;
            padding: 8px 14px;
            background: rgba(245, 158, 11, .14);
            color: #fbbf24;
          }}
          form.recipe {{
            display: flex;
            flex-wrap: wrap;
            align-items: end;
            gap: 12px;
            margin: 18px 0 24px;
            padding: 14px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: rgba(27, 27, 27, .9);
          }}
          form.recipe label {{ display: grid; gap: 6px; font-size: 13px; color: var(--muted); }}
          form.recipe input {{
            width: 130px;
            border: 1px solid #4a4a4a;
            border-radius: 7px;
            padding: 10px;
            background: #0f0f0f;
            color: var(--text);
            font: inherit;
          }}
          form.recipe button {{
            border: 1px solid #d97706;
            border-radius: 7px;
            padding: 11px 16px;
            background: #d97706;
            color: #111;
            font: inherit;
            font-weight: 700;
            cursor: pointer;
          }}
          form.settings {{
            display: grid;
            gap: 18px;
            margin: 18px 0 28px;
            padding: 18px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: rgba(27, 27, 27, .92);
          }}
          form.settings section {{ display: grid; gap: 10px; }}
          form.settings h2 {{ margin: 0; font-size: 18px; }}
          .form-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }}
          .form-grid.wide {{ grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }}
          form.settings label {{ display: grid; gap: 6px; color: var(--muted); font-size: 13px; }}
          form.settings input {{
            width: 100%;
            border: 1px solid #4a4a4a;
            border-radius: 7px;
            padding: 10px;
            background: #0f0f0f;
            color: var(--text);
            font: inherit;
          }}
          form.settings button {{
            justify-self: start;
            border: 1px solid #d97706;
            border-radius: 7px;
            padding: 11px 16px;
            background: #d97706;
            color: #111;
            font: inherit;
            font-weight: 700;
            cursor: pointer;
          }}
          .ok {{ color: #34d399; }}
          .warn {{ color: #fbbf24; }}
          .bad {{ color: #fb7185; }}
          svg {{
            width: 100%;
            max-height: 52vh;
            min-height: 320px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: #161616;
          }}
          svg rect {{ fill: #161616; }}
          svg line {{ stroke: #4b4b4b; }}
          svg text {{ font: 14px system-ui; }}
          #pressureLine {{ stroke: var(--pressure); }}
          #flowLine {{ stroke: var(--flow); }}
          #weightLine {{ stroke: var(--weight); }}
          ul {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px 18px 18px 34px; }}
          li {{ margin: 8px 0; }}
          @media (max-width: 900px) {{
            body {{ padding: 18px; }}
            .metrics.live {{ grid-template-columns: repeat(2, minmax(130px, 1fr)); }}
          }}
        </style>
      </head>
      <body>{body}</body>
    </html>
    """


def _fmt(value: float | None, unit: str) -> str:
    return "n/a" if value is None else f"{value:.2f} {unit}"


def _ratio(value: float | None) -> str:
    return "n/a" if value is None else f"1:{value:.2f}"


def _format_ts(timestamp: float) -> str:
    return dt.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def _recipe_form(redirect_to: str = "/") -> str:
    recipe = recipe_store.load()
    return f"""
    <form class="recipe" method="post" action="/recipe">
      <input type="hidden" name="redirect_to" value="{redirect_to}">
      <label>
        Input dose
        <input type="number" step="0.1" min="0" name="input_dose_g" value="{recipe.input_dose_g:.1f}">
      </label>
      <label>
        Target yield
        <input type="number" step="0.1" min="0" name="target_yield_g" value="{recipe.target_yield_g:.1f}">
      </label>
      <button type="submit">Set target</button>
    </form>
    """


def _status_payload() -> dict:
    settings = settings_store.load()
    now = dt.datetime.now().timestamp()
    last_seen = collector.last_seen
    sensors = [
        {
            "name": "Pressure",
            "entity": settings.pressure_entity,
            "value": collector.values.pressure_bar,
            "unit": "bar",
            "last_seen": last_seen.get("pressure"),
        },
        {
            "name": "Weight",
            "entity": settings.weight_entity,
            "value": collector.values.weight_g,
            "unit": "g",
            "last_seen": last_seen.get("weight"),
        },
        {
            "name": "Flow",
            "entity": settings.flow_entity,
            "value": collector.values.flow_g_s,
            "unit": "g/s",
            "last_seen": last_seen.get("flow"),
        },
        {
            "name": "Timer",
            "entity": settings.timer_entity,
            "value": collector.values.timer_s,
            "unit": "s",
            "last_seen": last_seen.get("timer"),
        },
    ]
    for sensor in sensors:
        sensor["age_s"] = now - sensor["last_seen"] if sensor["last_seen"] else None
        sensor["status"] = _sensor_status(sensor["age_s"])
    return {
        "ha_url": config.ha_url,
        "database": str(storage.path),
        "mode": "mock" if mock_mode else "live",
        "mock_mode": mock_mode,
        "settings": settings.__dict__,
        "recipe": recipe_store.load().__dict__,
        "running": collector.running,
        "sensors": sensors,
    }


def _sensor_status_rows() -> str:
    rows = []
    for sensor in _status_payload()["sensors"]:
        age = "never" if sensor["age_s"] is None else f"{sensor['age_s']:.1f}s ago"
        value = "n/a" if sensor["value"] is None else f"{sensor['value']:.2f} {sensor['unit']}"
        status = sensor["status"]
        css = "ok" if status == "ok" else "warn" if status == "stale" else "bad"
        rows.append(
            f"""
            <tr>
              <td>{sensor['name']}</td>
              <td>{sensor['entity']}</td>
              <td>{value}</td>
              <td>{age}</td>
              <td class="{css}">{status}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def _sensor_status(age_s: float | None) -> str:
    if age_s is None:
        return "waiting"
    if age_s <= 10:
        return "ok"
    if age_s <= 60:
        return "stale"
    return "offline"
