"""
Main entry point for the AlgoTrading system.

Initializes and runs the trading engine with WebSocket data feed.
"""
import threading
import logging

# IMPORTANT: Load config FIRST before importing any modules that depend on it
from configs.config_loader import Config
from configs.logger import setup_logger

# Setup logging early
setup_logger()
logger = logging.getLogger(__name__)

# Load configuration BEFORE importing modules that use it
Config.load()

# Now import modules that depend on Config
from trading_engine import TradingEngine
from rest_client.web_socket_client import WebSocketClient


def main():
    """Main function to start the trading system."""
    logger.info("AlgoTrading system starting")

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

    # Run trading engine (blocking)
    try:
        engine.run(loop_interval=5)
    except KeyboardInterrupt:
        logger.info("Trading system stopped by user")
    except Exception as e:
        logger.exception(f"Trading engine error: {e}")
    finally:
        logger.info("Shutting down trading system")


if __name__ == "__main__":
    main()
