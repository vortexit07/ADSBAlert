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

Notes
-----

- This README is intentionally minimal. See individual source files for implementation details and configuration.
- If you want me to expand this README with configuration options, screenshots, or detailed deploy steps, tell me what you'd like included.