from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Strategy:
    fast: int = 20
    slow: int = 50
    rsi_period: int = 14
    atr_period: int = 10
    supertrend_multiplier: float = 3.0
    bb_period: int = 20
    bb_std: float = 2.0
    rsi_min: float = 50.0
    rsi_max: float = 70.0

    def __post_init__(self):
        periods = [self.fast, self.slow, self.rsi_period, self.atr_period, self.bb_period]
        if any(type(x) is not int or x < 2 or x > 500 for x in periods):
            raise ValueError('Periods must be integers in [2, 500]')
        if self.fast >= self.slow:
            raise ValueError('fast must be less than slow')
        if not 0 <= self.rsi_min < self.rsi_max <= 100:
            raise ValueError('Invalid RSI thresholds')
        if not 0 < self.supertrend_multiplier <= 20 or not 0 < self.bb_std <= 10:
            raise ValueError('Invalid indicator multipliers')


def validate_bars(frame):
    d = frame.copy().reset_index(drop=True)
    required = ['time', 'open', 'high', 'low', 'close']
    if not set(required).issubset(d.columns):
        raise ValueError('CSV requires time (Unix seconds), open, high, low, close')
    for c in required:
        d[c] = pd.to_numeric(d[c], errors='raise')
    if not np.isfinite(d[required].to_numpy()).all():
        raise ValueError('Missing or nonfinite OHLC/time')
    if (d.time % 1 != 0).any() or (d.time <= 0).any():
        raise ValueError('time must be positive integer Unix seconds')
    d['time'] = d.time.astype('int64')
    if not d.time.is_monotonic_increasing or d.time.duplicated().any():
        raise ValueError('Bars must have strictly increasing timestamps')
    if (d[['open','high','low','close']] <= 0).any().any():
        raise ValueError('Prices must be positive')
    if (d.high < d[['open','close','low']].max(axis=1)).any() or (d.low > d[['open','close','high']].min(axis=1)).any():
        raise ValueError('Invalid OHLC ranges')
    return d


def wilder(values, period):
    """Wilder smoothing with an SMA seed; leading NaNs are allowed."""
    a = np.asarray(values, dtype=float)
    out = np.full(len(a), np.nan)
    valid = np.flatnonzero(np.isfinite(a))
    if not len(valid):
        return out
    start = valid[0]
    seed = start + period - 1
    if seed < len(a):
        out[seed] = a[start:seed+1].mean()
        for i in range(seed+1, len(a)):
            out[i] = (out[i-1]*(period-1)+a[i])/period
    return out


def indicators(frame, config=Strategy()):
    d = validate_bars(frame)
    c = d.close
    d['sma_fast'] = c.rolling(config.fast).mean()
    d['sma_slow'] = c.rolling(config.slow).mean()
    d['ema_fast'] = c.ewm(span=config.fast, adjust=False, min_periods=config.fast).mean()
    delta = c.diff()
    gain = wilder(delta.clip(lower=0), config.rsi_period)
    loss = wilder(-delta.clip(upper=0), config.rsi_period)
    with np.errstate(divide='ignore', invalid='ignore'):
        rsi = 100-100/(1+gain/loss)
    rsi[(gain == 0) & (loss == 0)] = 50
    rsi[(gain > 0) & (loss == 0)] = 100
    d['rsi'] = rsi
    tr = pd.concat([d.high-d.low, (d.high-c.shift()).abs(), (d.low-c.shift()).abs()], axis=1).max(axis=1)
    d['atr'] = wilder(tr, config.atr_period)
    mid = (d.high+d.low)/2
    upper = (mid+config.supertrend_multiplier*d.atr).to_numpy()
    lower = (mid-config.supertrend_multiplier*d.atr).to_numpy()
    direction = np.zeros(len(d), dtype=int)
    st = np.full(len(d), np.nan)
    for i in range(config.atr_period-1, len(d)):
        if i == config.atr_period-1:
            direction[i] = 1
        else:
            if not (upper[i] < upper[i-1] or c.iloc[i-1] > upper[i-1]):
                upper[i] = upper[i-1]
            if not (lower[i] > lower[i-1] or c.iloc[i-1] < lower[i-1]):
                lower[i] = lower[i-1]
            direction[i] = (1 if c.iloc[i] > upper[i] else -1) if direction[i-1] == -1 else (-1 if c.iloc[i] < lower[i] else 1)
        st[i] = lower[i] if direction[i] == 1 else upper[i]
    d['supertrend'] = st
    d['st_direction'] = direction
    d['bb_mid'] = c.rolling(config.bb_period).mean()
    std = c.rolling(config.bb_period).std(ddof=0)
    d['bb_upper'] = d.bb_mid+config.bb_std*std
    d['bb_lower'] = d.bb_mid-config.bb_std*std
    return d


def signals(frame, config=Strategy()):
    """Long/flat trend-following baseline; each target is decided at bar CLOSE."""
    d = indicators(frame, config)
    ready = d[['sma_slow','rsi','atr','supertrend','bb_upper']].notna().all(axis=1)
    entry = ready & (d.st_direction == 1) & (d.sma_fast > d.sma_slow) & d.rsi.between(config.rsi_min, config.rsi_max) & (d.close > d.bb_mid) & (d.close < d.bb_upper)
    exit_ = (d.st_direction == -1) | (d.sma_fast < d.sma_slow) | (d.rsi < 45)
    target, active = [], 0
    for buy, sell in zip(entry, exit_):
        if sell:
            active = 0
        elif buy:
            active = 1
        target.append(active)
    d['target'] = target
    return d


def snapshot(frame, config=Strategy()):
    d = signals(frame, config)
    if len(d) < max(config.slow, config.bb_period, config.rsi_period+1, config.atr_period):
        raise ValueError('Insufficient indicator warmup bars')
    row = d.iloc[-1]
    return {'as_of_bar_open': int(row.time), 'decision_at': 'this bar close; execute no earlier than next bar',
            'target': 'LONG' if row.target else 'FLAT', 'strategy': asdict(config),
            'indicators': {k: float(row[k]) for k in ['close','sma_fast','sma_slow','ema_fast','rsi','atr','supertrend','bb_lower','bb_mid','bb_upper']},
            'conditions': {'uptrend': bool(row.st_direction == 1), 'ma_bullish': bool(row.sma_fast > row.sma_slow),
                           'rsi_entry_zone': bool(config.rsi_min <= row.rsi <= config.rsi_max),
                           'bollinger_entry_zone': bool(row.bb_mid < row.close < row.bb_upper)},
            'note': 'Rule-based long/flat target, not a probability or an LLM prediction.'}
