import csv
from pathlib import Path
from .core import Strategy, signals
from .data import TIMEFRAMES


def export_replay(frame, path, symbol, timeframe='H1', config=Strategy()):
    if timeframe not in TIMEFRAMES or not symbol or any(c in symbol for c in ',\n\r'):
        raise ValueError('Invalid symbol/timeframe')
    d = signals(frame, config)
    if len(d) < config.slow+2:
        raise ValueError('Insufficient bars')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='ascii') as out:
        writer = csv.writer(out)
        writer.writerow(['time','target','atr','symbol','period_seconds'])
        for i in range(max(config.slow,config.bb_period,config.rsi_period+1,config.atr_period), len(d)):
            # MT5 opening epoch is preserved; use actual next bar, respecting sessions.
            prev = d.iloc[i-1]
            writer.writerow([int(d.iloc[i].time), int(prev.target), format(prev.atr,'.12g'), symbol, TIMEFRAMES[timeframe]])
    return str(path)
