import time
import threading
import os
import requests
from aircraft_db import load_aircraft_db, get_aircraft_info
from interesting import load_rules, is_interesting

# Load .env if present
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# Optional OpenSky credentials (will be used for HTTP Basic auth if set)
_OPENSKY_ID = os.getenv("OPENSKY_ID")
_OPENSKY_SECRET = os.getenv("OPENSKY_SECRET")

_OAUTH_PARAMS ={
    "content-type": "application/x-www-form-urlencoded",
    "grant_type": "client_credentials",
    "client_id": _OPENSKY_ID,
    "client_secret": _OPENSKY_SECRET
}

TOKEN = requests.post(
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token", data=_OAUTH_PARAMS
)

if TOKEN.status_code == 200:
    TOKEN = TOKEN.json().get("access_token")
    print("Successfully obtained OpenSky access token.")

# Base REST URL
_OPENSKY_BASE = "https://opensky-network.org/api"

SA_BOUNDS = (-35, -21, 16, 34)
# Compute a safe default check interval based on daily OpenSky credits so
# we don't exceed the user's allowance. Defaults can be overridden via
# environment variables.
# Cost tiers: this project currently uses ~4 credits per broad-area request.
_COST_PER_REQUEST = int(os.getenv("OPENSKY_COST_PER_REQUEST", "4"))
_DAILY_CREDITS = int(os.getenv("OPENSKY_DAILY_CREDITS", "4000"))

# Maximum number of requests allowed per day (integer division)
_allowed_requests = max(1, _DAILY_CREDITS // _COST_PER_REQUEST)
# Default interval in seconds between requests (round up and add 1s safety)
_default_interval = int(86400 // _allowed_requests) + 1

# Allow explicit override with CHECK_INTERVAL env var (seconds)
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", str(_default_interval)))

print(
    f"OpenSky: daily_credits={_DAILY_CREDITS}, cost/request={_COST_PER_REQUEST}, allowed_requests/day={_allowed_requests}, check_interval={CHECK_INTERVAL}s"
)

live_aircraft = {}
# Last observed remaining credits from OpenSky response header (int) or None
last_rate_limit_remaining = None
# Timestamp of the last successful fetch (unix time ms)
last_fetch_time = None

def fetch_aircraft():
    print("Fetching aircraft data from OpenSky...")
    try:
        global last_rate_limit_remaining
        params = {
            "lamin": SA_BOUNDS[0],
            "lamax": SA_BOUNDS[1],
            "lomin": SA_BOUNDS[2],
            "lomax": SA_BOUNDS[3],
            "extended": True,
        }
        headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else None
        r = requests.get(
            f"{_OPENSKY_BASE}/states/all", params=params, headers=headers, timeout=15
        )
                
        # capture remaining credits header if present
        try:
            hdr = r.headers.get("x-rate-limit-remaining")
            if hdr is None:
                hdr = r.headers.get("X-RateLimit-Remaining")
            if hdr:
                try:
                    # update module-level var
                    last_rate_limit_remaining = int(hdr)
                    print(f"OpenSky remaining credits: {last_rate_limit_remaining}")
                except Exception:
                    pass
        except Exception:
            pass

        if r.status_code != 200:
            return []
        data = r.json()
        return data.get("states", [])
    except Exception:
        return []

def watcher_loop():
    print("Watcher started.")
    load_aircraft_db()

    global live_aircraft, last_fetch_time

    while True:
        rules = load_rules()
        states = fetch_aircraft()
        last_fetch_time = time.time() * 1000  # ms timestamp
        print(f"Fetched {len(states)} aircraft from OpenSky.")
        updated = {}

        for s in states:
            # Support both StateVector objects (from wrapper) and raw
            # arrays (from REST) so this function is robust.
            if hasattr(s, "icao24"):
                icao24 = s.icao24
                callsign = (s.callsign or "").strip()
                lat = s.latitude
                lon = s.longitude
                # prefer geo_altitude when available
                altitude = (
                    s.geo_altitude
                    if getattr(s, "geo_altitude", None) is not None
                    else s.baro_altitude
                )
                velocity = s.velocity
            else:
                icao24 = s[0]
                callsign = (s[1] or "").strip()
                lat = s[6]
                lon = s[5]
                altitude = s[7]
                velocity = s[9]

            if not icao24:
                continue

            info = get_aircraft_info(icao24)
            if not info:
                continue

            interesting_flag = is_interesting(info, rules)

            updated[icao24] = {
                "icao24": icao24,
                "callsign": callsign,
                "registration": info["registration"],
                "typecode": info["typecode"],
                "operator": info["operator"],
                "lat": lat,
                "lon": lon,
                "altitude": altitude,
                "velocity": velocity,
                "interesting": interesting_flag,
            }

        live_aircraft.clear()
        live_aircraft.update(updated)
        time.sleep(CHECK_INTERVAL)

def start_watcher():
    thread = threading.Thread(target=watcher_loop, daemon=True)
    thread.start()