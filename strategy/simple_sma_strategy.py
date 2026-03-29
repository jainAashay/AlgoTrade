from typing import Dict, Any, Optional
import logging

from data_analysis.data_manager import get_data_manager
from strategy.base import StrategyBase

logger = logging.getLogger(__name__)

class SimpleSMAStrategy(StrategyBase):

    def generate_signal(self, symbol: str, position: Optional[Dict[str, Any]], instrument_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:

        market_data = get_data_manager().market_data
        df = market_data.get(symbol, {}).get(self.config["resolution"])

        if df is None or len(df) < 10:
            logger.warning(f"Insufficient data for {symbol}")
            return None

        strategy_config = self.config.get("strategy", {})
        min_move_percent = strategy_config.get("min_move_percent", 0.5)

        # === CLOSED CANDLES ===
        curr = df.iloc[-2]   # last closed
        prev = df.iloc[-3]
        prev_candles = df.iloc[-6:-2]  # last 4 candles

        # === EMA CHECK ===
        if "ema_5" not in df.columns or "ema_13" not in df.columns:
            logger.warning(f"EMA columns not found for {symbol}")
            return None

        ema5_now = df["ema_5"].iloc[-2]
        ema5_prev = df["ema_5"].iloc[-3]
        ema13 = df["ema_13"].iloc[-2]

        if not ema5_prev:
            return None

        # === EMA MOMENTUM (ORIGINAL LOGIC) ===
        ema_move_percent = ((ema5_now - ema5_prev) / ema5_prev) * 100
        logger.info(f"{symbol} EMA5 move %: {ema_move_percent:.4f}")

        bullish_ema_momentum = ema_move_percent > 0
        bearish_ema_momentum = ema_move_percent < 0
        move_condition = abs(ema_move_percent) >= min_move_percent

        # === CANDLE DIRECTION (ORIGINAL) ===
        curr_bullish = curr["close"] > curr["open"]
        curr_bearish = curr["close"] < curr["open"]

        # === EMA STRUCTURE (NEW) ===
        bullish_trend = curr["close"] > ema5_now > ema13
        bearish_trend = curr["close"] < ema5_now < ema13

        # === NO OVERLAP (NEW) ===
        prev_high = prev_candles["high"].max()
        prev_low = prev_candles["low"].min()

        no_overlap_long = curr["close"] > prev_high
        no_overlap_short = curr["close"] < prev_low

        logger.info(f"{symbol} prev_high: {prev_high}, prev_low: {prev_low}, curr_close: {curr['close']}")

        # =========================================================
        # ENTRY
        # =========================================================
        no_position = not position or position.get("size", 0) == 0

        if no_position:
            if bullish_ema_momentum and move_condition and curr_bullish and bullish_trend and no_overlap_long :
                logger.info(f"{symbol} ENTER LONG")
                return {"signal": "ENTER_LONG", "side": "buy"}

            if  bearish_ema_momentum and move_condition and curr_bearish and bearish_trend and no_overlap_short :
                logger.info(f"{symbol} ENTER SHORT")
                return {"signal": "ENTER_SHORT", "side": "sell"}

        # =========================================================
        # EXIT
        # =========================================================
        else:
            size = position.get("size", 0)

            # EMA reversal exit (your new rule)
            if size > 0 and ema5_now < ema13:
                logger.info(f"{symbol} EXIT LONG (EMA reversal)")
                return {"signal": "EXIT_LONG", "side": "sell"}

            if size < 0 and ema5_now > ema13:
                logger.info(f"{symbol} EXIT SHORT (EMA reversal)")
                return {"signal": "EXIT_SHORT", "side": "buy"}

        return None