from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import List

# Add the repository root to sys.path so package imports work standalone.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml
from algo_trader.config.logging_config import configure_logging, get_logger
from algo_trader.src.accounting.tax_logger import TaxLogger
from algo_trader.src.execution.paper_trader import PaperTrader
from algo_trader.src.risk.risk_manager import RiskManager
from algo_trader.src.reconciliation.reconciler import Reconciler
from algo_trader.src.strategy.ma_rsi_strategy import MA_RSI_Strategy
from algo_trader.src.domain.models import Order, OrderSide, OrderType

START_PRICE = 30_000.0
PRICE_DROP = 300.0
NUM_TICKS = 50


def load_config() -> dict:
    config_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_system(config: dict):
    log_cfg = config["logging"]
    configure_logging(level=log_cfg["level"], log_dir=log_cfg["log_dir"])
    logger = get_logger("main")

    tax_path = Path(__file__).resolve().parents[1] / config["tax"]["log_path"]
    tax_logger = TaxLogger(log_path=str(tax_path))

    paper = PaperTrader(
        initial_cash=100_000.0,
        fee_rate=config["exchange"]["fee_rate"],
        tax_logger=tax_logger,
        min_order_size=config["exchange"]["min_order_size"],
    )

    risk = RiskManager(
        base_risk_per_trade_jpy=config["risk"]["base_risk_per_trade_jpy"],
        stop_loss_distance_jpy=config["risk"]["stop_loss_distance_jpy"],
        monthly_loss_cap_jpy=config["risk"]["monthly_loss_cap_jpy"],
        warning_threshold_jpy=config["risk"]["warning_threshold_jpy"],
        critical_threshold_jpy=config["risk"]["critical_threshold_jpy"],
    )

    strat_cfg = config["strategy"]
    strategy = MA_RSI_Strategy(
        symbol=strat_cfg["symbol"],
        ma_fast=strat_cfg["ma_fast"],
        ma_slow=strat_cfg["ma_slow"],
        rsi_period=strat_cfg["rsi_period"],
        overbought=strat_cfg["overbought"],
        oversold=strat_cfg["oversold"],
    )

    reconciler = Reconciler(paper)
    return paper, risk, strategy, reconciler, logger


def run_paper_simulation(paper, risk, strategy, reconciler, logger):
    symbol = strategy.symbol
    prices: List[float] = [START_PRICE]
    paper.set_price(symbol, START_PRICE)
    logger.info("paper_simulation_started", start_price=START_PRICE, ticks=NUM_TICKS)

    for tick in range(NUM_TICKS):
        current_price = prices[-1] - PRICE_DROP
        prices.append(current_price)
        paper.set_price(symbol, current_price)

        reconciler.reconcile(paper.portfolio, symbol)
        if paper.portfolio.system_locked:
            logger.warning("system_locked", reason="reconciliation")
            break

        if paper.portfolio.current_monthly_loss >= risk.cap:
            break

        max_size = risk.max_position_size(paper.portfolio)
        if max_size <= paper._min_order_size:
            logger.info(
                "risk_blocked_new_entry",
                tick=tick,
                current_loss=paper.portfolio.current_monthly_loss,
            )
            continue

        affordable = paper.portfolio.cash_jpy / (current_price * (1.0 + paper.fee_rate))
        amount = min(max_size, affordable)
        if amount < paper._min_order_size:
            logger.info("insufficient_cash", tick=tick, cash=paper.portfolio.cash_jpy)
            continue

        order = strategy.on_tick(paper.portfolio, current_price, prices, amount)
        if order is None:
            order = Order(
                id=f"sim-buy-{tick}",
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                amount=amount,
            )

        result = risk.validate_order(order, paper.portfolio)
        if result.approved:
            paper.place_order(order)
            logger.info(
                "paper_trade_executed",
                tick=tick,
                side=order.side.value,
                amount=order.amount,
                price=current_price,
                loss=paper.portfolio.current_monthly_loss,
            )
        else:
            logger.info(
                "order_rejected",
                tick=tick,
                reason=result.message,
                alert=result.alert_level.value,
            )

        if paper.portfolio.current_monthly_loss >= risk.cap:
            logger.warning(
                "hard_cap_reached_during_trading",
                tick=tick,
                loss=paper.portfolio.current_monthly_loss,
            )
            break

    if paper.portfolio.current_monthly_loss >= risk.cap:
        paper.portfolio.system_locked = True
        logger.critical(
            "emergency_close",
            loss=paper.portfolio.current_monthly_loss,
            message="HARD MONTHLY LOSS CAP BREACHED. LIQUIDATING POSITIONS.",
        )
        paper.cancel_all_orders(symbol)
        paper.market_close_all(paper.portfolio)

    logger.info(
        "simulation_complete",
        final_cash=paper.portfolio.cash_jpy,
        current_monthly_loss=paper.portfolio.current_monthly_loss,
        trades=len(paper.portfolio.trades),
        locked=paper.portfolio.system_locked,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Algorithmic crypto trader with hard monthly loss cap."
    )
    parser.add_argument(
        "--paper", action="store_true", help="Run the paper trading simulation."
    )
    args = parser.parse_args()
    if not args.paper:
        parser.print_help()
        return

    config = load_config()
    paper, risk, strategy, reconciler, logger = build_system(config)
    run_paper_simulation(paper, risk, strategy, reconciler, logger)


if __name__ == "__main__":
    main()
