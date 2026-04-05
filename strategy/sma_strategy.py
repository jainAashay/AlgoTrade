from typing import Dict, Any, Optional
import logging

from data_analysis.data_manager import get_data_manager
from strategy.base import StrategyBase

logger = logging.getLogger(__name__)

class SMAStrategy(StrategyBase):

    def generate_signal(self,symbol: str,position: Optional[Dict[str, Any]],instrument_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:

        market_data = get_data_manager().market_data
        df = market_data.get(symbol, {}).get(self.config["resolution"])

        if df is None or len(df) < 10:
            logger.warning(f"Insufficient data for {symbol}")
            return None

        strategy_config = self.config.get("strategy", {})
        min_move_percent = strategy_config.get("min_move_percent", 0.5)

        # === CLOSED CANDLES ===
        curr = df.iloc[-2]   # last closed candle
        prev = df.iloc[-3]

        # === EMA CHECK ===
        if "ema_5" not in df.columns or "ema_13" not in df.columns:
            logger.warning(f"EMA columns not found for {symbol}")
            return None

        ema5_now = df["ema_5"].iloc[-2]
        ema5_prev = df["ema_5"].iloc[-3]
        ema13 = df["ema_13"].iloc[-2]

        if not ema5_prev:
            return None

        # === EMA % MOVE ===
        ema_move_percent = ((ema5_now - ema5_prev) / ema5_prev) * 100
        logger.info(f"{symbol} EMA5 move %: {ema_move_percent:.4f}")

        move_condition = abs(ema_move_percent) >= min_move_percent

        # === YOUR CONDITIONS ===
        gap_up = curr["open"] >= prev["close"]
        gap_down = curr["open"] < prev["close"]

        bullish_trend = ema5_now > ema13
        bearish_trend = ema5_now < ema13

        # === CANDLE DIRECTION (NEW ADDITION) ===
        curr_bullish = curr["close"] > curr["open"]
        curr_bearish = curr["close"] < curr["open"]

        # =========================================================
        # ENTRY
        # =========================================================
        no_position = not position or position.get("size", 0) == 0

        if no_position:
            if gap_up and bullish_trend and move_condition and curr_bullish:
                logger.info(f"{symbol} ENTER LONG")
                return {"signal": "ENTER_LONG", "side": "buy"}

            if gap_down and bearish_trend and move_condition and curr_bearish:
                logger.info(f"{symbol} ENTER SHORT")
                return {"signal": "ENTER_SHORT", "side": "sell"}

        # =========================================================
        # EXIT
        # =========================================================
        else:
            size = position.get("size", 0)

            if size > 0 and ema5_now < ema13:
                logger.info(f"{symbol} EXIT LONG")
                return {"signal": "EXIT_LONG", "side": "sell"}

            if size < 0 and ema5_now > ema13:
                logger.info(f"{symbol} EXIT SHORT")
                return {"signal": "EXIT_SHORT", "side": "buy"}

        return None