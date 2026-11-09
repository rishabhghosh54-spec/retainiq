"""Deterministic whole-subscriber sampling for resource-limited real-data runs.

All source rows are scanned, but only one stable MD5 bucket subset is retained.
Never sample log rows independently: doing so would corrupt activity features.
"""
import hashlib
import json
import time
from pathlib import Path

import duckdb


def sample_sources(raw, output, buckets=5, modulus=1000, memory_limit="3GB"):
    raw, output = Path(raw).resolve(), Path(output).resolve()
    if output == raw or raw in output.parents:
        raise ValueError("Sample output must be outside raw input directory")
    if not 0 < buckets <= modulus:
        raise ValueError("Require 0 < buckets <= modulus")
    sources = {table: sorted(raw.rglob(f"{table}*.csv")) for table in ["transactions", "user_logs"]}
    if any(not paths for paths in sources.values()):
        raise FileNotFoundError("Both transaction and listening CSVs are required")
    names = [p.name for paths in sources.values() for p in paths]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate source basenames would overwrite sampled files; resolve input layout first")
    output.mkdir(parents=True, exist_ok=True)
    (output/"coverage").mkdir(exist_ok=True)
    report = {"status": "running", "sampling": {"algorithm": "md5_number_lower(msno) % modulus < buckets", "buckets": buckets,
               "modulus": modulus, "expected_fraction": buckets/modulus,
               "scope": "Complete histories for selected transaction subscribers; no date or outcome sampling"}, "files": []}
    (output/"sampling-report.json").write_text(json.dumps(report, indent=2))
    with duckdb.connect() as con:
        con.execute("SET threads=2")
        con.execute(f"SET memory_limit='{memory_limit}'")
        con.execute("SET disabled_optimizers='join_order,build_side_probe_side'")
        for table, paths in sources.items():
            if table == "user_logs":
                # Hash transaction users once, then use a set join on the much larger
                # activity table instead of computing MD5 hundreds of millions of times.
                con.read_csv([str(output/p.name) for p in sources["transactions"]], header=True, all_varchar=True).create_view("sample_tx", replace=True)
                con.execute("CREATE TEMP TABLE selected_users AS SELECT DISTINCT msno FROM sample_tx").fetchall()
            for path in paths:
                start = time.monotonic()
                print(f"Scanning {path.name}", flush=True)
                date = "transaction_date" if table == "transactions" else "date"
                con.read_csv(str(path), header=True, all_varchar=True).create_view("source", replace=True)
                days = con.execute(f"SELECT {date} event_date,count(*) rows FROM source GROUP BY {date} ORDER BY {date}").df()
                profile = {"n": int(days.rows.sum()), "first_date": str(days.event_date.min()), "last_date": str(days.event_date.max())}
                days.to_csv(output/"coverage"/f"{path.stem}.csv", index=False)
                destination = output/path.name
                # SQL literals are generated only from integers and a safely quoted path.
                dest = str(destination).replace("'", "''")
                select = f"SELECT * FROM source WHERE md5_number_lower(msno) % {int(modulus)} < {int(buckets)}" if table == "transactions" else "SELECT s.* FROM source s SEMI JOIN selected_users u ON s.msno=u.msno"
                con.execute(f"COPY ({select}) TO '{dest}' (HEADER, FORMAT CSV)").fetchall()
                sample_rows = con.execute("SELECT count(*) FROM read_csv(?, header=true, all_varchar=true)", [str(destination)]).fetchall()[0][0]
                print(f"Hashing {path.name}", flush=True)
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(8*1024*1024), b""):
                        digest.update(block)
                entry = {"file": path.name, "source_relative_path": str(path.relative_to(raw)),
                         "bytes": path.stat().st_size, "sha256": digest.hexdigest(),
                         "rows": int(profile["n"]), "first_date": profile["first_date"], "last_date": profile["last_date"],
                         "selected_rows": sample_rows, "seconds": round(time.monotonic()-start, 2)}
                report["files"].append(entry)
                (output/"sampling-report.json").write_text(json.dumps(report, indent=2))
                print(json.dumps(entry), flush=True)
    report["status"] = "complete"
    (output/"sampling-report.json").write_text(json.dumps(report, indent=2))
    return report
