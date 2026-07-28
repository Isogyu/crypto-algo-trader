# Algorithmic Crypto Trader (JPY)

A production-grade, risk-first algorithmic trading system for JPY-denominated crypto markets.  The primary objective is **capital preservation** under a hard monthly loss cap of **30,000 JPY**.

## Core design

- Clean Architecture layout under `algo_trader/`
- Pydantic domain models (`Order`, `Trade`, `Position`, `PortfolioState`)
- Pre-trade risk interceptor with dynamic sizing and multi-stage circuit breakers
- CCXT execution adapter with exponential backoff and pre-order validation
- Paper trading simulator with realistic PnL, fees, slippage, and tax logging
- Reconciliation module that locks the system on state mismatch
- JSONL tax log export for Japanese crypto tax reporting

## Quick start

```bash
# Install dependencies
pip install -e ".[test]"

# Run unit tests
pytest

# Run the paper trading simulation
python -m algo_trader.src.main --paper
```

The paper simulation attempts 50 ticks of synthetic trades against a falling ETH/JPY price, demonstrates risk interception, writes entries to `algo_trader/data/tax_trade_log.jsonl`, and performs an emergency close when the hard loss cap is reached.

## Configuration

Edit `algo_trader/config/config.yaml` to adjust risk thresholds, exchange settings, and strategy parameters.  Sensitive values (`api_key`, `secret`) should be provided through environment variables or a `.env` file — never committed.

## Docker

```bash
docker compose up --build
```

## Risk model

- Allowable risk per trade = `min(base_risk_per_trade_jpy, monthly_loss_cap_jpy - current_loss)`
- Max position size = Allowable risk / stop_loss_distance_jpy
- 15,000 JPY warning: position size halved
- 25,000 JPY critical: only exit / stop-loss orders allowed
- 30,000 JPY hard cap: system locks and emergency-closes all positions

## License

Private / proprietary — for educational and development use only.
