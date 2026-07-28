from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional
from algo_trader.src.domain.models import Order, PortfolioState, Position, Signal


class Logger(ABC):
    """Abstract logging interface used by domain services."""

    @abstractmethod
    def debug(self, msg: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def info(self, msg: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def warning(self, msg: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def error(self, msg: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def critical(self, msg: str) -> None:
        raise NotImplementedError


class ExchangeInterface(ABC):
    """Abstract exchange interface for broker/exchange adapters."""

    @abstractmethod
    def fetch_balance(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def fetch_ticker(self, symbol: str) -> float:
        raise NotImplementedError

    @abstractmethod
    def fetch_open_orders(self, symbol: str) -> List[Order]:
        raise NotImplementedError

    @abstractmethod
    def fetch_positions(self, symbol: str) -> List[Position]:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, order: Order) -> Order:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def cancel_all_orders(self, symbol: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def market_close_all(self, portfolio: PortfolioState) -> List[Order]:
        raise NotImplementedError


class Strategy(ABC):
    """Abstract base for all trading strategies."""

    @abstractmethod
    def generate_signal(self, state: PortfolioState, price: float, prices: List[float]) -> Signal:
        raise NotImplementedError

    @abstractmethod
    def on_tick(self, state: PortfolioState, price: float, prices: List[float]) -> Optional[Order]:
        raise NotImplementedError
