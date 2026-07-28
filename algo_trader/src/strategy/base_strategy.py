from __future__ import annotations
from abc import ABC
from typing import List, Optional
from algo_trader.src.domain.interfaces import Strategy
from algo_trader.src.domain.models import Order, PortfolioState, Signal


class BaseStrategy(Strategy, ABC):
    """Base class for all trading strategies with helper hooks."""

    def generate_signal(self, state: PortfolioState, price: float, prices: List[float]) -> Signal:
        raise NotImplementedError

    def on_tick(self, state: PortfolioState, price: float, prices: List[float], max_size: float = 1.0) -> Optional[Order]:
        raise NotImplementedError
