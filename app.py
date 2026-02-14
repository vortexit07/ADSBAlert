from flask import Flask, jsonify, render_template
import watcher
import os
import signal

app = Flask(__name__)

@app.route("/api/aircraft")
def api_aircraft():
    return jsonify(list(watcher.live_aircraft.values()))


@app.route("/api/status")
def api_status():
    # Estimated requests per day at current interval
    CHECK_INTERVAL = watcher.CHECK_INTERVAL
    _DAILY_CREDITS = watcher._DAILY_CREDITS
    _COST_PER_REQUEST = watcher._COST_PER_REQUEST
    _allowed_requests = watcher._allowed_requests

    requests_per_day = max(1, 86400 // CHECK_INTERVAL)
    estimated_credits_used = requests_per_day * _COST_PER_REQUEST

    # Prefer the server-reported remaining credits header when available
    remaining_header = getattr(watcher, 'last_rate_limit_remaining', None)
    if isinstance(remaining_header, int):
        remaining_credits = remaining_header
    else:
        remaining_credits = max(0, _DAILY_CREDITS - estimated_credits_used)

    return jsonify(
        {
            "check_interval": CHECK_INTERVAL,
            "daily_credits": _DAILY_CREDITS,
            "cost_per_request": _COST_PER_REQUEST,
            "allowed_requests_per_day": _allowed_requests,
            "estimated_requests_per_day": requests_per_day,
            "estimated_credits_used_per_day": estimated_credits_used,
            "remaining_credits": remaining_credits,
            "last_fetch_time": watcher.last_fetch_time,
        }
    )

@app.route("/api/quit", methods=["POST"])
def api_quit():
    # Gracefully shut down the Flask server
    os.kill(os.getpid(), signal.SIGTERM)
    return jsonify({"status": "shutting down"})

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

if __name__ == "__main__":
    watcher.start_watcher()
    app.run(host="0.0.0.0", port=5000)