"""
Common utilities for algo trading system.
"""
from typing import Dict, Optional, List, Any
from rest_client.rest_client import get_rest_client
from exceptions import OrderError, ExchangeError
import logging

logger = logging.getLogger(__name__)


class CommonUtils:
    """Utility class providing common trading operations and time conversions."""
    
    def __init__(self):
        self._product_id_cache: Dict[str, int] = {}
        self.rest_client = get_rest_client()

    def get_product_id_from_symbol(self, symbol: str) -> int:
        """Get product ID for a symbol (with caching)."""
        if self._product_id_cache.get(symbol):
            return self._product_id_cache[symbol]
        
        try:
            product = self.rest_client.delta_client.get_product(symbol)
            self._product_id_cache[symbol] = product['id']
            return product['id']
        except Exception as e:
            raise OrderError(f"Failed to fetch products for {symbol}") from e
        
        raise OrderError(f"Product not found: {symbol}")

    def get_fill_history_data(self, symbol: str, start_time: int, end_time: int, query_params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get fill history for a symbol within a time range."""
        try:
            all_fills: List[Dict[str, Any]] = []
            product_ids = str(self.get_product_id_from_symbol(symbol))
            current_query_params = {"product_ids": product_ids, "contract_types": "perpetual_futures", "start_time": start_time,
                                    "end_time": end_time, "page_size": 500}  # Max limit
            if query_params:
                current_query_params.update(query_params)
            response = self.rest_client.get_fill_history(symbol=symbol, query_params=current_query_params)
            fills = response["result"]
            after = response["meta"]["after"]
            all_fills.extend(fills)
            # Fetch fills until no more are returned or the start_time is reached
            while fills and after:
                current_query_params["after"] = after
                response = self.rest_client.get_fill_history(symbol=symbol, query_params=current_query_params)
                fills = response["result"]
                after = response["meta"]["after"]
                all_fills.extend(fills)
                
            return all_fills
        except Exception as e:
            logger.exception(f"Error fetching fill history for {symbol}")
            raise ExchangeError(f"Failed to fetch fill history for {symbol}") from e

    @staticmethod
    def resolution_to_seconds(resolution: str) -> int:
        """Convert resolution string to seconds."""
        r = resolution.strip().upper()
        match r:
            case "D":
                return 86400
            case _ if r.endswith("D") and r[:-1].isdigit():
                return int(r[:-1]) * 86400
            case _ if r.endswith("M") and r[:-1].isdigit():
                return int(r[:-1]) * 60
            case _ if r.endswith("H") and r[:-1].isdigit():
                return int(r[:-1]) * 3600
            case _:
                return 60


# Global instance for backward compatibility
_common_utils = CommonUtils()

def get_common_utils() -> CommonUtils:
    """Get the global CommonUtils instance."""
    return _common_utils
