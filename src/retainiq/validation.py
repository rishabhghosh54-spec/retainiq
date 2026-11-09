"""Full-transaction label audit independent of the sampled model experiment."""
import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd

from retainiq.audit import compare_official


def full_reference_audit(raw, database, label_file, output):
    paths = sorted(Path(raw).rglob("transactions*.csv"))
    if not paths:
        raise FileNotFoundError("No transaction CSVs")
    database, output = Path(database), Path(output)
    database.parent.mkdir(parents=True, exist_ok=True)
    source_files = []
    for path in paths:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8*1024*1024), b""):
                digest.update(block)
        source_files.append({"file": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()})
    with duckdb.connect(str(database)) as con:
        con.execute("SET threads=2")
        con.execute("SET memory_limit='3GB'")
        con.read_csv(list(map(str, paths)), header=True, all_varchar=True).create_view("source")
        numeric = ["payment_method_id", "payment_plan_days", "plan_list_price", "actual_amount_paid", "is_auto_renew", "is_cancel"]
        checks = " OR ".join(f"{col} IS NULL OR NOT regexp_full_match({col},'[0-9]+')" for col in numeric)
        invalid = con.execute(f"SELECT count(*) FROM source WHERE msno IS NULL OR trim(msno)='' OR {checks}").fetchall()[0][0]
        if invalid:
            raise ValueError(f"{invalid} transaction rows violate full-audit numeric/key schema")
        raw_rows = con.execute("SELECT count(*) FROM source").fetchall()[0][0]
        cols = ",".join(f"CAST({col} AS BIGINT) {col}" for col in numeric)
        con.execute(f"""CREATE OR REPLACE TABLE transactions AS SELECT DISTINCT msno,{cols},
            strptime(transaction_date,'%Y%m%d') transaction_date,
            strptime(membership_expire_date,'%Y%m%d') membership_expire_date FROM source""").fetchall()
        flag_errors = con.execute("SELECT count(*) FROM transactions WHERE is_cancel NOT IN (0,1) OR is_auto_renew NOT IN (0,1)").fetchall()[0][0]
        if flag_errors:
            raise ValueError("Invalid binary flags")
        clean_rows = con.execute("SELECT count(*) FROM transactions").fetchall()[0][0]
    report = compare_official(database, Path(label_file))
    report.update({"scope": "All supplied transaction rows; no subscriber sampling or listening-based exclusion",
                   "raw_transaction_rows": raw_rows, "deduplicated_transaction_rows": clean_rows, "sources": source_files})
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    return report
