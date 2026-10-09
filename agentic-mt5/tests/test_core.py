import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from ta_mcp.core import indicators, signals, validate_bars, Strategy, wilder
from ta_mcp.backtest import backtest, Costs
from ta_mcp.replay import export_replay
from ta_mcp.data import dataset


def bars(n=100):
    c=np.linspace(100,120,n)
    return pd.DataFrame({'time':1700000000+np.arange(n)*3600,'open':c,'high':c+1,'low':c-1,'close':c})

class CoreTests(unittest.TestCase):
    def test_rsi_edges(self):
        self.assertEqual(indicators(bars()).rsi.iloc[-1],100)
        d=bars(); d[['open','close']]=100; d.high=101; d.low=99
        self.assertEqual(indicators(d).rsi.iloc[-1],50)
        d=bars(); d[['open','close']]=np.linspace(120,100,100)[:,None]*np.ones((1,2)); d.high=d.close+1; d.low=d.close-1
        self.assertEqual(indicators(d).rsi.iloc[-1],0)
    def test_wilder_seed(self):
        np.testing.assert_allclose(wilder([1,2,3,4],3)[2:],[2,8/3])
    def test_bollinger_population_std(self):
        d=indicators(bars())
        self.assertAlmostEqual(d.bb_upper.iloc[-1],d.close.tail(20).mean()+2*d.close.tail(20).std(ddof=0))
    def test_prefix_invariance(self):
        d=bars(200); d.close+=np.sin(np.arange(200)); d.high=d[['open','close']].max(axis=1)+1; d.low=d[['open','close']].min(axis=1)-1
        pd.testing.assert_frame_equal(signals(d).iloc[:100],signals(d.iloc[:100]))
    def test_validation(self):
        d=bars(); d.loc[3,'time']=d.loc[2,'time']
        with self.assertRaises(ValueError): validate_bars(d)
        with self.assertRaises(ValueError): Strategy(fast=100,slow=20)
        with self.assertRaises(ValueError): Costs(risk_fraction=-1)
        with self.assertRaises(ValueError): dataset('../secrets.csv')
    def test_replay_shift(self):
        d=bars(); s=signals(d)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'replay.csv'; export_replay(d,p,'TEST')
            out=pd.read_csv(p)
            self.assertEqual(out.time.iloc[0],d.time.iloc[50])
            self.assertEqual(out.target.iloc[0],s.target.iloc[49])
            self.assertAlmostEqual(out.atr.iloc[0],s.atr.iloc[49])
    def test_stop_first_and_next_open(self):
        d=bars(55); d['target']=0; d['atr']=1.
        d.loc[50,'target']=1
        d.loc[51,['open','high','low','close']]=[100,110,90,100]
        with patch('ta_mcp.backtest.signals',return_value=d):
            r=backtest(d,costs=Costs(fee_bps=0,slippage_bps=0))
        t=r['trades'][0]
        self.assertEqual(t['entry_time'],d.time.iloc[51])
        self.assertEqual(t['exit_price'],98)
        self.assertEqual(t['reason'],'stop')
        self.assertAlmostEqual(t['pnl'],-100)
    def test_gap_stop(self):
        d=bars(55); d['target']=0; d['atr']=1.
        d.loc[50:51,'target']=1
        d.loc[51,['open','high','low','close']]=[100,101,99,100]
        d.loc[52,['open','high','low','close']]=[90,91,89,90]
        with patch('ta_mcp.backtest.signals',return_value=d):
            r=backtest(d,costs=Costs(fee_bps=0,slippage_bps=0))
        self.assertEqual(r['trades'][0]['exit_price'],90)
        self.assertEqual(r['trades'][0]['reason'],'gap_stop')
    def test_accounting(self):
        r=backtest(bars(200))
        self.assertAlmostEqual(r['metrics']['final_equity'],10000+sum(t['pnl'] for t in r['trades']))
        self.assertGreaterEqual(r['metrics']['max_drawdown_pct'],0)

if __name__=='__main__': unittest.main()
