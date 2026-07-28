from __future__ import annotations
import pytest
from algo_trader.src.domain.models import Order, OrderSide, OrderType, PortfolioState, Position
from algo_trader.src.risk.risk_manager import AlertLevel, RiskManager


def _make_order(
    amount: float = 1.0, side: OrderSide = OrderSide.BUY, order_type: OrderType = OrderType.MARKET
) -> Order:
    return Order(
        id="order-1",
        symbol="ETH/JPY",
        side=side,
        order_type=order_type,
        amount=amount,
    )


def _make_portfolio(
    loss: float = 0.0, position: Position | None = None, cash: float = 100_000.0
) -> PortfolioState:
    p = PortfolioState(cash_jpy=cash, current_monthly_loss=loss)
    if position is not None:
        p.positions["ETH/JPY"] = position
    return p


class TestRiskManager:
    def test_order_rejected_when_hard_cap_reached(self):
        manager = RiskManager(
            base_risk_per_trade_jpy=1_000,
            stop_loss_distance_jpy=1_000,
        )
        portfolio = _make_portfolio(loss=30_000)
        order = _make_order(0.5)
        result = manager.validate_order(order, portfolio)

        assert result.approved is False
        assert result.alert_level == AlertLevel.EMERGENCY
        assert result.requires_emergency_close is True
        assert result.system_lock is True
        assert portfolio.system_locked is True

    def test_circuit_breaker_warning_at_15k_halves_size(self):
        manager = RiskManager(
            base_risk_per_trade_jpy=1_000,
            stop_loss_distance_jpy=1_000,
            warning_threshold_jpy=15_000,
            critical_threshold_jpy=25_000,
        )
        portfolio = _make_portfolio(loss=15_000)
        order = _make_order(1.0)
        result = manager.validate_order(order, portfolio)

        assert result.approved is False
        assert result.alert_level == AlertLevel.WARNING
        assert result.allowed_quantity == pytest.approx(0.5)

    def test_circuit_breaker_critical_at_25k_blocks_new_entries(self):
        manager = RiskManager(
            base_risk_per_trade_jpy=1_000,
            stop_loss_distance_jpy=1_000,
            warning_threshold_jpy=15_000,
            critical_threshold_jpy=25_000,
        )
        portfolio = _make_portfolio(loss=25_000)
        order = _make_order(0.3)
        result = manager.validate_order(order, portfolio)

        assert result.approved is False
        assert result.alert_level == AlertLevel.CRITICAL
        assert "only exit" in result.message.lower()

    def test_circuit_breaker_critical_allows_exits(self):
        manager = RiskManager(
            base_risk_per_trade_jpy=1_000,
            stop_loss_distance_jpy=1_000,
            warning_threshold_jpy=15_000,
            critical_threshold_jpy=25_000,
        )
        position = Position(
            symbol="ETH/JPY",
            side=OrderSide.BUY,
            amount=1.0,
            average_entry_price=30_000.0,
        )
        portfolio = _make_portfolio(loss=25_000, position=position)
        order = _make_order(1.0, OrderSide.SELL)
        result = manager.validate_order(order, portfolio)

        assert result.approved is True
        assert result.alert_level == AlertLevel.CRITICAL
        assert result.allowed_quantity == pytest.approx(1.0)

    def test_dynamic_sizing_near_loss_limit(self):
        manager = RiskManager(
            base_risk_per_trade_jpy=1_000,
            stop_loss_distance_jpy=1_000,
            monthly_loss_cap_jpy=30_000,
            warning_threshold_jpy=15_000,
            critical_threshold_jpy=29_500,
        )
        # Remaining budget 600 JPY, base risk 1000, warning threshold active -> 0.3 units.
        portfolio = _make_portfolio(loss=29_400)
        order = _make_order(0.5)
        result = manager.validate_order(order, portfolio)

        assert result.approved is False
        assert result.allowed_quantity == pytest.approx(0.3)
        assert result.alert_level == AlertLevel.WARNING

    def test_max_position_size_helper(self):
        manager = RiskManager(
            base_risk_per_trade_jpy=1_000,
            stop_loss_distance_jpy=1_000,
        )
        assert manager.max_position_size(_make_portfolio(loss=0)) == pytest.approx(1.0)
        assert manager.max_position_size(_make_portfolio(loss=15_000)) == pytest.approx(0.5)
        assert manager.max_position_size(_make_portfolio(loss=25_000)) == pytest.approx(0.0)

    def test_zero_size_order_rejected(self):
        manager = RiskManager(
            base_risk_per_trade_jpy=1_000,
            stop_loss_distance_jpy=1_000,
        )
        portfolio = _make_portfolio(loss=29_900)
        order = _make_order(0.1)
        result = manager.validate_order(order, portfolio)
        assert result.approved is False
        assert result.allowed_quantity == pytest.approx(0.0)

    def test_emergency_close_orders_generated(self):
        manager = RiskManager(
            base_risk_per_trade_jpy=1_000,
            stop_loss_distance_jpy=1_000,
        )
        portfolio = _make_portfolio(
            position=Position(
                symbol="ETH/JPY",
                side=OrderSide.BUY,
                amount=2.0,
                average_entry_price=30_000.0,
            )
        )
        orders = manager.generate_emergency_close_orders(portfolio)
        assert len(orders) == 1
        assert orders[0].side == OrderSide.SELL
        assert orders[0].amount == pytest.approx(2.0)
