from __future__ import annotations
import random
import time
import uuid
from typing import Callable, List, TypeVar
import ccxt
from algo_trader.config.logging_config import get_logger
from algo_trader.src.domain.interfaces import ExchangeInterface
from algo_trader.src.domain.models import Order, OrderSide, OrderType, PortfolioState, Position

RT = TypeVar("RT")


def _retry(max_retries: int = 5, base_delay: float = 1.0) -> Callable[..., RT]:
    def decorator(func: Callable[..., RT]) -> Callable[..., RT]:
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RateLimitExceeded) as exc:
                    last_exc = exc
                    time.sleep(delay + random.random())
                    delay *= 2
            raise last_exc
        return wrapper
    return decorator


class CCXTAdapter(ExchangeInterface):
    """Production CCXT wrapper with exponential backoff and pre-order validation."""

    def __init__(self, config: dict):
        self.config = config
        self.exchange = self._build_exchange()
        self.logger = get_logger("ccxt_adapter")

    def _build_exchange(self):
        name = self.config.get("name", "bitflyer")
        cls = getattr(ccxt, name, None)
        if cls is None:
            raise ValueError(f"Unsupported exchange: {name}")
        return cls({
            "apiKey": self.config.get("api_key", ""),
            "secret": self.config.get("secret", ""),
            "sandbox": self.config.get("sandbox", True),
            "enableRateLimit": True,
        })

    def _last_price(self, symbol: str) -> float:
        return self.fetch_ticker(symbol)

    def _pre_validate(self, order: Order, portfolio_value: float) -> None:
        if order.amount <= 0:
            raise ValueError("Order amount must be positive")
        min_size = self.config.get("min_order_size", 0.001)
        if order.amount < min_size:
            raise ValueError(f"Order amount {order.amount} below minimum {min_size}")
        price = order.price or self._last_price(order.symbol)
        notional = order.amount * price
        max_leverage = self.config.get("max_leverage", 1)
        if notional > portfolio_value * max_leverage:
            raise ValueError("Order notional exceeds maximum leverage")
        if notional > portfolio_value * 5:
            raise ValueError("Fat-finger guard: order notional > 5x portfolio value")

    @_retry()
    def fetch_balance(self) -> dict:
        return self.exchange.fetch_balance()

    @_retry()
    def fetch_ticker(self, symbol: str) -> float:
        return float(self.exchange.fetch_ticker(symbol)["last"])

    @_retry()
    def fetch_open_orders(self, symbol: str = None) -> List[Order]:
        raw = self.exchange.fetch_open_orders(symbol) or []
        return [self._to_order(o) for o in raw]

    @_retry()
    def fetch_positions(self, symbol: str = None) -> List[Position]:
        if not hasattr(self.exchange, "fetch_positions"):
            return []
        raw = self.exchange.fetch_positions([symbol]) if symbol else self.exchange.fetch_positions()
        positions = []
        for p in raw:
            contracts = float(p.get("contracts", 0))
            if contracts:
                positions.append(Position(
                    symbol=p.get("symbol", symbol or ""),
                    side=OrderSide.BUY if contracts > 0 else OrderSide.SELL,
                    amount=abs(contracts),
                    average_entry_price=float(p.get("entryPrice") or p.get("average") or 0),
                ))
        return positions

    def _to_order(self, raw: dict) -> Order:
        side = OrderSide.BUY if raw.get("side") == "buy" else OrderSide.SELL
        typ = OrderType(raw.get("type", "limit"))
        return Order(
            id=str(raw.get("id", uuid.uuid4())),
            symbol=raw.get("symbol", ""),
            side=side,
            order_type=typ,
            amount=float(raw.get("amount", 0)),
            price=raw.get("price") and float(raw["price"]),
            status=raw.get("status", "open"),
        )

    @_retry()
    def place_order(self, order: Order, portfolio_value: float = 100_000.0) -> Order:
        self._pre_validate(order, portfolio_value)
        side = order.side.value
        order_type = order.order_type.value
        amount = order.amount
        price = order.price
        if order_type == "market":
            result = self.exchange.create_market_buy_order(order.symbol, amount) if side == "buy" else self.exchange.create_market_sell_order(order.symbol, amount)
        else:
            result = self.exchange.create_limit_buy_order(order.symbol, amount, price) if side == "buy" else self.exchange.create_limit_sell_order(order.symbol, amount, price)
        order.status = "open" if result.get("status") == "open" else "filled"
        return order

    @_retry()
    def cancel_order(self, order_id: str) -> bool:
        try:
            self.exchange.cancel_order(order_id)
            return True
        except ccxt.OrderNotFound:
            return False

    @_retry()
    def cancel_all_orders(self, symbol: str) -> None:
        try:
            self.exchange.cancel_all_orders(symbol)
        except Exception as exc:
            self.logger.warning("cancel_all_orders failed", error=str(exc))

    @_retry()
    def market_close_all(self, portfolio: PortfolioState) -> List[Order]:
        closed: List[Order] = []
        for symbol, pos in list(portfolio.positions.items()):
            side = OrderSide.SELL if pos.side == OrderSide.BUY else OrderSide.BUY
            order = Order(
                id=str(uuid.uuid4()),
                symbol=symbol,
                side=side,
                order_type=OrderType.MARKET,
                amount=pos.amount,
            )
            self.place_order(order)
            closed.append(order)
        return closed
