"""Birth-feature placebo protocol.
For each person, preserve birth year (and optionally geography) while randomizing month/day/time.
The full training pipeline must be rerun on many shuffled copies. A BaZi model only earns credit
if real birthdays beat the placebo distribution out-of-sample.
"""
import numpy as np, pandas as pd

def shuffle_birthdays(df: pd.DataFrame, seed=0):
    rng=np.random.default_rng(seed)
    x=df.copy()
    for _, idx in x.groupby(["birth_year","birth_country"], dropna=False).groups.items():
        idx=list(idx)
        vals=x.loc[idx,["birth_month","birth_day"]].to_numpy(copy=True)
        rng.shuffle(vals)
        x.loc[idx,["birth_month","birth_day"]]=vals
    return x
