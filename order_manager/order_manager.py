"""
Order and position management module.
"""
import time
import json
from typing import Dict, List, Optional, Any, Tuple

from delta_rest_client import OrderType

from utils.common_utils import CommonUtils, get_common_utils
from collections import defaultdict
import logging
from configs.config_loader import Config

from rest_client.rest_client import get_rest_client
from exceptions import OrderError

logger = logging.getLogger(__name__)


class OrderManager:
    """Manages orders, positions, and market data operations."""
    
    def __init__(self):
        """Initialize OrderManager."""
        self.rest_client = get_rest_client()
        self.common_utils = get_common_utils()
        self.instruments = Config.get("instruments")
        self.delta_client = self.rest_client.delta_client
        self.order_timestamps: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.positions: Dict[str, Any] = {}

    def handle_position_update(self, message: Dict[str, Any]) -> None:
        """Handle incoming position update messages."""
        action = message.get("action")
        symbol = message.get("symbol")
        
        if not symbol or not action:
            logger.warning(f"Invalid position update message: {message}")
            return
        
        if action == "snapshot":
            for position_data in message.get("result", []) :
                self.positions[position_data["symbol"]] = position_data
            logger.info(f"Position snapshot received. Current open positions: {list(self.positions.keys())}")
            return
        
        if action == "create" or action == "update":
            position = message  # The message itself is the position data for create/update
            self.positions[symbol] = position
            logger.info(f"Position {action}d for {symbol}: {json.dumps(position)}")
            
            # If it's a new position entry, place a bracket order
            if action == "create":
                instrument_config = next((i for i in self.instruments if i["symbol"] == symbol), None)
                if instrument_config:
                    self.place_bracket_order(symbol, position, instrument_config)
                else:
                    logger.warning(f"No instrument configuration found for {symbol}. Cannot place bracket order.")

        elif action == "delete":
            if symbol in self.positions:
                del self.positions[symbol]
                logger.info(f"Position deleted for {symbol}.")
        else:
            logger.warning(f"Unknown position action: {action} for symbol: {symbol}")

    @staticmethod
    def position_side(position: Dict[str, Any]) -> Optional[str]:
        """Determine the side of a position."""
        size = float(position.get("size", 0))
        if size > 0:
            return "buy"
        if size < 0:
            return "sell"
        return None

    def get_best_bid_ask(self, symbol: str, depth: int = 1) -> Tuple[Optional[float], Optional[float]]:
        """Get best bid and ask prices from orderbook."""
        try:
            product_id = self.common_utils.get_product_id_from_symbol(symbol)
            orderbook = self.delta_client.get_l2_orderbook(product_id)
            buy_book = orderbook.get("buy", [])
            sell_book = orderbook.get("sell", [])

            best_bid = float(buy_book[0]["price"]) if buy_book else None
            best_ask = float(sell_book[0]["price"]) if sell_book else None
            return best_bid, best_ask
        except Exception as e:
            logger.error(f"Error getting best bid/ask for {symbol}: {e}")
            return None, None

    def place_market_order(self, symbol: str, side: str, qty: float, reduce_only: bool = False) -> Optional[Dict[str, Any]]:
        """Place a market order."""
        try:
            return self.delta_client.place_order(
                product_id=str(self.common_utils.get_product_id_from_symbol(symbol)),
                side=side.lower(),
                order_type=OrderType.MARKET,
                size=qty,
                reduce_only=reduce_only
            )
        except Exception as e:
            logger.error(f"Error placing market order for {symbol}: {e}")
            raise OrderError(f"Failed to place market order for {symbol}") from e

    def place_ioc_limit_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Optional[Dict[str, Any]]:
        """Place an IOC (Immediate or Cancel) limit order."""
        try:
            return self.delta_client.create_order(order={
                "product_symbol": symbol,
                "limit_price": str(limit_price),
                "size": qty,
                "side": side,
                "order_type": "limit_order"
            })
        except Exception as e:
            logger.error(f"Error placing IOC limit order for {symbol}: {e}")
            raise OrderError(f"Failed to place IOC limit order for {symbol}") from e

    def place_reduce_only_limit_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Optional[Dict[str, Any]]:
        """Place a reduce-only limit order (typically for take profit)."""
        try:
            return self.delta_client.place_order(
                product_id=self.common_utils.get_product_id_from_symbol(symbol),
                side=side.lower(),
                order_type="limit",
                size=qty,
                price=str(limit_price),
                reduce_only=True
            )
        except Exception as e:
            logger.error(f"Error placing reduce-only limit order for {symbol}: {e}")
            raise OrderError(f"Failed to place reduce-only limit order for {symbol}") from e

    def place_stop_loss_market_order(self, symbol: str, side: str, qty: float, stop_price: float, close_on_trigger: bool = True) -> Optional[Dict[str, Any]]:
        """Place a stop loss market order."""
        try:
            return self.delta_client.place_order(
                product_id=self.common_utils.get_product_id_from_symbol(symbol),
                side=side.lower(),
                order_type="market",
                size=qty,
                stop_price=str(stop_price),
                stop_order_type="stop",
                close_on_trigger=close_on_trigger,
                reduce_only=True
            )
        except Exception as e:
            logger.error(f"Error placing stop loss order for {symbol}: {e}")
            raise OrderError(f"Failed to place stop loss order for {symbol}") from e

    def get_open_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Get all open orders for a symbol."""
        try:
            all_orders = self.delta_client.get_live_orders()
            return [
                order for order in all_orders
                if order.get("product_symbol") == symbol
                and order.get("state") == "open"
            ]
        except Exception as e:
            logger.error(f"Error getting open orders for {symbol}: {e}")
            return []

    def cancel_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Cancel an order by ID."""
        try:
            return self.delta_client.cancel_order(order_id=order_id)
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            raise OrderError(f"Failed to cancel order {order_id}") from e

    def cancel_all_orders(self, symbol: str) -> None:
        """Cancel all open orders for a symbol."""
        open_orders = self.get_open_orders(symbol)
        for order in open_orders:
            try:
                self.cancel_order(order["id"])
            except Exception as e:
                logger.error(f"Error cancelling order {order['id']}: {e}")

    def cancel_expired_orders(self, symbol: str, ttl_seconds: float) -> None:
        """Cancel orders that have expired based on TTL."""
        now = time.time()
        open_orders = self.get_open_orders(symbol)

        for order in open_orders:
            order_id = order["id"]
            placed_at = self.order_timestamps[symbol].get(order_id)

            if placed_at is None or (now - placed_at) >= ttl_seconds:
                logger.info(f"Cancelling expired order {order_id} for {symbol}")
                try:
                    self.cancel_order(order_id)
                except Exception as e:
                    logger.error(f"Error cancelling expired order {order_id}: {e}")

    def get_open_position(self, symbol: str) -> Dict[str, Any]:
        """Get all open positions for a symbol."""
        try:
            product_id = self.common_utils.get_product_id_from_symbol(symbol)
            position = self.delta_client.get_position(product_id)
            return position
        except Exception as e:
            logger.error(f"Error getting positions for {symbol}: {e}")
            return []

    def close_position_reduce_only(self, symbol: str, position: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Close a position using a reduce-only market order."""
        size = abs(float(position["size"]))
        side = "sell" if float(position["size"]) > 0 else "buy"
        return self.place_market_order(symbol, side, size, reduce_only=True)

    def change_leverage(self, symbol: str, leverage: int) -> Optional[Dict[str, Any]]:
        """Change leverage for a symbol."""
        try:
            return self.delta_client.set_leverage(
                product_id=self.common_utils.get_product_id_from_symbol(symbol),
                leverage=leverage
            )
        except Exception as e:
            logger.error(f"Error changing leverage for {symbol}: {e}")
            raise OrderError(f"Failed to change leverage for {symbol}") from e

    def place_bracket_order(self,symbol: str,position: Dict[str, Any],instrument_config: Dict[str, Any]) -> None:
        """Place TP and SL using individual Place Order requests (Delta-compatible)."""
        try:
            position_side = self.position_side(position)
            if not position_side:
                logger.warning(f"Cannot place bracket order for {symbol}: position side not determined.")
                return

            entry_price = float(position["entry_price"])
            size = abs(float(position["size"]))

            take_profit_pct = instrument_config.get("take_profit_pct", 0.02)
            stop_loss_pct = instrument_config.get("stop_loss_pct", 0.05)
            trailing_amount = instrument_config.get("trailing_amount_pct", 0.0) * entry_price

            # ----------------------------------
            # Price calculation
            # ----------------------------------
            if position_side == "buy":
                tp_price = entry_price * (1 + take_profit_pct)
                sl_price = entry_price * (1 - stop_loss_pct)
            else:
                tp_price = entry_price * (1 - take_profit_pct)
                sl_price = entry_price * (1 + stop_loss_pct)

            product_id = self.common_utils.get_product_id_from_symbol(symbol)

            bracket_order = {
                "product_id": product_id,
                "product_symbol": symbol,
                "stop_loss_order": {
                    "order_type": "market_order"
                },
                "take_profit_order": {
                    "order_type": "market_order",
                    "stop_price": str(tp_price)
                },
                "bracket_stop_trigger_method": "last_traded_price"
            }

            if trailing_amount != 0:
                bracket_order["stop_loss_order"]["trail_amount"] = str(trailing_amount)
            else:
                bracket_order["stop_loss_order"]["stop_price"] = str(sl_price)

            logger.info(f"Sending bracket order for {symbol} with request body: {bracket_order}")

            self.rest_client.send_private_request(method="POST",path="/v2/orders/bracket",body=bracket_order)

            logger.info(f"Placed TP & SL for {symbol} | Entry={entry_price}, TP={tp_price}, SL={sl_price}")

        except Exception as e:
            logger.error(f"Error placing bracket order for {symbol}: {e}",exc_info=True)
            raise OrderError(f"Failed to place bracket order for {symbol}") from e


# Simple global instance
_order_manager = None

def get_order_manager() -> OrderManager:
    """Get the global OrderManager instance."""
    global _order_manager
    if _order_manager is None:
        _order_manager = OrderManager()
    return _order_manager


