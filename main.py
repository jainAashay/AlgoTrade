"""
Main entry point for the AlgoTrading system.

Initializes and runs the trading engine with WebSocket data feed.
"""
import threading
import logging
from flask import Flask, jsonify

# IMPORTANT: Load config FIRST before importing any modules that depend on it
from configs.config_loader import Config
from configs.logger import setup_logger

# Setup logging early
# Load configuration BEFORE importing modules that use it
Config.load()
setup_logger()
logger = logging.getLogger(__name__)

# Now import modules that depend on Config
from trading_engine import TradingEngine
from trading_engine import get_system_mode, set_system_mode
from rest_client.web_socket_client import WebSocketClient


def _start_control_api() -> None:
    """Start control API for changing system mode."""
    app = Flask(__name__)

    @app.route("/system/bir", methods=["POST", "GET"])
    def set_bir():
        mode = set_system_mode("BIR")
        return jsonify({"status": "ok", "mode": mode}), 200

    @app.route("/system/oor", methods=["POST", "GET"])
    def set_oor():
        mode = set_system_mode("OOR")
        return jsonify({"status": "ok", "mode": mode}), 200

    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


def main():
    """Main function to start the trading system."""
    logger.info("AlgoTrading system starting")
    set_system_mode("OOR")
    logger.info(f"Default system mode set to {get_system_mode()}")

    # Initialize trading engine
    try:
        engine = TradingEngine()
    except Exception as e:
        logger.exception(f"Failed to initialize trading engine: {e}")
        return

    # Start WebSocket in background thread
    ws_client = WebSocketClient(engine.data_manager)
    ws_thread = threading.Thread(target=ws_client.start, daemon=True)
    ws_thread.start()
    logger.info("WebSocket client started in background thread")

    api_thread = threading.Thread(target=_start_control_api, daemon=True)
    api_thread.start()
    logger.info("Control API started in background thread on port 5000")

    # Run trading engine (blocking)
    try:
        engine.run(loop_interval=10)
    except KeyboardInterrupt:
        logger.info("Trading system stopped by user")
    except Exception as e:
        logger.exception(f"Trading engine error: {e}")
    finally:
        logger.info("Shutting down trading system")


if __name__ == "__main__":
    main()
