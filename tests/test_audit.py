from pathlib import Path

from retainiq.audit import cohort_audit, compare_official
from retainiq.data import ingest
from retainiq.demo import generate
from retainiq.features import snapshot


def test_official_comparison_reports_only_intersection(tmp_path):
    raw = tmp_path/"raw"
    generate(raw, n=40)
    db = tmp_path/"test.duckdb"
    ingest(raw, db, "synthetic")
    proxy = snapshot(db, "2016-01-01", "2016-09-30")
    label_file = tmp_path/"labels.csv"
    proxy[["msno", "is_churn"]].iloc[:20].to_csv(label_file, index=False)
    report = compare_official(db, label_file, "2016-01-01", "2016-09-30")
    assert report["matched_rows"] == 20
    assert report["agreement"] == 1.0
    assert sum(map(sum, report["confusion_official_rows_proxy_columns"])) == 20
    cohort = cohort_audit(db, "2016-01-01", "2016-09-30")
    assert cohort["eligible_matured_rows"] == 40
