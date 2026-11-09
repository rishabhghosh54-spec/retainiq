"""Chunked ingestion into DuckDB; ambiguous records fail instead of guessing."""
import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd

SCHEMAS = {
    "transactions": {"msno", "transaction_date", "membership_expire_date", "is_cancel", "is_auto_renew", "actual_amount_paid", "payment_plan_days"},
    "user_logs": {"msno", "date", "total_secs", "num_unq"},
}


def normalize(frame, table):
    missing = SCHEMAS[table] - set(frame.columns)
    if missing:
        raise ValueError(f"{table}: missing columns {sorted(missing)}")
    optional = {"payment_method_id", "plan_list_price"} & set(frame) if table == "transactions" else set()
    frame = frame[sorted(SCHEMAS[table] | optional)].copy()
    if frame.isna().any().any() or frame.msno.astype(str).str.strip().eq("").any():
        raise ValueError(f"{table}: null or empty required values")
    for col in ["transaction_date", "membership_expire_date"] if table == "transactions" else ["date"]:
        frame[col] = pd.to_datetime(frame[col].astype(str), format="%Y%m%d", errors="raise")
    for col in set(frame) - {"msno", "transaction_date", "membership_expire_date", "date"}:
        frame[col] = pd.to_numeric(frame[col], errors="raise")
        if not frame[col].map(lambda v: float('-inf') < v < float('inf')).all():
            raise ValueError(f"{col}: nonfinite value")
        if (frame[col] < 0).any():
            raise ValueError(f"{col}: negative value; investigate source instead of clipping")
    if table == "user_logs" and (frame.total_secs >= 1e12).any():
        raise ValueError("total_secs: overflow-scale positive value; investigate or explicitly quarantine")
    if table == "transactions":
        for col in {"payment_method_id", "plan_list_price", "payment_plan_days"} & set(frame):
            if (frame[col] % 1 != 0).any():
                raise ValueError(f"{col}: expected integer for reference label ordering")
        for col in ["is_cancel", "is_auto_renew"]:
            if not frame[col].isin([0, 1]).all():
                raise ValueError(f"{col}: expected binary")
    return frame


def ingest(raw, database, provenance="kkbox", chunksize=200_000, quarantine_negative_logs=False):
    raw, database = Path(raw), Path(database)
    database.parent.mkdir(parents=True, exist_ok=True)
    files = {t: sorted(p for p in raw.rglob(f"{t}*.csv") if "coverage" not in p.relative_to(raw).parts) for t in SCHEMAS}
    if any(not paths for paths in files.values()):
        raise FileNotFoundError("Need transactions*.csv AND user_logs*.csv (extract Kaggle archives first)")
    manifest = {"provenance": provenance, "files": [], "tables": {}}
    if (raw/"sampling-report.json").is_file():
        manifest["sampling"] = json.loads((raw/"sampling-report.json").read_text())
        if manifest["sampling"].get("status") != "complete":
            raise ValueError("Subscriber sampling is incomplete; rerun sample before ingestion")
        if provenance == "kkbox":
            manifest["provenance"] = "kkbox_subscriber_sample"
    con = duckdb.connect(str(database))
    con.execute("BEGIN")
    try:
        con.execute("CREATE OR REPLACE TABLE invalid_logs (msno VARCHAR, date TIMESTAMP, total_secs DOUBLE, reason VARCHAR)")
        manifest["quality_policy"] = "quarantine listening duration <0 or >=1e12 seconds; exclude affected users only after offending event" if quarantine_negative_logs else "strict"
        for table, paths in files.items():
            con.execute(f"DROP TABLE IF EXISTS {table}")
            first = True
            for path in paths:
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                manifest["files"].append({"name": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
                for chunk in pd.read_csv(path, chunksize=chunksize, dtype={"msno": "str"}):
                    if table == "user_logs" and quarantine_negative_logs and "total_secs" in chunk:
                        seconds = pd.to_numeric(chunk.total_secs, errors="raise")
                        invalid_duration = (seconds < 0) | (seconds >= 1e12)
                        if invalid_duration.any():
                            # Validate all other fields without silently repairing duration.
                            checked = normalize(chunk.loc[invalid_duration].assign(total_secs=0), table)
                            invalid = checked[["msno", "date"]].copy()
                            invalid["total_secs"] = chunk.loc[invalid_duration, "total_secs"].to_numpy(dtype=float)
                            invalid["reason"] = ["negative_listening_duration" if v < 0 else "overflow_scale_positive_duration" for v in invalid.total_secs]
                            con.register("invalid_batch", invalid)
                            con.execute("INSERT INTO invalid_logs SELECT * FROM invalid_batch")
                            chunk = chunk.loc[~invalid_duration]
                    batch = normalize(chunk, table)
                    con.register("batch", batch)
                    con.execute(f"CREATE TABLE {table} AS SELECT * FROM batch" if first else f"INSERT INTO {table} SELECT * FROM batch")
                    first = False
            if first:
                raise ValueError(f"{table}: no rows")
            # Exact duplicate overlap between original/v2 exports is safe to remove.
            before = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT DISTINCT * FROM {table}")
            date = "transaction_date" if table == "transactions" else "date"
            count, start, end = con.execute(f"SELECT count(*), min({date}), max({date}) FROM {table}").fetchone()
            manifest["tables"][table] = {"rows": count, "duplicates_removed": before-count, "min_date": str(start), "max_date": str(end)}
        # KKBOX has same-day revisions without a reliable event ordering. Do not invent one.
        for table, date in [("transactions", "transaction_date"), ("user_logs", "date")]:
            conflicts = con.execute(f"SELECT count(*) FROM (SELECT msno,{date} FROM {table} GROUP BY ALL HAVING count(*)>1)").fetchone()[0]
            manifest["tables"][table]["conflicting_keys"] = conflicts
        invalid_rows, invalid_users = con.execute("SELECT count(*),count(DISTINCT msno) FROM invalid_logs").fetchone()
        negatives = con.execute("SELECT count(*) FROM invalid_logs WHERE total_secs<0").fetchone()[0]
        manifest["quality"] = {"invalid_listening_rows_quarantined": invalid_rows, "negative_listening_rows_quarantined": negatives,
                               "overflow_scale_positive_rows_quarantined": invalid_rows-negatives, "affected_subscribers_all_dates": invalid_users}
        con.execute("CREATE TABLE IF NOT EXISTS metadata (payload VARCHAR)")
        con.execute("DELETE FROM metadata")
        con.execute("INSERT INTO metadata VALUES (?)", [json.dumps(manifest)])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    database.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
