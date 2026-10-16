"""Pure EMA-crossover logic (no API calls) so it can be unit-tested and backtested."""
from dataclasses import dataclass

import pandas as pd


@dataclass
class Params:
    fast_len: int = 9
    slow_len: int = 21
    stop_loss_pct: float = 0.03   # 3%
    take_profit_pct: float = 0.06  # 6%
    position_pct: float = 0.10     # 10% of equity per trade


def add_emas(closes: pd.Series, p: Params) -> pd.DataFrame:
    df = pd.DataFrame({"close": closes})
    df["fast"] = df["close"].ewm(span=p.fast_len, adjust=False).mean()
    df["slow"] = df["close"].ewm(span=p.slow_len, adjust=False).mean()
    return df


def last_cross(closes: pd.Series, p: Params) -> str | None:
    """Cross on the most recent COMPLETED bar: 'up', 'down' or None."""
    if len(closes) < p.slow_len + 2:
        return None
    df = add_emas(closes, p)
    prev, cur = df.iloc[-2], df.iloc[-1]
    if prev.fast <= prev.slow and cur.fast > cur.slow:
        return "up"
    if prev.fast >= prev.slow and cur.fast < cur.slow:
        return "down"
    return None


def decide(cross: str | None, has_position: bool, entry_price: float | None,
           current_price: float, already_acted_on_bar: bool, p: Params) -> tuple[str, str]:
    """Return (action, reason). action is 'buy', 'sell' or 'hold'."""
    if has_position:
        if current_price <= entry_price * (1 - p.stop_loss_pct):
            return "sell", f"stop loss hit ({current_price:.2f} <= {entry_price * (1 - p.stop_loss_pct):.2f})"
        if current_price >= entry_price * (1 + p.take_profit_pct):
            return "sell", f"take profit hit ({current_price:.2f} >= {entry_price * (1 + p.take_profit_pct):.2f})"
        if cross == "down":
            return "sell", "fast EMA crossed below slow EMA"
        return "hold", "in position, no exit signal"
    if cross == "up" and not already_acted_on_bar:
        return "buy", "fast EMA crossed above slow EMA"
    if cross == "up":
        return "hold", "crossover already traded on this bar"
    return "hold", "flat, no entry signal"
