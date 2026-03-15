"""
Data analysis and market data management module.
"""

from .data_manager import DataManager, get_data_manager, init_instrument, add_candle, bootstrap_candles

__all__ = ["DataManager", "get_data_manager", "init_instrument", "add_candle", "bootstrap_candles"]
