from typing import Dict, Any, Optional
import logging

from data_analysis.data_manager import get_data_manager
from strategy.base import StrategyBase

logger = logging.getLogger(__name__)


class SuperTrendImpulseStrategy(StrategyBase):

    def generate_signal(self,
                        symbol: str,
                        position: Optional[Dict[str, Any]],
                        instrument_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:

        market_data = get_data_manager().market_data
        df = market_data.get(symbol, {}).get(self.config["resolution"])

        if df is None or len(df) < 3:
            logger.warning(f"Insufficient data for {symbol}")
            return None

        # Last 3 CLOSED candles
        p_prev_candle = df.iloc[-3]
        prev_candle = df.iloc[-2]
        curr_candle = df.iloc[-1]

        p_prev_supertrend = p_prev_candle.get("supertrend_value_5_1.2")
        prev_supertrend = prev_candle.get("supertrend_value_5_1.2")
        curr_supertrend = curr_candle.get("supertrend_value_5_1.2")

        if p_prev_supertrend is None or prev_supertrend is None or curr_supertrend is None:
            logger.warning(f"{symbol} Supertrend data missing.")
            return None

        # --------------------------------------------------
        # Supertrend % Impulse Check
        # --------------------------------------------------
        st_percent_move = self._percent_move(p_prev_supertrend, prev_supertrend)
        threshold = self.config.get("strategy", {}).get("supertrend_diff_threshold", 0.4)

        logger.info(f"{symbol} Supertrend % move: {st_percent_move:.4f}")

        if abs(st_percent_move) < threshold:
            logger.info(f"{symbol} Supertrend move not strong enough.")
            return None

        # --------------------------------------------------
        # Extract OHLC
        # --------------------------------------------------
        prev_open = prev_candle["open"]
        prev_close = prev_candle["close"]
        prev_high = prev_candle["high"]
        prev_low = prev_candle["low"]

        curr_open = curr_candle["open"]
        curr_close = curr_candle["close"]

        # --------------------------------------------------
        # Wick Calculations ON PREVIOUS CANDLE
        # --------------------------------------------------
        total_range = prev_high - prev_low
        if total_range <= 0:
            return None

        upper_wick = prev_high - max(prev_open, prev_close)
        lower_wick = min(prev_open, prev_close) - prev_low

        upper_ratio = upper_wick / total_range
        lower_ratio = lower_wick / total_range

        wick_threshold = self.config.get("strategy", {}).get("wick_threshold", 0.05)

        # --------------------------------------------------
        # Trend Direction Logic
        # --------------------------------------------------
        bullish_trend = (
            curr_close > curr_open and
            curr_close > curr_supertrend and
            p_prev_supertrend <= prev_supertrend < curr_supertrend and
            prev_close > prev_open and          # previous candle bullish
            upper_ratio < wick_threshold        # strong bullish candle
        )

        bearish_trend = (
            curr_close < curr_open and
            curr_close < curr_supertrend and
            p_prev_supertrend >= prev_supertrend > curr_supertrend and
            prev_close < prev_open and          # previous candle bearish
            lower_ratio < wick_threshold        # strong bearish candle
        )

        # ==========================================================
        # ====================== LONG ==============================
        # ==========================================================

        if bullish_trend:
            logger.info(f"{symbol} SUPERTREND IMPULSE LONG (Prev Wick Filter)")

            return {
                "signal": "ENTER_LONG",
                "side": "buy",
                "trailing_stop_loss": curr_supertrend
            }

        # ==========================================================
        # ====================== SHORT =============================
        # ==========================================================

        if bearish_trend:
            logger.info(f"{symbol} SUPERTREND IMPULSE SHORT (Prev Wick Filter)")

            return {
                "signal": "ENTER_SHORT",
                "side": "sell",
                "trailing_stop_loss": curr_supertrend
            }

        return None

    # -------------------------------------------------------------

    def _percent_move(self, value1: float, value2: float) -> float:
        if value1 == 0:
            return 0.0
        return ((value2 - value1) / value1) * 100