from typing import Dict, Any, Optional
import logging

from data_analysis.data_manager import get_data_manager
from strategy.base import StrategyBase

logger = logging.getLogger(__name__)

class SimpleSMAStrategy(StrategyBase):

    def generate_signal(self,symbol: str,position: Optional[Dict[str, Any]],instrument_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:

        market_data = get_data_manager().market_data
        df = market_data.get(symbol, {}).get(self.config["resolution"])

        if df is None or len(df) < 5:
            logger.warning(f"Insufficient data for {symbol}")
            return None

        strategy_config = self.config.get("strategy", {})
        min_move_percent = strategy_config.get("min_move_percent", 0.5)

        # === CLOSED CANDLES ===
        curr = df.iloc[-2]   # last closed

        # === EMA CHECK ===
        if "ema_5" not in df.columns:
            logger.warning(f"ema_5 column not found for {symbol}")
            return None

        ema_now = df["ema_5"].iloc[-2]
        ema_prev = df["ema_5"].iloc[-3]

        if not ema_prev:
            return None

        ema_move_percent = ((ema_now - ema_prev) / ema_prev) * 100
        logger.info(f"{symbol} EMA5 move %: {ema_move_percent:.4f}")

        bullish_ema = ema_move_percent > 0
        bearish_ema = ema_move_percent < 0
        move_condition = abs(ema_move_percent) >= min_move_percent

        # === CURRENT CANDLE DIRECTION ===
        curr_bullish = curr["close"] > curr["open"]
        curr_bearish = curr["close"] < curr["open"]

        # =========================================================
        # ENTRY
        # =========================================================
        no_position = not position or position.get("size", 0) == 0
        logger.info(f"Current Position : {position}")

        if no_position:
            if bullish_ema and move_condition and curr_bullish:
                logger.info(f"{symbol} ENTER LONG")
                return {"signal": "ENTER_LONG", "side": "buy"}

            if bearish_ema and move_condition and curr_bearish:
                logger.info(f"{symbol} ENTER SHORT")
                return {"signal": "ENTER_SHORT", "side": "sell"}

        # =========================================================
        # EXIT / REVERSE
        # =========================================================
        else:
            size = position.get("size",0)

            if size > 0 and bearish_ema:
                logger.info(f"{symbol} EXIT LONG")
                return {"signal": "EXIT_LONG", "side": "sell"}

            if size < 0  and bullish_ema:
                logger.info(f"{symbol} EXIT SHORT")
                return {"signal": "EXIT_SHORT", "side": "buy"}

        return None