from dataclasses import dataclass, asdict
import math
from .core import Strategy, signals


@dataclass(frozen=True)
class Costs:
    initial_cash: float = 10000
    fee_bps: float = 2
    slippage_bps: float = 2
    risk_fraction: float = .01
    stop_atr: float = 2
    take_atr: float = 4

    def __post_init__(self):
        if not all(math.isfinite(v) for v in asdict(self).values()):
            raise ValueError('Costs must be finite')
        if self.initial_cash <= 0 or not 0 < self.risk_fraction <= .1:
            raise ValueError('Invalid cash/risk')
        if not 0 <= self.fee_bps <= 100 or not 0 <= self.slippage_bps <= 100:
            raise ValueError('Invalid costs')
        if self.stop_atr <= 0 or self.take_atr <= 0:
            raise ValueError('ATR distances must be positive')


def backtest(frame, config=Strategy(), costs=Costs()):
    d = signals(frame, config)
    if len(d) < config.slow+2:
        raise ValueError('Insufficient backtest bars')
    cash, qty, stop, take = costs.initial_cash, 0, 0, 0
    slip, fee = costs.slippage_bps/10000, costs.fee_bps/10000
    trades, curve = [], []
    entry = {}
    def close(price, time, reason):
        nonlocal cash, qty
        fill = price*(1-slip)
        proceeds = qty*fill*(1-fee)
        cash += proceeds
        trades.append({**entry, 'exit_time': int(time), 'exit_price': fill, 'reason': reason,
                       'pnl': proceeds-entry['outlay']})
        qty = 0
    for i in range(1, len(d)):
        bar, prev = d.iloc[i], d.iloc[i-1]
        exited = False
        # Existing gaps are executed at the open, including adverse stop gaps.
        if qty and (bar.open <= stop or bar.open >= take):
            close(bar.open, bar.time, 'gap_stop' if bar.open <= stop else 'gap_take')
            exited = True
        if qty and prev.target == 0:
            close(bar.open, bar.time, 'signal')
            exited = True
        if not qty and not exited and prev.target == 1 and prev.atr > 0:
            fill = bar.open*(1+slip)
            distance = costs.stop_atr*prev.atr
            stop, take = fill-distance, fill+costs.take_atr*prev.atr
            if stop > 0:
                qty = min(cash*costs.risk_fraction/distance, cash/(fill*(1+fee)))
                outlay = qty*fill*(1+fee)
                cash -= outlay
                entry = {'entry_time': int(bar.time), 'entry_price': fill, 'units': qty, 'outlay': outlay}
        # If OHLC touches both, assume stop first (conservative ambiguity handling).
        if qty and bar.low <= stop:
            close(stop, bar.time, 'stop')
        elif qty and bar.high >= take:
            close(take, bar.time, 'take')
        if qty and i == len(d)-1:
            close(bar.close, bar.time, 'end_of_data')
        curve.append({'time': int(bar.time), 'equity': float(cash+qty*bar.close)})
    peak, drawdown = costs.initial_cash, 0
    for p in curve:
        peak = max(peak, p['equity'])
        drawdown = max(drawdown, (peak-p['equity'])/peak)
    wins = sum(t['pnl'] > 0 for t in trades)
    return {'metrics': {'return_pct': (cash/costs.initial_cash-1)*100,
                        'max_drawdown_pct': drawdown*100, 'trades': len(trades),
                        'win_rate_pct': 100*wins/len(trades) if trades else 0,
                        'final_equity': cash}, 'costs': asdict(costs), 'strategy': asdict(config),
            'model': 'Long only, fractional cash equity units, no leverage; next-open fills; fixed ATR brackets; stop-first OHLC; no corporate actions.',
            'trades': trades, 'equity': curve}
