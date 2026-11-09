"""Build a self-contained synthetic public demo; never use real artifacts."""
import json
from pathlib import Path

import pandas as pd

from retainiq.data import ingest
from retainiq.demo import generate
from retainiq.features import snapshot
from retainiq.model import train


def ensure_public_demo(output):
    output = Path(output)
    report_path = output/"report.json"
    if report_path.is_file():
        report = json.loads(report_path.read_text())
        if report.get("provenance") != "synthetic":
            raise ValueError("Public demo refuses non-synthetic artifacts")
        if (output/"scored.parquet").is_file():
            scored = pd.read_parquet(output/"scored.parquet")
            if not scored.msno.str.startswith("synthetic-").all():
                raise ValueError("Public demo refuses non-synthetic subscriber IDs")
            return output
    output.mkdir(parents=True, exist_ok=True)
    generate(output/"raw", n=150, seed=42)
    ingest(output/"raw", output/"demo.duckdb", provenance="synthetic")
    frame = pd.concat([snapshot(output/"demo.duckdb", d, "2016-09-30")
        for d in ["2016-01-01", "2016-04-01", "2016-07-01"]], ignore_index=True)
    train(frame, output)
    return output
