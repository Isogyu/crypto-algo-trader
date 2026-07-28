from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from algo_trader.src.domain.models import Trade


class TaxLogger:
    """Exports every trade event to a JSONL file suitable for Japanese tax reporting."""

    def __init__(self, log_path: str = "data/tax_trade_log.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_trade(self, trade: Trade, current_monthly_loss_jpy: float) -> None:
        record = {
            "timestamp": trade.timestamp.isoformat(),
            "trade_id": trade.id,
            "symbol": trade.symbol,
            "side": trade.side.value,
            "price": float(trade.price),
            "amount": float(trade.amount),
            "fee_jpy": float(trade.fee_jpy),
            "slippage_jpy": float(trade.slippage_jpy),
            "realized_pnl_jpy": float(trade.realized_pnl_jpy),
            "total_monthly_loss_jpy": float(current_monthly_loss_jpy),
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def log_event(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        price: float,
        amount: float,
        fee_jpy: float,
        slippage_jpy: float,
        realized_pnl_jpy: float,
        current_monthly_loss_jpy: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        record = {
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side,
            "price": float(price),
            "amount": float(amount),
            "fee_jpy": float(fee_jpy),
            "slippage_jpy": float(slippage_jpy),
            "realized_pnl_jpy": float(realized_pnl_jpy),
            "total_monthly_loss_jpy": float(current_monthly_loss_jpy),
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
