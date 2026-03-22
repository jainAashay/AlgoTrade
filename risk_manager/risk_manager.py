"""
Risk management module.
"""
import time
import logging
import math
from datetime import datetime, timezone, timedelta

from typing import List, Dict, Any
from utils.common_utils import CommonUtils, get_common_utils

logger = logging.getLogger(__name__)


class RiskManager:
    """Manages trading risk limits and validations."""

    def __init__(self):
        self.common_utils = get_common_utils()


    def allowed_to_trade(self,symbol: str,inst:Dict[str, Any]) -> bool:

        risk_config = inst.get("risk")
        time_frame = risk_config.get("time_frame")
        max_trades = risk_config.get("max_trades")
        fill_interval = risk_config.get("fill_interval",180)

        seconds = CommonUtils.resolution_to_seconds(time_frame)
        fill_interval_in_minutes = int(CommonUtils.resolution_to_seconds(fill_interval) / 60 )

        # Get fills for the last 24 hours (example interval)
        end_time = int(time.time() * 1_000_000)  # microseconds
        start_time = end_time - (seconds * 1_000_000)
        fills = self.common_utils.get_fill_history_data(symbol=symbol, start_time=start_time, end_time=end_time)
        fills_sorted = sorted(fills,key=lambda x: datetime.fromisoformat(x["created_at"].replace("Z", "+00:00")),reverse=True)
        if len(fills_sorted) == 0:
            return True
        latest_fill = fills_sorted[0]
        latest_time = datetime.fromisoformat(latest_fill["created_at"].replace("Z", "+00:00"))
        now_utc = datetime.now(timezone.utc)
        time_diff = now_utc - latest_time
        recent_fill = False
        if time_diff < timedelta(minutes=fill_interval_in_minutes):
            logger.info("Recent fill is within last 3 minutes.")
            recent_fill = True

        logger.info(f"Found {len(fills)} fills for {symbol} between {start_time} and {end_time}")
        logger.info(f"{symbol} fills: {fills}")

        if math.floor(len(fills) / 2) > max_trades or recent_fill:
            logger.warning(f"Trading blocked for {symbol} due to excessive fills: {len(fills)}")
            return False
        
        return True


# Simple global instance
_risk_manager = None

def get_risk_manager() -> RiskManager:
    """Get the global RiskManager instance."""
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager


# Backward compatibility
def allowed_to_trade() -> bool:
    """Check if trading is allowed (backward compatibility)."""
    # This function should no longer be used directly without an order_manager
    raise NotImplementedError("allowed_to_trade requires an OrderManager instance")
