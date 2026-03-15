"""
Strategy engine module.
"""
import importlib
from typing import Dict, List, Tuple, Optional, Any
import logging
from order_manager.order_manager import OrderManager

from strategy.base import StrategyBase
from data_analysis.data_manager import get_data_manager
from exceptions import StrategyError

logger = logging.getLogger(__name__)


class StrategyEngine:
    """Manages and evaluates multiple trading strategies."""

    def __init__(self, instruments: List[Dict[str, Any]], order_manager: OrderManager):
        """Initialize StrategyEngine with instruments."""
        self.strategies: Dict[str, StrategyBase] = {}
        self.data_manager = get_data_manager()
        self.order_manager = order_manager
        
        for inst in instruments:
            self._load_strategy(inst)
    
    def _load_strategy(self, instrument_config: Dict[str, Any]) -> None:
        """Load a strategy for an instrument."""
        symbol = instrument_config["symbol"]
        strat_cfg = instrument_config.get("strategy")
        
        if not strat_cfg:
            raise StrategyError(f"No strategy configuration for {symbol}")
        
        strategy_name = strat_cfg.get("name")
        if not strategy_name:
            raise StrategyError(f"No strategy name specified for {symbol}")
        
        try:
            module = importlib.import_module(f"strategy.{strategy_name}")
        except ImportError as e:
            raise StrategyError(f"Failed to import strategy module '{strategy_name}' for {symbol}") from e
        
        class_name = strat_cfg.get("class") or strat_cfg.get("class_name")
        if not class_name:
            raise StrategyError(f"No strategy class specified for {symbol}")
        
        strategy_cls = getattr(module, class_name, None)
        if strategy_cls is None:
            raise StrategyError(f"Strategy class '{class_name}' not found in module '{module.__name__}'")
        
        if not issubclass(strategy_cls, StrategyBase):
            raise StrategyError(f"Strategy class '{class_name}' must inherit from StrategyBase")
        
        try:
            self.strategies[symbol] = strategy_cls(instrument_config)
            logger.info(f"Loaded strategy {strategy_name} ({class_name}) for {symbol}")
        except Exception as e:
            raise StrategyError(f"Failed to instantiate strategy {class_name} for {symbol}") from e

    def generate_signal(self, symbol: str,instrument_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate a trading signal for a specific symbol."""
        strategy = self.strategies.get(symbol)
        if not strategy:
            logger.warning(f"No strategy loaded for {symbol}")
            return None

        position = self.order_manager.get_open_position(symbol)
        signal = strategy.generate_signal(symbol, position,instrument_config)
        if signal:
            logger.info(f"Signal generated: {symbol} -> {signal}")
        return signal

    def get_strategy(self, symbol: str) -> Optional[StrategyBase]:
        """Get strategy for a symbol."""
        return self.strategies.get(symbol)
