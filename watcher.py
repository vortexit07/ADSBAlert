from datetime import datetime
import time
import threading
import os
import requests
import logging
from aircraft_db import load_aircraft_db, get_aircraft_info
from interesting import load_rules, is_interesting

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Load .env if present
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

# Discord webhook for interesting aircraft alerts
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Optional OpenSky credentials (will be used for HTTP Basic auth if set)
_OPENSKY_ID = os.getenv("OPENSKY_ID")
_OPENSKY_SECRET = os.getenv("OPENSKY_SECRET")


def get_opensky_token(id, secret):
    try:
        _OAUTH_PARAMS = {
            "content-type": "application/x-www-form-urlencoded",
            "grant_type": "client_credentials",
            "client_id": id,
            "client_secret": secret,
        }

        response = requests.post(
            "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token",
            data=_OAUTH_PARAMS,
            timeout=10,
        )

        if response.status_code == 200:
            logger.info("Successfully obtained OpenSky access token.")
            return response.json().get("access_token"), datetime.now()
        else:
            logger.warning(
                f"Failed to get OpenSky token: {response.status_code} - {response.text}"
            )
    except Exception as e:
        logger.warning(f"Error getting OpenSky token: {e}")


TOKEN = None
if _OPENSKY_ID and _OPENSKY_SECRET:
    TOKEN, token_time = get_opensky_token(_OPENSKY_ID, _OPENSKY_SECRET)
else:
    logger.info("No OpenSky credentials provided, using unauthenticated access")


def refresh_token_if_needed():
    global TOKEN, token_time
    if (
        TOKEN and (datetime.now() - token_time).total_seconds() > 3600
    ):  # Token valid for 1 hour
        logger.info("Refreshing OpenSky access token...")
        TOKEN, token_time = get_opensky_token(_OPENSKY_ID, _OPENSKY_SECRET)


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
logger.info(
    f"OpenSky: daily_credits={_DAILY_CREDITS}, cost/request={_COST_PER_REQUEST}, allowed_requests/day={_allowed_requests}, check_interval={CHECK_INTERVAL}s"
)

live_aircraft = {}
# Last observed remaining credits from OpenSky response header (int) or None
last_rate_limit_remaining = None
# Timestamp of the last successful fetch (unix time ms)
last_fetch_time = None
# Track which aircraft we've already alerted about (to avoid duplicate notifications)
alerted_aircraft = set()


def send_discord_alert(aircraft_info):
    """Send an alert to Discord about an interesting aircraft."""
    if not DISCORD_WEBHOOK_URL:
        return

    try:
        # Format the message with aircraft details
        icao24 = aircraft_info.get("icao24", "Unknown")
        callsign = aircraft_info.get("callsign", "").strip() or "N/A"
        registration = aircraft_info.get("registration", "Unknown")
        typecode = aircraft_info.get("typecode", "Unknown")
        operator = aircraft_info.get("operator", "Unknown")
        lat = aircraft_info.get("lat")
        lon = aircraft_info.get("lon")
        altitude = aircraft_info.get("altitude")
        velocity = aircraft_info.get("velocity")

        # Create embed message for Discord
        embed = {
            "title": "Interesting Aircraft Detected! 🛩️",
            "url": f"https://www.flightradar24.com/{callsign or registration}",
            "color": 0xFF0000,  # Red
            "fields": [
                {"name": "ICAO24", "value": icao24, "inline": True},
                {"name": "Callsign", "value": callsign, "inline": True},
                {
                    "name": "Registration",
                    "value": f"[{registration}](https://www.flightradar24.com/{registration})",
                    "inline": True,
                },
                {"name": "Type", "value": typecode, "inline": True},
                {"name": "Operator", "value": operator, "inline": False},
                {
                    "name": "Location",
                    "value": f"{lat}, {lon}" if lat and lon else "N/A",
                    "inline": True,
                },
                {
                    "name": "Altitude (m)",
                    "value": str(altitude) if altitude else "N/A",
                    "inline": True,
                },
                {
                    "name": "Velocity (m/s)",
                    "value": str(velocity) if velocity else "N/A",
                    "inline": True,
                },
            ],
            "footer": {"text": "ADSBAlert"},
        }

        payload = {"embeds": [embed]}
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)

        if response.status_code not in (200, 204):
            logger.warning(f"Discord webhook failed with status {response.status_code}")
    except Exception as e:
        logger.error(f"Error sending Discord alert: {e}", exc_info=True)


def fetch_aircraft():
    logger.info("Fetching aircraft data from OpenSky...")
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
                    logger.info(
                        f"OpenSky remaining credits: {last_rate_limit_remaining}"
                    )
                except Exception:
                    pass
        except Exception:
            pass

        if r.status_code != 200:
            logger.warning(f"OpenSky API returned {r.status_code}: {r.text}")
            if r.status_code == 401:
                refresh_token_if_needed()  # Try refreshing token if unauthorized
            return []
        data = r.json()
        states = data.get("states", [])
        logger.info(f"Successfully fetched {len(states)} aircraft states from OpenSky")
        return states
    except Exception as e:
        logger.error(f"Error fetching aircraft data: {e}", exc_info=True)
        return []


def watcher_loop():
    logger.info("Watcher started.")
    load_aircraft_db()

    global live_aircraft, last_fetch_time, alerted_aircraft

    while True:
        try:
            rules = load_rules()
            refresh_token_if_needed()
            states = fetch_aircraft()
            last_fetch_time = time.time() * 1000  # ms timestamp
            logger.info(f"Fetched {len(states)} aircraft from OpenSky.")
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

                # Send Discord alert if this is an interesting aircraft we haven't alerted about yet
                if interesting_flag and icao24 not in alerted_aircraft:
                    alerted_aircraft.add(icao24)
                    logger.info(
                        f"Interesting aircraft detected: {icao24} ({callsign or info['registration']})"
                    )
                    send_discord_alert(updated[icao24])

            live_aircraft.clear()
            live_aircraft.update(updated)
            logger.debug(f"Updated live_aircraft with {len(live_aircraft)} aircraft")

            for icao in list(alerted_aircraft):
                if icao not in live_aircraft:
                    alerted_aircraft.remove(icao)
                    logger.info(
                        f"Aircraft {icao} no longer live, removed from alerted set"
                    )

        except Exception as e:
            logger.error(f"Error in watcher loop: {e}", exc_info=True)

        time.sleep(CHECK_INTERVAL)


def start_watcher():
    thread = threading.Thread(target=watcher_loop, daemon=True)
    thread.start()
