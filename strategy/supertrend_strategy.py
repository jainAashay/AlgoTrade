from typing import Dict, Any, Optional
import logging

from data_analysis.data_manager import get_data_manager
from strategy.base import StrategyBase

logger = logging.getLogger(__name__)


class Strategy2(StrategyBase):

    def generate_signal(self,symbol: str,position: Optional[Dict[str, Any]],instrument_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:

        market_data = get_data_manager().market_data
        df = market_data.get(symbol, {}).get(self.config["resolution"])

        # Need at least 2 closed candles
        if df is None or len(df) < 2:
            logger.warning(f"Insufficient data for {symbol}: {len(df) if df is not None else 0} candles")
            return None

        # Last 2 CLOSED candles
        c2 = df.iloc[-3]
        c1 = df.iloc[-2]
        c0 = df.iloc[-1]


        volume_sma_2 = c1.get("volume_sma_2")
        volume_sma_5 = c1.get("volume_sma_5")

        if volume_sma_2 is None or volume_sma_5 is None:
            logger.warning(f"Missing volume SMA values for {symbol}")
            return None

        volume_multiplication = self.config.get("strategy").get("volume_multiplication", 2)

        volume_slope = volume_sma_2 / volume_sma_5

        logger.info(f"{symbol} volume slope : {volume_slope}")

        if volume_slope < volume_multiplication:
            logger.info(f"Volume SMA factor for {symbol} (last 3 : 5 candles) : {volume_slope:.4f} is less than configured")
            return None

        # -------------------- EMA Values --------------------
        ema_2 = c2.get("ema_5")
        ema_1 = c1.get("ema_5")

        open_2, close_2 = c2["open"], c2["close"]
        open_1, close_1 = c1["open"], c1["close"]

        # Candle direction analysis
        p_prev_bullish = close_2 > open_2
        prev_bullish = close_1 > open_1

        p_prev_bearish = close_2 < open_2
        prev_bearish = close_1 < open_1


        if ema_2 is None or ema_1 is None:
            logger.warning(f"Missing EMA values for {symbol}")
            return None

        # -------------------- EMA % Move --------------------
        ema_percent_move = self._ema_percent_change(ema_2, ema_1)

        logger.info(f"{symbol} EMA % move (last 2 candles) : {ema_percent_move:.4f}%")

        impulse_threshold = self.config.get("ema_impulse_threshold", 1)

        # ================= LONG CONDITIONS =================
        if ema_percent_move > impulse_threshold and prev_bullish and p_prev_bullish:
            logger.info(f"IMPULSE LONG signal for {symbol}")

            return {
                "signal": "ENTER_LONG",
                "side": "buy"
            }

        # ================= SHORT CONDITIONS =================
        if ema_percent_move < -impulse_threshold and prev_bearish and p_prev_bearish:
            logger.info(f"IMPULSE SHORT signal for {symbol}")

            return {
                "signal": "ENTER_SHORT",
                "side": "sell"
            }

        return None

    # ------------------------------------------------------------------

    def _ema_percent_change(self, prev_ema: float, curr_ema: float) -> float:
        """
        Calculate percentage change between two EMA values.
        """
        if prev_ema == 0:
            return 0.0
        return (curr_ema - prev_ema) / prev_ema

    # ------------------------------------------------------------------

    def _calculate_confidence(self, ema_percent_move: float, natr: float) -> float:
        """
        Confidence based on EMA impulse strength and volatility.
        """

        # # Normalize EMA move (1% = max confidence contribution)
        # slope_score = min(abs(ema_percent_move) / 1.0, 1.0)
        #
        # # Normalize NATR (2% = strong volatility)
        # volatility_score = min(natr / 2.0, 1.0)
        #
        # # Weighted average
        # confidence = (slope_score * 0.7) + (volatility_score * 0.3)

        return 1 #round(confidence, 3)
