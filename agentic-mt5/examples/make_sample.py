"""Deterministic artificial prices for software validation, not performance evidence."""
from pathlib import Path
import numpy as np
import pandas as pd
rng = np.random.default_rng(42)
n=1500
returns=.00015+.002*np.sin(np.arange(n)/65)+rng.normal(0,.004,n)
close=100*np.exp(np.cumsum(returns))
open_=np.r_[100,close[:-1]]*np.exp(rng.normal(0,.001,n))
spread=rng.uniform(.001,.008,n)
d=pd.DataFrame({'time':1704067200+np.arange(n)*3600,'open':open_,
                'high':np.maximum(open_,close)*(1+spread),
                'low':np.minimum(open_,close)*(1-spread),'close':close})
Path('data').mkdir(exist_ok=True)
d.to_csv('data/SYNTHETIC_H1.csv',index=False)
print('Created synthetic fixture: data/SYNTHETIC_H1.csv')
