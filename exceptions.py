"""
Custom exceptions for the AlgoTrading system.
"""


class AlgoTradingException(Exception):
    """Base exception for all AlgoTrading errors."""
    pass


class ConfigurationError(AlgoTradingException):
    """Raised when there's a configuration error."""
    pass


class DataError(AlgoTradingException):
    """Raised when there's a data-related error."""
    pass


class OrderError(AlgoTradingException):
    """Raised when there's an order-related error."""
    pass


class StrategyError(AlgoTradingException):
    """Raised when there's a strategy-related error."""
    pass


class RiskManagementError(AlgoTradingException):
    """Raised when risk management rules are violated."""
    pass


class ExchangeError(AlgoTradingException):
    """Raised when there's an exchange API error."""
    pass
