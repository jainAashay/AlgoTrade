"""
Market data management module.

Provides DataManager class for managing OHLCV data and technical indicators.
"""
import time
from typing import Dict, List, Optional, Any
import pandas as pd
import logging
from rest_client import get_rest_client

from indicators.indicator_service import IndicatorService
from exceptions import DataError
from utils.common_utils import CommonUtils

logger = logging.getLogger(__name__)


class DataManager:
    """
    Manages market data (OHLCV candles) and applies technical indicators.
    """
    
    def __init__(self, max_candles: int = 1500):
        """Initialize the DataManager."""
        self.market_data: Dict[str, Dict[str, pd.DataFrame]] = {}
        self.symbol_to_product_look_up: Dict[str,str] = {}
        self.max_candles = max_candles
        self.indicator_service = IndicatorService()
        self.rest_client = get_rest_client()
        
    def init_instrument(self, symbol: str, resolution: str) -> None:
        """Initialize data storage for an instrument."""
        if symbol not in self.market_data:
            self.market_data[symbol] = {}
        
        if resolution not in self.market_data[symbol]:
            self.market_data[symbol][resolution] = pd.DataFrame(
                columns=["ts", "open", "high", "low", "close", "volume"]
            )

        assets = self.rest_client.get_assets()
        for asset in assets:
            self.symbol_to_product_look_up[asset["symbol"]] = asset["id"]

        logger.info(f"Initialized instrument {symbol} for timeframe: {resolution}")

    def add_candle(self, symbol: str, timeframe: str, candle: List[Any], indicators_cfg: Optional[List[Dict[str, Any]]] = None) -> None:
        """Add or update a candle in the market data."""
        if symbol not in self.market_data or timeframe not in self.market_data[symbol]:
            logger.warning(f"Received candle before init: {symbol} {timeframe}")
            return

        df = self.market_data[symbol][timeframe].copy()
        ts = self._normalize_timestamp(candle[0])

        row = {
            "ts": ts,
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[5]),
        }

        # Upsert logic
        if not df.empty and ts in df["ts"].values:
            idx = df.index[df["ts"] == ts][0]
            df.loc[idx, ["open", "high", "low", "close", "volume"]] = [
                row["open"], row["high"], row["low"], row["close"], row["volume"]
            ]
        else:
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

        # Sort & cap
        df = df.sort_values("ts").tail(self.max_candles).reset_index(drop=True)

        # Apply indicators
        if indicators_cfg:
            df = self.indicator_service.apply_indicators(df, indicators_cfg)

        self.market_data[symbol][timeframe] = df
        # Log formatted data with clear column headings
        df_tail = self.market_data[symbol][timeframe].tail(5)
        logger.info(f"Market_data updated for {symbol} {timeframe} - Latest 5 rows:")
        logger.info(f"Columns: {list(df_tail.columns)}")
        for idx, row in df_tail.iterrows():
            row_str = " | ".join([f"{col}: {val:.6f}" if isinstance(val, (int, float)) else f"{col}: {val}" 
                                 for col, val in row.items()])
            logger.info(f"  Row {idx}: {row_str}")
        logger.debug(f"Added/updated candle {symbol} {timeframe} ts={ts} close={row['close']}, length={len(self.market_data[symbol][timeframe])}")

    def seed_candles(self, symbol: str, resolution: str, candles: List[List[Any]], indicators_cfg: Optional[List[Dict[str, Any]]] = None) -> None:
        """Seed historical candles for an instrument."""
        if not candles:
            logger.warning(f"No candles provided for {symbol} {resolution}")
            return
            
        df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume"])
        df = df.dropna(how="any").tail(self.max_candles).sort_values("ts").reset_index(drop=True)
        
        df = self.indicator_service.apply_indicators(df, indicators_cfg)
        self.market_data[symbol][resolution] = df

    def bootstrap_candles(self, instrument_config: Dict[str, Any], rest_client) -> None:
        """Bootstrap historical candles for an instrument."""
        symbol = instrument_config["symbol"]
        resolution = str(instrument_config["resolution"])
        bootstrap_length = int(instrument_config.get("bootstrap_length", 120))
        indicators_cfg = instrument_config.get("strategy", {}).get("indicators", {})
        
        now = int(time.time())
        sec = CommonUtils.resolution_to_seconds(resolution)
        start = now - (bootstrap_length * sec)
        
        logger.info(f"Bootstrapping {symbol} {resolution}: fetching {bootstrap_length} candles from {start} to {now}")

        try:
            ohlc = rest_client.fetch_ohlc(symbol, resolution, start, now)
            candles = [
                [c["ts"], c["open"], c["high"], c["low"], c["close"], c["volume"]]
                for c in ohlc
            ]
            
            if candles:
                self.seed_candles(symbol, resolution, candles, indicators_cfg)
            else:
                logger.warning(f"No historical candles fetched for {symbol} {resolution}")
        except Exception as e:
            logger.error(f"Error bootstrapping candles for {symbol}: {e}")
            raise DataError(f"Failed to bootstrap candles for {symbol}") from e
        
        logger.info(f"Bootstrap completed for {symbol}")

    def get_dataframe(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Get the DataFrame for a symbol and timeframe."""
        if symbol not in self.market_data:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        
        if timeframe not in self.market_data[symbol]:
            return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
        
        return self.market_data[symbol][timeframe].copy()

    @staticmethod
    def _normalize_timestamp(ts_micro: int) -> int:
        """Normalize timestamp from microseconds to seconds."""
        return ts_micro // 1_000_000


# Simple global instance
_data_manager = None

def get_data_manager() -> DataManager:
    """Get the global DataManager instance."""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager


# Backward compatibility
def init_instrument(inst: Dict[str, Any]) -> None:
    """Initialize instrument (backward compatibility)."""
    get_data_manager().init_instrument(inst["symbol"], inst["resolution"])

def add_candle(symbol: str, tf: str, candle: List[Any], indicators_cfg: Optional[Dict[str, Any]] = None) -> None:
    """Add candle (backward compatibility)."""
    get_data_manager().add_candle(symbol, tf, candle, indicators_cfg)

def bootstrap_candles(inst: Dict[str, Any]) -> None:
    """Bootstrap candles (backward compatibility)."""
    from rest_client.rest_client import get_rest_client
    get_data_manager().bootstrap_candles(inst, get_rest_client())
