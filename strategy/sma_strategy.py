from typing import Dict, Any, Optional
import logging

from data_analysis.data_manager import get_data_manager
from strategy.base import StrategyBase

logger = logging.getLogger(__name__)


class SMAStrategy(StrategyBase):

    def generate_signal(self, symbol: str, position: Optional[Dict[str, Any]],
                        instrument_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:

        market_data = get_data_manager().market_data
        df = market_data.get(symbol, {}).get(self.config["resolution"])

        if df is None or len(df) < 5:
            logger.warning(f"Insufficient data for {symbol}")
            return None

        # === CONFIG ===
        min_move_percent = self.config.get("strategy", {}).get("min_move_percent", 2.0)

        # === LAST CLOSED CANDLES ===
        curr = df.iloc[-2]
        prev = df.iloc[-3]

        # === EMA CALCULATIONS ===
        # Use ema_5 from indicator service
        if "ema_5" not in df.columns:
            logger.warning(f"ema_5 column not found in data for {symbol}")
            return None

        ema5_now = df["ema_5"].iloc[-2]
        ema5_prev = df["ema_5"].iloc[-3]

        if ema5_prev == 0 or ema5_prev is None:
            return None

        ema5_move_percent = ((ema5_now - ema5_prev) / ema5_prev) * 100

        move_condition = abs(ema5_move_percent) >= min_move_percent

        bullish_move = ema5_move_percent > 0
        bearish_move = ema5_move_percent < 0

        logger.info(f"{symbol} EMA5 move %: {ema5_move_percent:.4f}")

        # === ENTRY CANDLE CONDITIONS (previous candle) ===
        prev_open = prev["open"]
        prev_high = prev["high"]
        prev_low = prev["low"]

        long_candle_ok = abs(prev_open - prev_low) < 1e-4  # open == low
        short_candle_ok = abs(prev_high - prev_open) < 1e-4  # open == high

        # === ENTRY SIGNALS ===
        long_signal = bullish_move and move_condition and long_candle_ok
        short_signal = bearish_move and move_condition and short_candle_ok

        if long_signal:
            logger.info(f"{symbol} ENTER LONG")
            return {
                "signal": "ENTER_LONG",
                "side": "buy"
            }

        if short_signal:
            logger.info(f"{symbol} ENTER SHORT")
            return {
                "signal": "ENTER_SHORT",
                "side": "sell"
            }
        return None
