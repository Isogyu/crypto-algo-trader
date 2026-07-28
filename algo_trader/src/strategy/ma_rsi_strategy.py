from __future__ import annotations
import uuid
from typing import List, Optional
from algo_trader.src.domain.models import Order, OrderSide, OrderType, PortfolioState, Signal
from algo_trader.src.strategy.base_strategy import BaseStrategy


class MA_RSI_Strategy(BaseStrategy):
    """Simple moving-average + RSI mean-reversion strategy."""

    def __init__(
        self,
        symbol: str,
        ma_fast: int = 5,
        ma_slow: int = 10,
        rsi_period: int = 7,
        overbought: float = 70.0,
        oversold: float = 30.0,
    ):
        self.symbol = symbol
        self.ma_fast = ma_fast
        self.ma_slow = ma_slow
        self.rsi_period = rsi_period
        self.overbought = overbought
        self.oversold = oversold

    def _ma(self, prices: List[float], window: int) -> float:
        if len(prices) < window:
            return prices[-1] if prices else 0.0
        return sum(prices[-window:]) / window

    def _rsi(self, prices: List[float]) -> float:
        period = self.rsi_period
        if len(prices) < period + 1:
            return 50.0
        gains = 0.0
        losses = 0.0
        for i in range(-period, 0):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains += change
            else:
                losses += -change
        if losses == 0:
            return 100.0
        rs = gains / losses
        return 100.0 - (100.0 / (1.0 + rs))

    def generate_signal(self, state: PortfolioState, price: float, prices: List[float]) -> Signal:
        ma_slow = self._ma(prices, self.ma_slow)
        ma_fast = self._ma(prices, self.ma_fast)
        rsi = self._rsi(prices)
        if price < ma_slow and price < ma_fast and rsi < self.oversold:
            return Signal.BUY
        if price > ma_slow and price > ma_fast and rsi > self.overbought:
            return Signal.SELL
        return Signal.HOLD

    def on_tick(self, state: PortfolioState, price: float, prices: List[float], max_size: float = 1.0) -> Optional[Order]:
        signal = self.generate_signal(state, price, prices)
        pos = state.positions.get(self.symbol)
        if signal == Signal.BUY:
            return Order(
                id=str(uuid.uuid4()),
                symbol=self.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=max_size,
            )
        if signal == Signal.SELL and pos and pos.side == OrderSide.BUY:
            return Order(
                id=str(uuid.uuid4()),
                symbol=self.symbol,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                amount=pos.amount,
            )
        return None
