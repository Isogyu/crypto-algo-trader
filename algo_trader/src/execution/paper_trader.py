from __future__ import annotations
import uuid
from typing import Dict, List, Optional
from algo_trader.config.logging_config import get_logger
from algo_trader.src.domain.interfaces import ExchangeInterface
from algo_trader.src.domain.models import Order, OrderSide, OrderType, PortfolioState, Position, Trade


class PaperTrader(ExchangeInterface):
    """Realistic paper trading simulator with JPY PnL and tax logging."""

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        fee_rate: float = 0.0012,
        tax_logger=None,
        slippage_pips: float = 0.0,
        min_order_size: float = 0.001,
    ):
        self.portfolio = PortfolioState(cash_jpy=initial_cash)
        self.fee_rate = fee_rate
        self.tax_logger = tax_logger
        self.slippage_pips = slippage_pips
        self._min_order_size = min_order_size
        self._prices: Dict[str, float] = {}
        self._realized_pnl = 0.0
        self._total_fees = 0.0
        self._total_slippage = 0.0
        self.logger = get_logger("paper_trader")

    def _price(self, symbol: str) -> float:
        p = self._prices.get(symbol, 0.0)
        if p <= 0:
            raise ValueError(f"No price available for {symbol}")
        return p

    def fetch_ticker(self, symbol: str) -> float:
        return self._price(symbol)

    def fetch_balance(self) -> dict:
        total = self.portfolio.cash_jpy
        for pos in self.portfolio.positions.values():
            total += pos.amount * self._price(pos.symbol)
        return {"JPY": {"free": self.portfolio.cash_jpy, "total": total}}

    def fetch_open_orders(self, symbol: str = None) -> List[Order]:
        return [o for o in self.portfolio.open_orders if symbol is None or o.symbol == symbol]

    def fetch_positions(self, symbol: str = None) -> List[Position]:
        if symbol is None:
            return list(self.portfolio.positions.values())
        pos = self.portfolio.positions.get(symbol)
        return [pos] if pos else []

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price
        self._recalc_monthly_loss()

    def _slippage_price(self, order: Order, price: float) -> float:
        if self.slippage_pips <= 0:
            return price
        # 1 pip = 1 JPY for simplicity in JPY-denominated pairs
        slippage = self.slippage_pips
        return price + slippage if order.side == OrderSide.SELL else price - slippage

    def _validate(self, order: Order) -> None:
        if order.amount < self._min_order_size:
            raise ValueError(f"Order size {order.amount} below min {self._min_order_size}")
        price = self._price(order.symbol)
        notional = order.amount * price
        position_value = sum(
            p.amount * self._price(p.symbol) for p in self.portfolio.positions.values()
        )
        portfolio_value = self.portfolio.cash_jpy + position_value
        if notional > portfolio_value * 5:
            raise ValueError("Fat-finger guard: notional > 5x portfolio value")
        if order.side == OrderSide.BUY:
            cost = notional * (1.0 + self.fee_rate)
            if cost > self.portfolio.cash_jpy:
                raise ValueError("Insufficient cash for buy")

    def place_order(self, order: Order, portfolio_value: float = 100_000.0) -> Order:
        price = self._price(order.symbol)
        fill_price = self._slippage_price(order, price)
        self._validate(order)
        if order.order_type == OrderType.LIMIT and order.price is not None:
            if (order.side == OrderSide.BUY and fill_price > order.price) or (order.side == OrderSide.SELL and fill_price < order.price):
                order.status = "open"
                self.portfolio.open_orders.append(order)
                return order
        notional = order.amount * fill_price
        fee_jpy = notional * self.fee_rate
        slippage_jpy = order.amount * abs(price - fill_price)
        realized = self._update_portfolio(order, fill_price)
        trade = Trade(
            id=str(uuid.uuid4()),
            order_id=order.id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            amount=order.amount,
            fee_jpy=fee_jpy,
            slippage_jpy=slippage_jpy,
            realized_pnl_jpy=realized,
        )
        order.filled = order.amount
        order.status = "filled"
        order.price = fill_price
        order.fee_jpy = fee_jpy
        order.slippage_jpy = slippage_jpy
        self.portfolio.trades.append(trade)
        self._realized_pnl += realized
        self._total_fees += fee_jpy
        self._total_slippage += slippage_jpy
        self._recalc_monthly_loss()
        if self.tax_logger is not None:
            self.tax_logger.log_trade(trade, self.portfolio.current_monthly_loss)
        return order

    def _update_portfolio(self, order: Order, fill_price: float) -> float:
        realized = 0.0
        if order.side == OrderSide.BUY:
            pos = self.portfolio.positions.get(order.symbol)
            if pos and pos.side == OrderSide.BUY:
                new_amount = pos.amount + order.amount
                avg = (pos.amount * pos.average_entry_price + order.amount * fill_price) / new_amount
                pos.amount = new_amount
                pos.average_entry_price = avg
            else:
                self.portfolio.positions[order.symbol] = Position(
                    symbol=order.symbol,
                    side=OrderSide.BUY,
                    amount=order.amount,
                    average_entry_price=fill_price,
                )
            self.portfolio.cash_jpy -= order.amount * fill_price
        else:  # SELL
            pos = self.portfolio.positions.get(order.symbol)
            if pos is None or pos.side != OrderSide.BUY:
                raise ValueError("Cannot sell without a long position")
            realized = (fill_price - pos.average_entry_price) * order.amount
            pos.realized_pnl += realized
            self.portfolio.cash_jpy += order.amount * fill_price
            pos.amount -= order.amount
            if pos.amount <= 1e-12:
                del self.portfolio.positions[order.symbol]
        return realized

    def _recalc_monthly_loss(self) -> None:
        unrealized = 0.0
        for symbol, pos in self.portfolio.positions.items():
            price = self._prices.get(symbol, 0.0)
            unrealized += pos.unrealized_pnl(price)
        total_pnl = self._realized_pnl + unrealized
        self.portfolio.current_monthly_loss = max(0.0, -total_pnl) + self._total_fees + self._total_slippage

    def cancel_order(self, order_id: str) -> bool:
        for i, o in enumerate(self.portfolio.open_orders):
            if o.id == order_id:
                self.portfolio.open_orders.pop(i)
                return True
        return False

    def cancel_all_orders(self, symbol: str) -> None:
        self.portfolio.open_orders = [o for o in self.portfolio.open_orders if o.symbol != symbol]

    def market_close_all(self, portfolio: PortfolioState) -> List[Order]:
        closed: List[Order] = []
        for symbol, pos in list(self.portfolio.positions.items()):
            order = Order(
                id=str(uuid.uuid4()),
                symbol=symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                amount=pos.amount,
            )
            self.place_order(order)
            closed.append(order)
        return closed
