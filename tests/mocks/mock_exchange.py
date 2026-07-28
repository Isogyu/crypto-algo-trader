from __future__ import annotations
from typing import List
from algo_trader.src.domain.interfaces import ExchangeInterface
from algo_trader.src.domain.models import Order, OrderSide, OrderType, PortfolioState, Position


class MockExchange(ExchangeInterface):
    """In-memory exchange used for integration tests."""

    def __init__(self, prices=None, positions=None, open_orders=None, cash=100_000.0):
        self._prices = prices or {}
        self._positions = positions or []
        self._open_orders = open_orders or []
        self._cash = cash

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price

    def fetch_balance(self) -> dict:
        total = self._cash + sum(
            p.amount * self._prices.get(p.symbol, 0.0) for p in self._positions
        )
        return {"JPY": {"free": self._cash, "total": total}}

    def fetch_ticker(self, symbol: str) -> float:
        return self._prices[symbol]

    def fetch_open_orders(self, symbol: str = None) -> List[Order]:
        return [o for o in self._open_orders if symbol is None or o.symbol == symbol]

    def fetch_positions(self, symbol: str = None) -> List[Position]:
        return [p for p in self._positions if symbol is None or p.symbol == symbol]

    def place_order(self, order: Order) -> Order:
        self._open_orders.append(order)
        return order

    def cancel_order(self, order_id: str) -> bool:
        for i, o in enumerate(self._open_orders):
            if o.id == order_id:
                self._open_orders.pop(i)
                return True
        return False

    def cancel_all_orders(self, symbol: str) -> None:
        self._open_orders = [o for o in self._open_orders if o.symbol != symbol]

    def market_close_all(self, portfolio: PortfolioState) -> List[Order]:
        return []
