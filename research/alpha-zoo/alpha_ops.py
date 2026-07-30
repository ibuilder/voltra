"""WorldQuant Alpha101 operator toolkit (Kakushadze 2015), panel form.

Every function operates on a panel: a pandas DataFrame indexed by timestamp with
one column per asset (our 4-coin basket). Cross-sectional ops act across columns
(axis=1); time-series ops act down the index within a rolling window.

This is the shared vocabulary the formulaic alphas are written in. Kept separate
so the alpha definitions in alpha_test.py read like the paper.

Reference: Zura Kakushadze, "101 Formulaic Alphas" (2015), arXiv:1601.00991.
Educational reference material — no edge is claimed. We TEST them, we don't trust
them (see docs/alpha-zoo-report.md).
"""

import numpy as np
import pandas as pd


def rank(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional rank across assets, normalized to (0, 1].

    NOTE: with a 4-coin basket the breadth is 4 — cross-sectional rank has very
    little resolution here vs. the thousands of stocks these alphas assume.
    """
    return df.rank(axis=1, pct=True)


def delay(df: pd.DataFrame, d: int) -> pd.DataFrame:
    return df.shift(d)


def delta(df: pd.DataFrame, d: int) -> pd.DataFrame:
    return df - df.shift(d)


def ts_sum(df: pd.DataFrame, d: int) -> pd.DataFrame:
    return df.rolling(d).sum()


def sma(df: pd.DataFrame, d: int) -> pd.DataFrame:
    return df.rolling(d).mean()


def stddev(df: pd.DataFrame, d: int) -> pd.DataFrame:
    return df.rolling(d).std()


def ts_min(df: pd.DataFrame, d: int) -> pd.DataFrame:
    return df.rolling(d).min()


def ts_max(df: pd.DataFrame, d: int) -> pd.DataFrame:
    return df.rolling(d).max()


def ts_argmax(df: pd.DataFrame, d: int) -> pd.DataFrame:
    return df.rolling(d).apply(np.argmax, raw=True) + 1


def ts_argmin(df: pd.DataFrame, d: int) -> pd.DataFrame:
    return df.rolling(d).apply(np.argmin, raw=True) + 1


def ts_rank(df: pd.DataFrame, d: int) -> pd.DataFrame:
    """Time-series rank: the percentile rank of the last value in a window."""
    def _r(x):
        return pd.Series(x).rank(pct=True).iloc[-1]
    return df.rolling(d).apply(_r, raw=False)


def correlation(a: pd.DataFrame, b: pd.DataFrame, d: int) -> pd.DataFrame:
    return a.rolling(d).corr(b)


def covariance(a: pd.DataFrame, b: pd.DataFrame, d: int) -> pd.DataFrame:
    return a.rolling(d).cov(b)


def scale(df: pd.DataFrame, a: float = 1.0) -> pd.DataFrame:
    """Rescale each row so sum(|x|) == a."""
    return df.mul(a).div(df.abs().sum(axis=1), axis=0)


def decay_linear(df: pd.DataFrame, d: int) -> pd.DataFrame:
    """Linearly-decaying weighted moving average over the last d rows."""
    w = np.arange(1, d + 1, dtype=float)
    w /= w.sum()
    return df.rolling(d).apply(lambda x: np.dot(x, w), raw=True)


def signedpower(df: pd.DataFrame, a: float) -> pd.DataFrame:
    return np.sign(df) * (df.abs() ** a)


def ts_product(df: pd.DataFrame, d: int) -> pd.DataFrame:
    return df.rolling(d).apply(np.prod, raw=True)
