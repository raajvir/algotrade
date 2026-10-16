# EMA Crossover Bot (Alpaca + GitHub Actions)

Same rules as the TradingView "EMA Crossover Strategy":

- **Buy** when the 9 EMA crosses above the 21 EMA on the last *completed* daily candle (10% of equity, capped by `MAX_ORDER_USD`)
- **Sell** at a −3% stop loss, a +6% take profit, or when the 9 EMA crosses back below the 21 EMA
- Long only. Runs hourly on GitHub's servers, so your laptop can be off.
- Stop loss and take profit are checked hourly, not tick by tick, so fills can be worse than −3% / +6% in a fast move.

## Setup (about 10 minutes)

1. **Get paper API keys:** Alpaca dashboard (Paper Trading) → Home → *API Keys* → *Generate New Keys*. Copy both keys; the secret is shown only once.
2. **Create a private GitHub repo** and upload all of these files, including the `.github/workflows/bot.yml` folder.
3. **Add the keys as secrets:** repo → Settings → Secrets and variables → Actions → *New repository secret*
   - `ALPACA_API_KEY`
   - `ALPACA_SECRET_KEY`
4. *(Optional)* Add **Variables** on the same page:
   - `SYMBOL`: `BTC/USD` (default; trades 24/7) or a stock/ETF like `SPY`
   - `MAX_ORDER_USD`: default `1000`
   - `DRY_RUN`: `true` to log decisions without placing orders
5. **Test it:** Actions tab → *EMA bot* → *Run workflow*. Open the run to see the decision log.

It then runs every hour automatically. GitHub can pause scheduled workflows in repos with no activity for 60 days, so re-enable it from the Actions tab if that happens.

## Going live later

Only after a few months of paper results you're happy with:

1. Generate **live** API keys and replace the two secrets.
2. Set the variables `ALPACA_PAPER` = `false` **and** `LIVE_TRADING_CONFIRMED` = `yes` (both are required; this is a safety latch).
3. Keep `MAX_ORDER_USD` small.

## Run the tests locally

```
pip install -r requirements.txt pytest
pytest -q
```
