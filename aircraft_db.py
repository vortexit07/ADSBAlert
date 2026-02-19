import csv
import requests
import logging

logger = logging.getLogger(__name__)

AIRCRAFT_DB_FILE = "db/aircraft.csv"
HEXDB_URL = "https://hexdb.io/api/v1/aircraft/{}"

_aircraft_db = {}
_hexdb_cache = {}


def load_aircraft_db():
    global _aircraft_db

    if _aircraft_db:
        return

    try:
        with open(AIRCRAFT_DB_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, quotechar="'")
            reader.fieldnames = [h.strip() for h in reader.fieldnames]

            for row in reader:
                icao = row.get("icao24")
                if icao:
                    _aircraft_db[icao.lower()] = row

        logger.info(f"Loaded {len(_aircraft_db)} aircraft from DB at {AIRCRAFT_DB_FILE}.")
    except FileNotFoundError:
        logger.error(f"Aircraft database file not found: {AIRCRAFT_DB_FILE}")
    except Exception as e:
        logger.error(f"Error loading aircraft database: {e}", exc_info=True)


def format_aircraft_type(manufacturer, icao_type, type_description):
    """Format aircraft type as 'Manufacturer ICAO-Variant'."""
    if not manufacturer or not icao_type:
        return "Unknown"
    
    manufacturer = manufacturer.strip()
    icao_type = icao_type.strip().upper()
    
    if type_description:
        type_description = type_description.strip()
        # Replace spaces with hyphens in the full type description
        # e.g., "A320 232" -> "A320-232"
        variant = type_description.replace(" ", "-")
        return f"{manufacturer} {variant}"
    
    return f"{manufacturer} {icao_type}"


def fetch_hexdb(icao24):
    """Fetch aircraft metadata from HexDB API."""
    try:
        response = requests.get(HEXDB_URL.format(icao24), timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data:
            return {
                "registration": data.get("Registration") or "Unknown",
                "typecode": format_aircraft_type(
                    data.get("Manufacturer"),
                    data.get("ICAOTypeCode"),
                    data.get("Type")
                ),
                "operator": data.get("RegisteredOwners") or "",
                "source": "hexdb",
            }
    except Exception as e:
        logger.debug(f"HexDB lookup failed for {icao24}: {e}")
    
    return None


def get_aircraft_info(icao24):
    # Check cache first
    if icao24 in _hexdb_cache:
        return _hexdb_cache[icao24]
    
    # Try HexDB API first
    info = fetch_hexdb(icao24)
    if info:
        _hexdb_cache[icao24] = info
        return info
    
    # Fallback to local database
    metadata = _aircraft_db.get(icao24.lower())
    if metadata:
        info = {
            "registration": metadata.get("registration") or "Unknown",
            "typecode": format_aircraft_type(
                metadata.get("manufacturer"),
                metadata.get("typecode"),
                metadata.get("type")
            ),
            "operator": metadata.get("operator") or "",
            "source": "local",
        }
        _hexdb_cache[icao24] = info
        return info
    
    # If no info found anywhere, create a minimal entry so the aircraft still appears
    logger.debug(f"No aircraft info found for {icao24}, using minimal entry")
    info = {
        "registration": icao24.upper(),
        "typecode": "Unknown",
        "operator": "",
        "source": "none",
    }
    _hexdb_cache[icao24] = info
    return info