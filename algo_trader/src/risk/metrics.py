from __future__ import annotations
from typing import Dict, List
from algo_trader.src.domain.models import PortfolioState, Position, Trade


class RiskMetrics:
    """Pure functions and cumulative trackers for PnL and loss-budget calculations."""

    def __init__(self, monthly_loss_cap_jpy: float = 30_000.0):
        self.monthly_loss_cap_jpy = monthly_loss_cap_jpy

    def current_monthly_loss(self, portfolio: PortfolioState) -> float:
        return max(0.0, portfolio.current_monthly_loss)

    def realized_pnl(self, trades: List[Trade]) -> float:
        return sum(t.realized_pnl_jpy for t in trades)

    def unrealized_pnl(
        self, positions: List[Position], prices: Dict[str, float]
    ) -> float:
        total = 0.0
        for pos in positions:
            price = prices.get(pos.symbol)
            if price is not None:
                total += pos.unrealized_pnl(price)
        return total

    def fees_and_slippage(self, trades: List[Trade]) -> float:
        return sum(t.fee_jpy + t.slippage_jpy for t in trades)

    def remaining_loss_budget(self, portfolio: PortfolioState) -> float:
        return max(0.0, self.monthly_loss_cap_jpy - portfolio.current_monthly_loss)
