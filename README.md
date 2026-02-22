ADSBAlert
=======

Simple ADS-B alerting utility and dashboard.

Overview
--------

ADSBAlert watches defined airspace and alerts the user of any interesting aircraft (defined by the user) overhead, and provides a web dashboard and tray/background helpers for running on Windows.

Quickstart (Windows)
---------------------

1. Install dependencies:

```
pip install -r requirements.txt
```

2. Run the main application (foreground):

```
python app.py
```

3. To start background helpers on Windows, use:

```
start_background.bat
```

What’s in this repo
--------------------

- `app.py`: Main application entrypoint / web server.
- `dash.py`: Dashboard code (web UI integration).
- `tray.py`: System tray helper for Windows.
- `watcher.py`: Background watcher that monitors ADS-B feed.
- `interesting.py`: Logic for marking/handling interesting aircraft.
- `aircraft_db.py`: Simple CSV-backed aircraft database utilities.
- `db/`: Data storage (e.g. `aircraft.csv`, `interesting.txt`).
- `db/interesting.txt`: Patterns used to mark "interesting" aircraft. Supports sections like `OP:` (operator), `TYPE:` (aircraft type) and `REG:` (registration/tail number); lines starting with `#` are comments.
- `templates/` and `static/`: Web UI templates and JS assets.
- `requirements.txt`: Python dependencies.

Environment (.env)
-------------------

The application can load runtime configuration from a `.env` file placed in the project root. The file is plain `KEY=VALUE` lines (no quotes required). Example variables used by this project:

- `OPENSKY_USER`: OpenSky username used for API requests. (optional)
- `OPENSKY_PASS`: OpenSky password or API key. (optional)
- `OPENSKY_DAILY_CREDITS`: (integer) number of API credits available per day.
- `OPENSKY_COST_PER_REQUEST`: (integer) cost in credits per API request.
- `DISCORD_WEBHOOK_URL`: Discord webhook URL for alerts. (optional)

### Setting up Discord Alerts

To receive Discord notifications when interesting aircraft are detected:

1. Create a Discord channel where you want to receive alerts
2. Create a webhook for that channel:
   - Right-click the channel → Edit Channel
   - Go to Integrations → Webhooks → New Webhook
   - Copy the webhook URL
3. Add it to your `.env` file:

```
DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

When an interesting aircraft appears, the app will send a formatted embed message to your Discord channel with:
- Aircraft ICAO24 code
- Callsign
- Registration (tail number)
- Aircraft type
- Operator
- Current location (lat/lon)
- Altitude and velocity

Each aircraft is only alerted once per session (the watcher tracks alerted aircraft in memory).

### Example .env file

Create a `.env` file like this (use your real credentials; do not commit the file to source control):

```
OPENSKY_USER=your_username
OPENSKY_PASS=your_password_or_key
OPENSKY_DAILY_CREDITS=4000
OPENSKY_COST_PER_REQUEST=4
DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```

Notes
-----

- This README is intentionally minimal. See individual source files for implementation details and configuration.
- If you want me to expand this README with configuration options, screenshots, or detailed deploy steps, tell me what you'd like included.
- If using the OpenSky API anonymously, total daily credits are restricted to 400 credits
- The credit usage for the default defined airspace is 4 credits per request, see [OpenSky API Documentation](https://openskynetwork.github.io/opensky-api/rest.html#:~:text=API%20credit%20usage) to adjust values in .env file accordingly