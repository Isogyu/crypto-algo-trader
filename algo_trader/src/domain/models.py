from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"


class Signal(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    amount: float = Field(gt=1e-12)
    price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"
    filled: float = 0.0
    fee_jpy: float = 0.0
    slippage_jpy: float = 0.0


class Trade(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    order_id: str
    symbol: str
    side: OrderSide
    price: float = Field(gt=0)
    amount: float = Field(gt=0)
    fee_jpy: float = 0.0
    slippage_jpy: float = 0.0
    realized_pnl_jpy: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str
    side: OrderSide
    amount: float = Field(gt=0)
    average_entry_price: float = Field(gt=0)
    realized_pnl: float = 0.0

    def unrealized_pnl(self, current_price: float) -> float:
        if current_price is None:
            return 0.0
        if self.side == OrderSide.BUY:
            return (current_price - self.average_entry_price) * self.amount
        return (self.average_entry_price - current_price) * self.amount

    def market_value(self, current_price: float) -> float:
        return self.amount * current_price


class PortfolioState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cash_jpy: float = 100_000.0
    positions: Dict[str, Position] = Field(default_factory=dict)
    open_orders: List[Order] = Field(default_factory=list)
    trades: List[Trade] = Field(default_factory=list)
    current_monthly_loss: float = 0.0
    system_locked: bool = False
    month: int = Field(default_factory=lambda: datetime.now(timezone.utc).month)
