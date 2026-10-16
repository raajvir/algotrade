import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pandas as pd
from strategy import Params, last_cross, decide

P = Params()


def series(vals):
    return pd.Series(vals, dtype=float)


def test_cross_up_detected():
    s = series([100 - i * 0.5 for i in range(40)] + [120])
    assert last_cross(s, P) == "up"


def test_cross_down_detected():
    s = series([100 + i * 0.5 for i in range(40)] + [80])
    assert last_cross(s, P) == "down"


def test_no_cross_in_steady_trend():
    assert last_cross(series([100 + i for i in range(40)]), P) is None


def test_too_little_data():
    assert last_cross(series([1, 2, 3]), P) is None


def test_buy_on_cross_up_when_flat():
    assert decide("up", False, None, 100, False, P)[0] == "buy"


def test_no_double_buy_same_bar():
    assert decide("up", False, None, 100, True, P)[0] == "hold"


def test_stop_loss():
    assert decide(None, True, 100, 96.9, False, P)[0] == "sell"


def test_take_profit():
    assert decide(None, True, 100, 106.1, False, P)[0] == "sell"


def test_exit_on_cross_down():
    assert decide("down", True, 100, 101, False, P)[0] == "sell"


def test_hold_in_position():
    assert decide(None, True, 100, 101, False, P)[0] == "hold"
