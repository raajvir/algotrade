"""EMA crossover bot for Alpaca. Run once per schedule tick (e.g. hourly via GitHub Actions).

Environment variables
---------------------
ALPACA_API_KEY, ALPACA_SECRET_KEY   required (paper keys while testing)
SYMBOL            default "BTC/USD"  (crypto uses a slash; stocks/ETFs e.g. "SPY")
ALPACA_PAPER      default "true"     set "false" only when going live
LIVE_TRADING_CONFIRMED  must be "yes" in addition to ALPACA_PAPER=false (safety latch)
MAX_ORDER_USD     default "1000"     hard cap on any single buy
DRY_RUN           default "false"    "true" = log decisions, place no orders
FAST_LEN, SLOW_LEN, STOP_LOSS_PCT, TAKE_PROFIT_PCT, POSITION_PCT  optional overrides
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest, StockBarsRequest, CryptoLatestTradeRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest

from strategy import Params, last_cross, decide


def env(name, default=None):
    v = os.getenv(name)
    return v if v not in (None, "") else default


def log(msg):
    print(msg, flush=True)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write(msg + "\n\n")


def main():
    key, secret = env("ALPACA_API_KEY"), env("ALPACA_SECRET_KEY")
    if not key or not secret:
        sys.exit("Missing ALPACA_API_KEY / ALPACA_SECRET_KEY")

    paper = env("ALPACA_PAPER", "true").lower() != "false"
    if not paper and env("LIVE_TRADING_CONFIRMED", "").lower() != "yes":
        sys.exit("Refusing to trade live: set LIVE_TRADING_CONFIRMED=yes as well as ALPACA_PAPER=false")

    symbol = env("SYMBOL", "BTC/USD")
    is_crypto = "/" in symbol
    pos_symbol = symbol.replace("/", "")
    dry_run = env("DRY_RUN", "false").lower() == "true"
    max_order = float(env("MAX_ORDER_USD", "1000"))
    p = Params(
        fast_len=int(env("FAST_LEN", 9)),
        slow_len=int(env("SLOW_LEN", 21)),
        stop_loss_pct=float(env("STOP_LOSS_PCT", 0.03)),
        take_profit_pct=float(env("TAKE_PROFIT_PCT", 0.06)),
        position_pct=float(env("POSITION_PCT", 0.10)),
    )

    trading = TradingClient(key, secret, paper=paper)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=max(120, p.slow_len * 5))

    # --- Daily bars, completed bars only ---
    if is_crypto:
        data = CryptoHistoricalDataClient(key, secret)
        bars = data.get_crypto_bars(CryptoBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=start)).df
        price = float(data.get_crypto_latest_trade(CryptoLatestTradeRequest(symbol_or_symbols=symbol))[symbol].price)
    else:
        data = StockHistoricalDataClient(key, secret)
        bars = data.get_stock_bars(StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day,
                                                    start=start, feed=DataFeed.IEX)).df
        price = float(data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX))[symbol].price)

    bars = bars.reset_index().set_index("timestamp").sort_index()
    if is_crypto:
        # crypto daily bars start at 00:00 UTC; today's bar is still forming
        bars = bars[bars.index < pd.Timestamp(now.date(), tz="UTC")]
    elif trading.get_clock().is_open:
        bars = bars.iloc[:-1]  # today's stock bar is still forming
    if bars.empty:
        sys.exit("No completed bars returned")

    closes = bars["close"]
    last_bar_time = closes.index[-1].to_pydatetime()
    cross = last_cross(closes, p)

    # --- Current position ---
    try:
        pos = trading.get_open_position(pos_symbol)
        has_pos, entry = float(pos.qty) > 0, float(pos.avg_entry_price)
    except Exception:
        has_pos, entry = False, None

    # --- Already bought on this signal bar? (prevents re-entry every hour) ---
    orders = trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, symbols=[symbol, pos_symbol],
                                                 after=last_bar_time, limit=50))
    acted = any(o.side == OrderSide.BUY for o in orders)

    action, reason = decide(cross, has_pos, entry, price, acted, p)
    mode = "PAPER" if paper else "LIVE"
    log(f"[{mode}] {now:%Y-%m-%d %H:%M} UTC | {symbol} price={price:.2f} | last bar {last_bar_time:%Y-%m-%d} "
        f"cross={cross} | position={'yes @ %.2f' % entry if has_pos else 'none'} -> {action.upper()}: {reason}")

    if dry_run or action == "hold":
        if dry_run and action != "hold":
            log("DRY_RUN=true, no order sent.")
        return

    if action == "buy":
        equity = float(trading.get_account().equity)
        notional = round(min(equity * p.position_pct, max_order), 2)
        order = trading.submit_order(MarketOrderRequest(
            symbol=symbol, notional=notional, side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC if is_crypto else TimeInForce.DAY))
        log(f"Submitted BUY ${notional} of {symbol} (order {order.id})")
    elif action == "sell":
        order = trading.close_position(pos_symbol)
        log(f"Submitted SELL (close position) {pos_symbol} (order {order.id})")


if __name__ == "__main__":
    main()
