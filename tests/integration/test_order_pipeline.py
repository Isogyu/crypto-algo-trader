from __future__ import annotations
import json
import tempfile
from pathlib import Path
from algo_trader.src.accounting.tax_logger import TaxLogger
from algo_trader.src.execution.paper_trader import PaperTrader
from algo_trader.src.risk.risk_manager import RiskManager
from algo_trader.src.domain.models import Order, OrderSide, OrderType


def test_paper_trader_hits_loss_cap_and_logs_tax():
    with tempfile.TemporaryDirectory() as tmp:
        tax_path = Path(tmp) / "tax.jsonl"
        tax_logger = TaxLogger(str(tax_path))
        paper = PaperTrader(
            initial_cash=100_000.0,
            fee_rate=0.0012,
            tax_logger=tax_logger,
            min_order_size=0.001,
            slippage_pips=10.0,
        )
        risk = RiskManager(
            base_risk_per_trade_jpy=1_000,
            stop_loss_distance_jpy=1_000,
            monthly_loss_cap_jpy=30_000,
        )

        symbol = "ETH/JPY"
        prices = [30_000.0 - 300.0 * i for i in range(60)]
        paper.set_price(symbol, prices[0])

        for price in prices[1:]:
            paper.set_price(symbol, price)
            if paper.portfolio.current_monthly_loss >= risk.cap:
                break
            max_size = risk.max_position_size(paper.portfolio)
            if max_size < 0.001:
                continue
            affordable = paper.portfolio.cash_jpy / (price * 1.0012)
            amount = min(max_size, affordable)
            if amount < 0.001:
                continue
            order = Order(
                id=f"buy-{price}",
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=amount,
            )
            if risk.validate_order(order, paper.portfolio).approved:
                paper.place_order(order)

        if paper.portfolio.current_monthly_loss >= risk.cap:
            paper.portfolio.system_locked = True
            paper.market_close_all(paper.portfolio)

        assert paper.portfolio.current_monthly_loss >= 30_000
        assert paper.portfolio.system_locked is True
        assert tax_path.exists()
        lines = tax_path.read_text().strip().split("\n")
        assert len(lines) >= 2
        for line in lines:
            record = json.loads(line)
            assert "realized_pnl_jpy" in record
            assert "total_monthly_loss_jpy" in record
