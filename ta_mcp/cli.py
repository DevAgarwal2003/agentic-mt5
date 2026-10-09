import argparse
import json
from pathlib import Path
from .core import snapshot
from .data import load_csv, fetch
from .backtest import backtest
from .replay import export_replay


def main():
    p = argparse.ArgumentParser(description='MT5 analysis and reproducible simulation')
    sub = p.add_subparsers(dest='command', required=True)
    for name in ['analyze','backtest','replay']:
        s = sub.add_parser(name)
        s.add_argument('--csv', required=True)
        if name != 'analyze':
            s.add_argument('--out', required=True)
        if name == 'replay':
            s.add_argument('--symbol', required=True)
            s.add_argument('--timeframe', default='H1')
    s = sub.add_parser('fetch')
    s.add_argument('--symbol', required=True)
    s.add_argument('--timeframe', default='H1')
    s.add_argument('--count', type=int, default=5000)
    s.add_argument('--out', required=True)
    a = p.parse_args()
    if a.command == 'fetch':
        d = fetch(a.symbol, a.timeframe, a.count)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        d.to_csv(a.out, index=False)
        print(f'Saved {len(d)} closed bars to {a.out}')
        return
    d = load_csv(a.csv)
    if a.command == 'analyze':
        print(json.dumps(snapshot(d), indent=2, allow_nan=False))
    elif a.command == 'replay':
        print(export_replay(d, a.out, a.symbol, a.timeframe))
    else:
        r = backtest(d)
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(r, indent=2, allow_nan=False), encoding='utf-8')
        print(json.dumps(r['metrics'], indent=2))

if __name__ == '__main__':
    main()
