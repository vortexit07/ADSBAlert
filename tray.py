import threading
import os
import sys
import time
import logging

# Setup file logging for pythonw compatibility
logfile = os.path.join(os.path.dirname(__file__), "tray.log")
logging.basicConfig(
    filename=logfile,
    level=logging.DEBUG,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
)
logging.info("ADSBAlert tray launcher starting")

# Import the Flask `app` and `watcher` module
try:
    from app import app as flask_app
    import watcher
except Exception as e:
    logging.error(f"Failed to import modules: {e}", exc_info=True)
    sys.exit(1)


def run_flask():
    """Run Flask server in background thread."""
    flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)


def main():
    """Start watcher and Flask server; keep process alive."""
    try:
        logging.info("Starting watcher thread")
        watcher.start_watcher()

        logging.info("Starting Flask server thread")
        t = threading.Thread(target=run_flask, daemon=True)
        t.start()

        logging.info("Watcher and Flask started. Dashboard at http://localhost:5000")
        
        # Keep process alive indefinitely
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Interrupted by user, exiting")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
