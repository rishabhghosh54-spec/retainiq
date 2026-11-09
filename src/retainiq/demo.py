"""Deterministic synthetic plumbing fixture, never an estimate of KKBOX performance."""
from pathlib import Path

import numpy as np
import pandas as pd


def generate(raw, n=600, seed=42):
    raw = Path(raw)
    raw.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    transactions, logs = [], []
    for cutoff in pd.to_datetime(["2016-01-01", "2016-04-01", "2016-07-01"]):
        for i in range(n):
            user = f"synthetic-{i:05d}"
            engaged = rng.random()
            expiry = cutoff + pd.Timedelta(days=int(rng.integers(1, 28)))
            fmt = lambda d: d.strftime("%Y%m%d")
            auto = int(rng.random() < engaged)
            transactions.append([user, fmt(cutoff-pd.Timedelta(days=20)), fmt(expiry), 0, auto, 149, 30])
            renew = rng.random() < .2 + .7*engaged
            if renew:
                transactions.append([user, fmt(expiry+pd.Timedelta(days=int(rng.integers(0, 25)))), fmt(expiry+pd.Timedelta(days=60)), 0, auto, 149, 30])
            for day in range(1, 31):
                if rng.random() < engaged:
                    logs.append([user, fmt(cutoff-pd.Timedelta(days=day)), round(float(rng.uniform(30, 3600)), 2), int(rng.integers(1, 40))])
    tx = pd.DataFrame(transactions, columns=["msno", "transaction_date", "membership_expire_date", "is_cancel", "is_auto_renew", "actual_amount_paid", "payment_plan_days"])
    tx["plan_list_price"] = 149
    tx["payment_method_id"] = 41
    tx.to_csv(raw/"transactions.csv", index=False)
    pd.DataFrame(logs, columns=["msno", "date", "total_secs", "num_unq"]).to_csv(raw/"user_logs.csv", index=False)
