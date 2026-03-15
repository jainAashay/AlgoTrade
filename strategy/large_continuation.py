from typing import Dict, Any, Optional
import logging

from data_analysis.data_manager import get_data_manager
from strategy.base import StrategyBase

logger = logging.getLogger(__name__)


class StrongContinuationStrategy(StrategyBase):

    def generate_signal(self,symbol: str,position: Optional[Dict[str, Any]],instrument_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:

        market_data = get_data_manager().market_data
        df = market_data.get(symbol, {}).get(self.config["resolution"])

        # Need at least 2 closed candles
        if df is None or len(df) < 2:
            logger.warning(f"Insufficient data for {symbol}")
            return None

        # Last 2 CLOSED candles
        prev_candle = df.iloc[-2]
        curr_candle = df.iloc[-1]

        ema_prev = prev_candle.get("ema_5")
        ema_curr = curr_candle.get("ema_5")

        ema_percent_move = self._percent_move(ema_prev, ema_curr)

        if abs(ema_percent_move) < self.config.get("strategy").get("ema_impulse_threshold", 0.01):
            logger.info(f"{symbol} EMA move {ema_percent_move:.4f} not large enough.")
            return None

        logger.info(f"{symbol} EMA % move: {ema_percent_move:.4f}")

        # Extract OHLC
        prev_open = prev_candle["open"]
        prev_close = prev_candle["close"]

        curr_open = curr_candle["open"]
        curr_close = curr_candle["close"]

        prev_high = prev_candle["high"]
        prev_low = prev_candle["low"]

        cur_high = curr_candle["high"]
        cur_low = curr_candle["low"]

        # -----------------------------
        # Previous Candle % Move
        # -----------------------------
        percent_threshold = self.config.get("strategy").get("large_candle_percent", 1.0)

        wick_threshold = self.config.get("strategy", {}).get("wick_threshold", 0.05)

        prev_percent_move = self._percent_move(prev_open, prev_close)

        logger.info(f"{symbol} Previous candle % move: {prev_percent_move:.4f}")

        if abs(prev_percent_move) < percent_threshold:
            logger.info(f"{symbol} Previous candle not large enough.")
            return None

        total_range = prev_high - prev_low
        if total_range <= 0:
            return None

        upper_wick = prev_high - max(prev_open, prev_close)
        lower_wick = min(prev_open, prev_close) - prev_low

        # ==========================================================
        # ====================== LONG SETUP ========================
        # ==========================================================

        # Previous bullish large candle
        if prev_close > prev_open:
            upper_ratio = upper_wick / total_range
            # Current candle must also be bullish
            if curr_close > curr_open  and curr_open > prev_close and cur_high == curr_close and upper_ratio < wick_threshold:
                logger.info(f"{symbol} STRONG CONTINUATION LONG")

                return {
                    "signal": "ENTER_LONG",
                    "side": "buy"
                }

        # ==========================================================
        # ====================== SHORT SETUP =======================
        # ==========================================================

        # Previous bearish large candle
        if prev_close < prev_open:
            lower_ratio = lower_wick / total_range

            # Current candle must also be bearish
            if curr_close < curr_open and curr_open < prev_close and cur_low == curr_close and lower_ratio < wick_threshold:
                logger.info(f"{symbol} STRONG CONTINUATION SHORT")

                return {
                    "signal": "ENTER_SHORT",
                    "side": "sell"
                }

        return None

    # -------------------------------------------------------------

    def _percent_move(self, open_price: float, close_price: float) -> float:
        """
        Calculate percentage move of candle.
        """
        if open_price == 0:
            return 0.0
        return ((close_price - open_price) / open_price) * 100
