from __future__ import annotations
from typing import Set
from algo_trader.config.logging_config import get_logger
from algo_trader.src.domain.interfaces import ExchangeInterface
from algo_trader.src.domain.models import PortfolioState


class Reconciler:
    """Compare local state with the exchange and lock if discrepancies exist."""

    def __init__(self, exchange: ExchangeInterface, logger=None):
        self.exchange = exchange
        self.logger = logger or get_logger("reconciler")

    def reconcile(self, local_state: PortfolioState, symbol: str = None) -> bool:
        try:
            remote_orders = self.exchange.fetch_open_orders(symbol)
            remote_positions = self.exchange.fetch_positions(symbol)
        except Exception as exc:
            self.logger.error("Reconciliation API call failed", error=str(exc))
            local_state.system_locked = True
            return False

        remote_ids = {o.id for o in remote_orders}
        local_ids = {o.id for o in local_state.open_orders}
        if remote_ids != local_ids:
            self.logger.warning(
                "Open order mismatch",
                remote=remote_ids,
                local=local_ids,
            )
            local_state.system_locked = True
            return False

        remote_set = {(p.symbol, p.side, round(p.amount, 8)) for p in remote_positions}
        local_set = {(p.symbol, p.side, round(p.amount, 8)) for p in local_state.positions.values()}
        if remote_set != local_set:
            self.logger.warning(
                "Position mismatch",
                remote=remote_set,
                local=local_set,
            )
            local_state.system_locked = True
            return False

        return True
