"""
Base strategy module.

Provides StrategyBase abstract class that all trading strategies must inherit from.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd


class StrategyBase(ABC):
    """
    Base class for all trading strategies.
    
    All strategies must inherit from this class and implement the generate_signal method.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize strategy with configuration.
        
        Args:
            config: Strategy configuration dictionary
        """
        self.config = config
    
    @abstractmethod
    def generate_signal(self,symbol: str,position: Optional[Dict[str, Any]],instrument_config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Generate a trading signal based on market data.
        
        Args:
            symbol: The trading symbol for which to generate the signal.
            dataframes: Dictionary of {timeframe: DataFrame} for the symbol
            position: Current position dictionary (None if flat)
            
        Returns:
            Signal dictionary with keys:
                - "signal": Signal type (e.g., "LONG", "SHORT", "EXIT_LONG")
                - "side": "buy" or "sell"
            Returns None if no signal
        """
        raise NotImplementedError("Subclasses must implement generate_signal")
