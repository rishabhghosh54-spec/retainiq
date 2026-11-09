import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import duckdb

import pandas as pd

from retainiq.data import ingest
from retainiq.demo import generate
from retainiq.features import snapshot
from retainiq.model import train


def main():
    parser = argparse.ArgumentParser(description="RetainIQ reproducible research CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--output", default="artifacts/demo")
    demo.add_argument("--users", type=int, default=600)
    check = sub.add_parser("access")
    check.add_argument("--raw", default="data/raw")
    fetch = sub.add_parser("download")
    fetch.add_argument("--raw", default="data/raw")
    ip = sub.add_parser("ingest")
    ip.add_argument("--raw", required=True)
    ip.add_argument("--database", default="data/kkbox.duckdb")
    ip.add_argument("--quarantine-invalid-logs", "--quarantine-negative-logs", dest="quarantine_negative_logs", action="store_true", help="Preserve negative or overflow-scale (>=1e12 seconds) durations separately; exclude subscribers using only pre-cutoff invalid records")
    sample = sub.add_parser("sample")
    sample.add_argument("--raw", required=True)
    sample.add_argument("--output", default="data/sample")
    sample.add_argument("--buckets", type=int, default=5)
    sample.add_argument("--modulus", type=int, default=1000)
    audit = sub.add_parser("audit")
    audit.add_argument("--database", required=True)
    audit.add_argument("--cutoffs", nargs="+", required=True)
    audit.add_argument("--observation-end", required=True)
    audit.add_argument("--official-labels")
    audit.add_argument("--official-cutoff", default="2017-02-01")
    audit.add_argument("--output", default="artifacts/kkbox/data-audit.json")
    full = sub.add_parser("validate-reference")
    full.add_argument("--raw", required=True)
    full.add_argument("--database", default="data/full-transactions.duckdb")
    full.add_argument("--official-labels", required=True)
    full.add_argument("--output", default="artifacts/reference/full-label-audit.json")
    evaluate = sub.add_parser("evaluate-official")
    evaluate.add_argument("--database", required=True)
    evaluate.add_argument("--model", required=True)
    evaluate.add_argument("--labels", required=True)
    evaluate.add_argument("--cutoff", required=True)
    evaluate.add_argument("--observation-end", required=True)
    evaluate.add_argument("--output", default="artifacts/reference/official-evaluation.json")
    build = sub.add_parser("build")
    build.add_argument("--database", required=True)
    build.add_argument("--cutoffs", nargs=3, required=True)
    build.add_argument("--observation-end", required=True, help="Last date with verified COMPLETE transaction coverage; max event date alone is insufficient")
    build.add_argument("--output", default="data/features.parquet")
    build.add_argument("--label-method", choices=["reference", "legacy"], default="reference")
    fit = sub.add_parser("train")
    fit.add_argument("--features", required=True)
    fit.add_argument("--output", default="artifacts/kkbox")
    fit.add_argument("--audit", help="Aggregate data-audit JSON to attach to evaluation report")
    args = parser.parse_args()
    if args.command == "access":
        raw = Path(args.raw)
        print(json.dumps({"raw_exists": raw.exists(), "csv_files": sorted(p.name for p in raw.glob("*.csv")),
            "kaggle_cli": bool(shutil.which("kaggle")),
            "credential_file_present": (Path.home()/".kaggle"/"kaggle.json").is_file(),
            "credential_environment_present": bool(os.getenv("KAGGLE_API_TOKEN") or (os.getenv("KAGGLE_USERNAME") and os.getenv("KAGGLE_KEY"))),
            "authorization_verified": False}, indent=2))
    elif args.command == "download":
        if not shutil.which("kaggle"):
            raise SystemExit("Install .[data], configure Kaggle credentials, and accept competition rules first.")
        Path(args.raw).mkdir(parents=True, exist_ok=True)
        subprocess.run(["kaggle", "competitions", "download", "-c", "kkbox-churn-prediction-challenge", "-p", args.raw], check=True)
        print("Downloaded archives. Extract ZIP and nested .7z files locally; do not commit data. Then ingest.")
    elif args.command == "sample":
        from retainiq.sample import sample_sources
        print(json.dumps(sample_sources(args.raw, args.output, args.buckets, args.modulus), indent=2))
    elif args.command == "evaluate-official":
        from retainiq.evaluation import evaluate_official
        print(json.dumps(evaluate_official(args.database,args.model,args.labels,args.cutoff,args.observation_end,args.output),indent=2))
    elif args.command == "validate-reference":
        from retainiq.validation import full_reference_audit
        print(json.dumps(full_reference_audit(args.raw, args.database, args.official_labels, args.output), indent=2))
    elif args.command == "audit":
        from retainiq.audit import cohort_audit, compare_official
        report = {"cohorts": [cohort_audit(args.database, d, args.observation_end) for d in args.cutoffs]}
        if args.official_labels:
            report["official_label_comparison"] = compare_official(args.database, Path(args.official_labels), args.official_cutoff, args.observation_end)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    elif args.command == "ingest":
        print(json.dumps(ingest(args.raw, args.database, quarantine_negative_logs=args.quarantine_negative_logs), indent=2))
    elif args.command == "build":
        frames = [snapshot(args.database, d, args.observation_end, label_method=args.label_method) for d in args.cutoffs]
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        pd.concat(frames, ignore_index=True).to_parquet(args.output, index=False)
        with duckdb.connect(str(args.database), read_only=True) as con:
            source = json.loads(con.execute("SELECT payload FROM metadata").fetchone()[0])
        audit = {"source": source, "observation_end_attested": args.observation_end,
                 "cohorts": [{"cutoff": d, "matured_rows": len(f),
                     "unmatured_dropped": len(snapshot(args.database, d, args.observation_end, labels=False, label_method=args.label_method))-len(f)} for d, f in zip(args.cutoffs, frames)]}
        Path(args.output).with_suffix(".audit.json").write_text(json.dumps(audit, indent=2))
        print(json.dumps(audit, indent=2))
    elif args.command == "train":
        audit = json.loads(Path(args.audit).read_text()) if args.audit else None
        print(json.dumps(train(pd.read_parquet(args.features), args.output, data_audit=audit), indent=2))
    elif args.command == "demo":
        out = Path(args.output)
        generate(out/"raw", n=args.users)
        ingest(out/"raw", out/"demo.duckdb", provenance="synthetic")
        frame = pd.concat([snapshot(out/"demo.duckdb", d, "2016-09-30") for d in ["2016-01-01", "2016-04-01", "2016-07-01"]], ignore_index=True)
        frame.to_parquet(out/"features.parquet", index=False)
        print(json.dumps(train(frame, out), indent=2))


if __name__ == "__main__":
    main()
