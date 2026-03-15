"""
WebSocket client module for real-time market data.
"""
import json
import websocket
import logging
import time
import hmac
import hashlib
from typing import Optional, Dict, Any

from configs.config_loader import Config
from exceptions import ExchangeError
from order_manager.order_manager import get_order_manager # Import get_order_manager

logger = logging.getLogger(__name__)


class WebSocketClient:
    """WebSocket client for receiving real-time market data."""
    
    def __init__(self, data_manager):
        """Initialize WebSocketClient."""
        self.data_manager = data_manager
        self.order_manager = get_order_manager() # Get OrderManager instance
        self.ws: Optional[websocket.WebSocketApp] = None
        self.url = Config.get("exchange", "ws_url")
        self.api_key = Config.get("exchange", "api_key")
        self.api_secret = Config.get("exchange", "api_secret")
        self.instruments = Config.get("instruments")
        
    def _on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        """Handle incoming WebSocket message."""
        logger.debug(f"Received WebSocket message: {message}")
        try:
            msg = json.loads(message)
            logger.info(f"Received message {json.dumps(msg)}")

            if msg.get("type") == "key-auth":
                logger.info(msg)
                if msg.get("success"):
                    logger.info("WebSocket authentication successful.")
                    self._subscribe_to_channels(ws)
                else:
                    logger.error(f"WebSocket authentication failed: {msg.get('message')}")
                return

            if msg.get("type") == "positions":
                logger.info(f"Received private channel message: {json.dumps(msg)}")
                self.order_manager.handle_position_update(msg) # Call order_manager's method
                return
            
            required_fields = ("open", "high", "low", "close", "volume", "symbol", "resolution")
            if not all(k in msg for k in required_fields):
                logger.warning(f"Missing required fields in message: {msg}")
                return
            
            symbol = msg["symbol"]
            timeframe = msg["resolution"]
            logger.info(f"Processing candle for {symbol} {timeframe}")
            
            candle = [msg["candle_start_time"],msg["open"],msg["high"],msg["low"],msg["close"],msg["volume"]]
            
            inst = next((i for i in self.instruments if i["symbol"] == symbol), None)
            
            if inst:
                indicators_cfg = inst.get("strategy", {}).get("indicators", [])
                self.data_manager.add_candle(symbol, timeframe, candle, indicators_cfg)
                logger.info(f"Successfully processed candle for {symbol} {timeframe}: close={candle[4]}")
            else:
                logger.warning(f"No instrument configuration found for {symbol}")
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error processing WS message: {e}", exc_info=True)
    
    def _on_open(self, ws: websocket.WebSocketApp) -> None:
        """Handle WebSocket connection opened."""
        logger.info("WebSocket connection opened successfully")
        self._authenticate_websocket(ws)
        
    def _authenticate_websocket(self, ws: websocket.WebSocketApp) -> None:
        """Authenticate WebSocket connection for private channels."""
        method = 'GET'
        timestamp = str(int(time.time()))
        path = '/live'
        signature_data = method + timestamp + path
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        auth_payload = {
            "type": "key-auth",
            "payload": {
                "api-key": self.api_key,
                "signature": signature,
                "timestamp": timestamp
            }
        }
        ws.send(json.dumps(auth_payload))
        logger.info("Sent WebSocket authentication request.")
    
    def _subscribe_to_channels(self, ws: websocket.WebSocketApp) -> None:
        """Subscribe to public and private channels."""
        channels_to_subscribe = []

        # Public channels (candlesticks)
        channels_by_tf: Dict[str, set] = {}
        for inst in self.instruments:
            symbol = inst["symbol"]
            resolution = inst["resolution"]
            channels_by_tf.setdefault(resolution, set()).add(symbol)
        
        for tf, symbols in channels_by_tf.items():
            channels_to_subscribe.append({
                "name": f"candlestick_{tf}",
                "symbols": list(symbols)
            })
        
        # Private channels (positions and orders)
        private_channels = ["positions", "orders"]
        for channel_name in private_channels:
            channels_to_subscribe.append({
                "name": channel_name,
                "symbols": ["all"]
            })
        
        payload = {
            "type": "subscribe",
            "payload": {"channels": channels_to_subscribe}
        }
        
        ws.send(json.dumps(payload))
        logger.info(f"Subscribed to channels: {json.dumps(payload, indent=2)}")

    def _on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        """Handle WebSocket error."""
        logger.error(f"WebSocket error occurred: {error}")
    
    def _on_close(self, ws: websocket.WebSocketApp, close_status_code: Optional[int], close_msg: Optional[str]) -> None:
        """Handle WebSocket connection closed."""
        logger.warning(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        if close_status_code is None:
            logger.warning("WebSocket closed unexpectedly - may be a network issue")
    
    def start(self) -> None:
        """Start WebSocket connection and run forever."""
        logger.info(f"Starting WebSocket connection to {self.url}")
        
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        self.ws.run_forever(ping_interval=30, ping_timeout=10)
    
    def stop(self) -> None:
        """Stop WebSocket connection."""
        if self.ws:
            self.ws.close()
            logger.info("WebSocket connection closed")


# Backward compatibility function
def start_ws() -> None:
    """Start WebSocket (backward compatibility)."""
    from data_analysis.data_manager import get_data_manager
    client = WebSocketClient(get_data_manager())
    client.start()
