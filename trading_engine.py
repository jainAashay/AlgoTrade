"""
Trading engine module.
"""
import time
import logging
import threading
from typing import Dict, Any

from configs.config_loader import Config
from data_analysis.data_manager import get_data_manager
from strategy.strategy_engine import StrategyEngine
from order_manager.order_manager import get_order_manager
from risk_manager.risk_manager import get_risk_manager
from exceptions import OrderError, RiskManagementError
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

_SYSTEM_MODE = "BIR"
_SYSTEM_MODE_LOCK = threading.Lock()


def set_system_mode(mode: str) -> str:
    """Set global system mode. Supported values: BIR, OOR."""
    normalized_mode = mode.strip().upper()
    if normalized_mode not in {"BIR", "OOR"}:
        raise ValueError(f"Unsupported mode: {mode}")

    global _SYSTEM_MODE
    with _SYSTEM_MODE_LOCK:
        _SYSTEM_MODE = normalized_mode
    return _SYSTEM_MODE


def get_system_mode() -> str:
    """Get global system mode."""
    with _SYSTEM_MODE_LOCK:
        return _SYSTEM_MODE


class TradingEngine:
    """Main trading engine that orchestrates strategy evaluation and order execution."""
    
    def __init__(self):
        """Initialize TradingEngine."""
        # Use simple global instances
        self.data_manager = get_data_manager()
        self.order_manager = get_order_manager()
        self.risk_manager = get_risk_manager()
        
        self.instruments = Config.get("instruments")
        self._initialize_instruments()
        self.strategy_engine = StrategyEngine(self.instruments, self.order_manager)
        
        logger.info("TradingEngine initialized successfully")
    
    def _initialize_instruments(self) -> None:
        """Initialize market data for all instruments."""
        for inst in self.instruments:
            symbol = inst["symbol"]
            resolution = inst["resolution"]
            leverage = inst.get("leverage")
            self.data_manager.init_instrument(symbol,resolution)
            try:
                self.data_manager.bootstrap_candles(inst, self.order_manager.rest_client)
                logger.info(f"Initialized and bootstrapped {symbol}")
            except Exception as e:
                logger.error(f"Failed to bootstrap {symbol}: {e}", exc_info=True)
                raise e
            if leverage:
                self.order_manager.change_leverage(symbol, leverage)
                logger.info(f"Set leverage for {symbol} to {leverage}x")

    def _place_order(self, symbol: str, signal: Dict[str, Any], inst: Dict[str, Any]) -> None:
        logger.info(f"Signal generated: {signal}")
        try:

            side = signal["side"]
            qty = inst["quantity"]

            # --------------------------------------------------
            # 3. Check current position
            # --------------------------------------------------

            position = self.order_manager.get_open_position(symbol)
            pos_side = self.order_manager.position_side(position)

            # Same direction → nothing to do
            if pos_side == side:
                logger.info(f"Already in {side} position for {symbol}")
                return

            self.order_manager.cancel_all_orders(symbol)

            # --------------------------------------------------
            # 4. Opposite position → flatten first
            # --------------------------------------------------
            if pos_side and pos_side != side:
                logger.info(f"Trend reversal on {symbol}. Closing existing position.")
                self.order_manager.close_position_reduce_only(symbol, position)
                logger.info(f"Successfully Closed existing position {pos_side} on {symbol}")
                return  # let next signal handle fresh entry

            # --------------------------------------------------
            # 1. Risk check for entry order
            # --------------------------------------------------
            if not self.risk_manager.allowed_to_trade(symbol,inst):
                logger.warning(f"Trading blocked by risk manager for {symbol}")
                return
            # --------------------------------------------------
            # 7. Entry price selection
            # --------------------------------------------------
            best_bid, best_ask = self.order_manager.get_best_bid_ask(symbol)
            entry_price = best_ask if side == "buy" else best_bid

            # --------------------------------------------------
            # 8. Place ENTRY order
            # --------------------------------------------------
            if entry_price:
                logger.info(f"Placing entry order for {symbol} at price {entry_price}")
                order = self.order_manager.place_ioc_limit_order(symbol, side, qty, entry_price)
            else:
                logger.warning(f"No entry price available for {symbol}")
                return

            logger.info(f"Entry order placed for {symbol}: {order['id']}")

        except RiskManagementError as e:
            logger.warning(f"Risk management blocked trade for {symbol}: {e}")
        except OrderError as e:
            logger.error(f"Order error for {symbol}: {e}")
        except Exception as e:
            logger.exception(f"Unhandled error while processing {symbol} : {e}")

    def _process_signal(self, symbol: str, signal: Dict[str, Any]) -> None:
        """Process a trading signal and execute orders."""
        try:
            inst = next((i for i in self.instruments if i["symbol"] == symbol), None)
            if not inst:
                logger.error(f"Instrument configuration not found for {symbol}")
                return

            self._place_order(symbol, signal, inst)
            
        except RiskManagementError as e:
            logger.warning(f"Risk management blocked trade for {symbol}: {e}")
        except OrderError as e:
            logger.error(f"Order error for {symbol}: {e}")
        except Exception as e:
            logger.exception(f"Error processing signal for {symbol}: {e}")

    def run(self, loop_interval: float = 10.0) -> None:
        """Run the main trading loop in parallel."""
        logger.info("Starting trading engine main loop")

        # Create executor once (better than recreating every loop)
        max_workers = min(8, len(self.instruments))  # avoid too many threads

        with ThreadPoolExecutor(max_workers=max_workers) as executor:

            while True:
                try:
                    current_mode = get_system_mode()
                    if current_mode != "BIR":
                        logger.info("System mode is OOR. Skipping trading iteration.")
                        time.sleep(loop_interval)
                        continue

                    # Submit all instruments in parallel
                    futures = [
                        executor.submit(self._process_instrument, inst)
                        for inst in self.instruments
                    ]

                    # Wait for completion & catch errors properly
                    for future in as_completed(futures):
                        try:
                            future.result()
                        except Exception as e:
                            logger.exception(f"Instrument execution error: {e}")

                except KeyboardInterrupt:
                    logger.info("Trading engine stopped by user")
                    break
                except Exception as e:
                    logger.exception(f"Main loop error: {e}")

                time.sleep(loop_interval)

    def _process_instrument(self, inst):
        symbol = inst["symbol"]

        signal = self.strategy_engine.generate_signal(symbol, inst)

        if signal is not None:
            logger.info(f"Signal generated for {symbol}: {signal}")
            self._process_signal(symbol, signal)

