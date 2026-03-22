from typing import Dict, Any, Optional
import logging

from data_analysis.data_manager import get_data_manager
from strategy.base import StrategyBase

logger = logging.getLogger(__name__)


class SMAStrategy(StrategyBase):

    def generate_signal(self,symbol: str,position: Optional[Dict[str, Any]],instrument_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:

        market_data = get_data_manager().market_data
        df = market_data.get(symbol, {}).get(self.config["resolution"])

        if df is None or len(df) < 5:
            logger.warning(f"Insufficient data for {symbol}")
            return None

        # === CONFIG ===
        strategy_config = self.config.get("strategy", {})
        min_move_percent = strategy_config.get("min_move_percent", 0.5)

        # === CLOSED CANDLES ===
        curr = df.iloc[-2]   # last closed
        prev = df.iloc[-3]   # previous closed

        # === EMA CHECK ===
        if "ema_5" not in df.columns:
            logger.warning(f"ema_5 column not found in data for {symbol}")
            return None

        ema_now = df["ema_5"].iloc[-2]
        ema_prev = df["ema_5"].iloc[-3]

        if ema_prev is None or ema_prev == 0:
            return None

        ema_move_percent = ((ema_now - ema_prev) / ema_prev) * 100

        bullish_ema = ema_move_percent > 0
        bearish_ema = ema_move_percent < 0
        move_condition = abs(ema_move_percent) >= min_move_percent

        logger.info(f"{symbol} EMA5 move %: {ema_move_percent:.4f}")

        # === CANDLE DIRECTION ===
        curr_bullish = curr["close"] > curr["open"]
        curr_bearish = curr["close"] < curr["open"]

        prev_bullish = prev["close"] > prev["open"]
        prev_bearish = prev["close"] < prev["open"]

        # === BOTH CANDLES SAME DIRECTION ===
        bullish_candles = curr_bullish and prev_bullish
        bearish_candles = curr_bearish and prev_bearish

        # =========================================================
        # === ENTRY CONDITIONS (only if NOT in position)
        # =========================================================
        if not position and position.get("size",0)==0:

            long_signal = ( bullish_ema and move_condition and bullish_candles )

            short_signal = ( bearish_ema and move_condition and bearish_candles )

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

        # =========================================================
        # === EXIT / REVERSE CONDITIONS (if already in position)
        # =========================================================
        else:
            position_side = position.get("side")

            # If in LONG and EMA turns bearish → exit/reverse
            if position_side == "buy" and bearish_ema :
                logger.info(f"{symbol} EXIT LONG / ENTER SHORT")
                return {
                    "signal": "EXIT_LONG",
                    "side": "sell"
                }

            # If in SHORT and EMA turns bullish → exit/reverse
            if position_side == "sell" and bullish_ema :
                logger.info(f"{symbol} EXIT SHORT / ENTER LONG")
                return {
                    "signal": "EXIT_SHORT",
                    "side": "buy"
                }

        return None