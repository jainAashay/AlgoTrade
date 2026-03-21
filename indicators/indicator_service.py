"""
Technical indicators service module.

Provides IndicatorService class for applying technical indicators to OHLCV data.
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)


class IndicatorService:
    """
    Service for applying technical indicators to market data.
    
    Supports various indicators including EMA, RSI, and Supertrend.
    """
    
    def apply_indicators(self,df: pd.DataFrame,indicators_cfg: Optional[List[Dict[str, Any]]] = None) -> pd.DataFrame:

        if df.empty:
            return df

        indicators_cfg = indicators_cfg or []
        df = df.copy()

        for cfg in indicators_cfg:
            name = cfg.get("name")

            if name == "ema":
                length = cfg.get("length", 7)
                df[f"ema_{length}"] = ta.ema(df["close"], length=length)

            elif name == "sma":
                length = cfg.get("length", 7)
                df[f"sma_{length}"] = ta.sma(df["close"], length=length)

            elif name == "rsi":
                length = cfg.get("length", 7)
                df[f"rsi_{length}"] = ta.rsi(df["close"], length=length)

            elif name == "atr":
                length = cfg.get("length", 7)
                df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=length)

            elif name == "supertrend":
                length = cfg.get("length", 7)
                multiplier = cfg.get("multiplier", 2.0)

                st = ta.supertrend(df["high"],df["low"],df["close"],length=length,multiplier=multiplier)

                if st is None or st.empty:
                    continue

                for col in st.columns:
                    if col.startswith("SUPERTd_"):
                        df[f"supertrend_direction_{length}_{multiplier}"] = st[col]
                    elif col.startswith("SUPERT_"):
                        df[f"supertrend_value_{length}_{multiplier}"] = st[col]

            elif name == "adx":
                length = cfg.get("length", 14)
                adx = ta.adx(df["high"], df["low"], df["close"], length=length)
                df["adx"] = adx[f"ADX_{length}"]


            elif name == "natr":
                length = cfg.get("length", 14)
                df[f"natr_{length}"] = ta.natr(df["high"], df["low"], df["close"], length=length)

            elif name == "volume_sma":
                length = cfg.get("length", 20)
                volume_col = cfg.get("volume", "volume")
                if volume_col in df.columns:
                    df[f"volume_sma_{length}"] = ta.sma(df[volume_col], length=length)
                else:
                    logger.warning(f"Volume column '{volume_col}' not found in DataFrame")

        return df

    @staticmethod
    def _find_column_suffix(df: pd.DataFrame, prefix: str) -> Optional[str]:
        """
        Find the suffix of the first column in a DataFrame that starts with a given prefix.
        This is necessary because pandas_ta appends indicator parameters to column names.
        
        Args:
            df: DataFrame to search
            prefix: Prefix to match
            
        Returns:
            Column suffix if found, None otherwise
        """
        cols = [str(c) for c in df.columns if str(c).startswith(prefix)]
        if cols:
            # Assuming the suffix is everything after the prefix
            return cols[0][len(prefix):]
        return None


# Backward compatibility function
def apply_indicators(df: pd.DataFrame, indicators_cfg: Optional[List[Dict[str, Any]]] = None) -> pd.DataFrame:
    """Apply indicators (backward compatibility)."""
    return get_indicator_service().apply_indicators(df, indicators_cfg)


# Simple global instance
indicator_service = None

def get_indicator_service() -> IndicatorService:
    """Get the global OrderManager instance."""
    global indicator_service
    if indicator_service is None:
        indicator_service = IndicatorService()
    return indicator_service
