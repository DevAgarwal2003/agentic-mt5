import os
from pathlib import Path
from contextlib import contextmanager
import pandas as pd
from .core import validate_bars

TIMEFRAMES = {'M5': 300, 'M15': 900, 'M30': 1800, 'H1': 3600, 'H4': 14400, 'D1': 86400}

@contextmanager
def terminal():
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise RuntimeError('MT5 requires Windows and pip install -e ".[mt5]"') from exc
    path = os.getenv('MT5_PATH')
    ok = mt5.initialize(path) if path else mt5.initialize()
    if not ok:
        raise RuntimeError(f'MT5 initialize failed: {mt5.last_error()}')
    try:
        yield mt5
    finally:
        mt5.shutdown()


def fetch(symbol, timeframe='H1', count=2000):
    if timeframe not in TIMEFRAMES or not 100 <= count <= 100000:
        raise ValueError('Unsupported timeframe or count outside [100,100000]')
    with terminal() as mt5:
        if not mt5.symbol_select(symbol, True):
            raise ValueError(f'Symbol unavailable: {symbol}; use broker symbol name')
        # Position 0 is forming; omit it from all analytical inputs.
        bars = mt5.copy_rates_from_pos(symbol, getattr(mt5, 'TIMEFRAME_'+timeframe), 1, count)
        if bars is None or len(bars) < 100:
            raise RuntimeError(f'Missing history: {mt5.last_error()}')
        return validate_bars(pd.DataFrame(bars))


def load_csv(path):
    return validate_bars(pd.read_csv(path))


def dataset(name):
    root = Path(os.getenv('TA_DATA_DIR', 'data')).resolve()
    path = (root/name).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != '.csv':
        raise ValueError('Dataset must be a CSV inside TA_DATA_DIR')
    return load_csv(path)


def list_datasets():
    root = Path(os.getenv('TA_DATA_DIR', 'data'))
    return sorted(p.name for p in root.glob('*.csv'))
