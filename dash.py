import requests
import time
import threading
import csv
from flask import Flask, jsonify, render_template_string

# ==============================
# CONFIG
# ==============================

SA_BOUNDS = (-35, -21, 16, 34)
CHECK_INTERVAL = 30
AIRCRAFT_DB_FILE = "aircraft-database.csv"
INTERESTING_FILE = "interesting_aircraft.txt"

# ==============================
# GLOBAL STATE
# ==============================

app = Flask(__name__)

_aircraft_db = {}
_hexdb_cache = {}
live_aircraft = {}
alerted_aircraft = set()

# ==============================
# LOAD LOCAL DATABASE
# ==============================


def load_aircraft_db():
    global _aircraft_db

    with open(AIRCRAFT_DB_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, quotechar="'")
        reader.fieldnames = [h.strip() for h in reader.fieldnames]

        for row in reader:
            icao = row.get("icao24")
            if icao:
                _aircraft_db[icao.lower()] = row

    print(f"Loaded {len(_aircraft_db)} aircraft from DB.")


# ==============================
# LOOKUP
# ==============================


def get_aircraft_info(icao24):
    if icao24 in _hexdb_cache:
        return _hexdb_cache[icao24]

    metadata = _aircraft_db.get(icao24.lower())
    if not metadata:
        return None

    info = {
        "registration": metadata.get("registration") or "Unknown",
        "typecode": (metadata.get("typecode") or "").upper(),
        "operator": metadata.get("operator") or "",
    }

    _hexdb_cache[icao24] = info
    return info


# ==============================
# INTERESTING
# ==============================


def load_interesting():
    operators = set()
    types = set()
    regs = set()

    try:
        with open(INTERESTING_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                line = line.upper()

                if line.startswith("OP:"):
                    operators.add(line[3:].strip())
                elif line.startswith("TYPE:"):
                    types.add(line[5:].strip())
                elif line.startswith("REG:"):
                    regs.add(line[4:].strip())
    except:
        pass

    return {
        "operators": operators,
        "types": types,
        "regs": regs,
    }


# ==============================
# FETCH OPEN SKY
# ==============================


def fetch_aircraft():
    try:
        response = requests.get(
            "https://opensky-network.org/api/states/all",
            params={
                "lamin": SA_BOUNDS[0],
                "lamax": SA_BOUNDS[1],
                "lomin": SA_BOUNDS[2],
                "lomax": SA_BOUNDS[3],
            },
            timeout=10,
        )

        response.raise_for_status()
        data = response.json()
        return data.get("states", [])
    except:
        return []


# ==============================
# WATCHER LOOP
# ==============================


def watcher_loop():
    print("Watcher started.")

    while True:
        interesting_rules = load_interesting()
        states = fetch_aircraft()

        updated = {}

        for s in states:
            icao24 = s[0]
            lat = s[6]
            lon = s[5]
            altitude = s[7]
            velocity = s[9]

            if not icao24:
                continue

            info = get_aircraft_info(icao24)
            if not info:
                continue

            reg = info["registration"].upper()
            typecode = info["typecode"].upper()
            operator = info["operator"].upper()

            is_interesting = (
                any(op in operator for op in interesting_rules["operators"])
                or typecode in interesting_rules["types"]
                or reg in interesting_rules["regs"]
            )

            updated[icao24] = {
                "icao24": icao24,
                "registration": info["registration"],
                "typecode": info["typecode"],
                "operator": info["operator"],
                "lat": lat,
                "lon": lon,
                "altitude": altitude,
                "velocity": velocity,
                "interesting": is_interesting,
            }

        global live_aircraft
        live_aircraft = updated

        time.sleep(CHECK_INTERVAL)


# ==============================
# WEB ROUTES
# ==============================


@app.route("/api/aircraft")
def api_aircraft():
    return jsonify(list(live_aircraft.values()))


@app.route("/")
def dashboard():
    return render_template_string(
        """
<!DOCTYPE html>
<html>
<head>
    <title>SA Airspace Monitor</title>
    <style>
        body { font-family: Arial; background: #111; color: #eee; }
        table { border-collapse: collapse; width: 100%; }
        th, td { padding: 8px; border-bottom: 1px solid #333; }
        th { background: #222; }
        tr.interesting { background: #5a0000; }
    </style>
</head>
<body>
<h2>South Africa Airspace Monitor</h2>
<table>
<thead>
<tr>
<th>ICAO</th>
<th>Reg</th>
<th>Type</th>
<th>Operator</th>
<th>Lat</th>
<th>Lon</th>
<th>Alt (m)</th>
<th>Speed (m/s)</th>
</tr>
</thead>
<tbody id="aircraft-table"></tbody>
</table>

<script>
async function loadData() {
    const res = await fetch('/api/aircraft');
    const data = await res.json();

    const table = document.getElementById('aircraft-table');
    table.innerHTML = '';

    data.forEach(ac => {
        const row = document.createElement('tr');
        if (ac.interesting) row.classList.add('interesting');

        row.innerHTML = `
            <td>${ac.icao24}</td>
            <td>${ac.registration}</td>
            <td>${ac.typecode}</td>
            <td>${ac.operator}</td>
            <td>${ac.lat ?? ''}</td>
            <td>${ac.lon ?? ''}</td>
            <td>${ac.altitude ?? ''}</td>
            <td>${ac.velocity ?? ''}</td>
        `;
        table.appendChild(row);
    });
}

setInterval(loadData, 5000);
loadData();
</script>

</body>
</html>
"""
    )


# ==============================
# STARTUP
# ==============================

if __name__ == "__main__":
    load_aircraft_db()

    watcher_thread = threading.Thread(target=watcher_loop, daemon=True)
    watcher_thread.start()

    app.run(host="0.0.0.0", port=5000)
