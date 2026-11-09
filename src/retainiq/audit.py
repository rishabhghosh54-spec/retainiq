"""Aggregate cohort and label-agreement diagnostics; never exports subscriber IDs."""
import pandas as pd
import duckdb

from retainiq.features import snapshot
from retainiq.labels import reference_labels, LABEL_METHOD


def cohort_audit(database, cutoff, observation_end):
    with duckdb.connect(str(database), read_only=True) as con:
        counts = con.execute("""
          WITH past AS (SELECT * FROM transactions WHERE transaction_date < CAST(? AS DATE)),
          ambiguous AS (SELECT msno FROM past GROUP BY msno,transaction_date HAVING count(*)>1)
          SELECT (SELECT count(DISTINCT msno) FROM past) historical_subscribers,
                 (SELECT count(DISTINCT msno) FROM ambiguous) transaction_ambiguous_subscribers
        """, [cutoff]).df().iloc[0].to_dict()
    rows = snapshot(database, cutoff, observation_end)
    return {"cutoff": cutoff, **{k: int(v) for k, v in counts.items()},
            "eligible_matured_rows": len(rows), "reference_churn_rate": float(rows.is_churn.mean()) if len(rows) else None,
            "label_method": LABEL_METHOD}


def compare_official(database, label_file, cutoff="2017-02-01", observation_end="2017-03-31"):
    official = pd.read_csv(label_file, dtype={"msno": str})
    if official.msno.duplicated().any() or not official.is_churn.isin([0, 1]).all():
        raise ValueError("Official label file must have unique subscribers and binary outcomes")
    with duckdb.connect(str(database), read_only=True) as con:
        proxy = reference_labels(con, cutoff, observation_end)
    joined = proxy[["msno", "is_churn"]].merge(official, on="msno", suffixes=("_proxy", "_official"), validate="one_to_one")
    confusion = pd.crosstab(joined.is_churn_official, joined.is_churn_proxy).reindex(index=[0, 1], columns=[0, 1], fill_value=0)
    official_churn = int((joined.is_churn_official == 1).sum())
    churn_agree = int(((joined.is_churn_official == 1) & (joined.is_churn_proxy == 1)).sum())
    return {"cutoff": cutoff, "official_file": str(label_file.name), "official_rows": len(official),
            "proxy_rows": len(proxy), "matched_rows": len(joined),
            "agreement": float((joined.is_churn_proxy == joined.is_churn_official).mean()) if len(joined) else None,
            "official_churn_rows_matched": official_churn,
            "official_churn_missed_by_proxy": official_churn-churn_agree,
            "official_churn_recall_of_proxy": churn_agree/official_churn if official_churn else None,
            "label_method": LABEL_METHOD,
            "release_gate": "Reference reconstruction and supplied labels are distinct targets. Report disagreements; never overwrite either to improve agreement.",
            "official_prevalence_matched": float(joined.is_churn_official.mean()) if len(joined) else None,
            "proxy_prevalence_matched": float(joined.is_churn_proxy.mean()) if len(joined) else None,
            "confusion_official_rows_proxy_columns": confusion.to_numpy().tolist(),
            "limitations": "Agreement on intersecting monthly reference cohort, before listening quality exclusions. Reconstructed reference labels may differ from supplied labels. March reconstruction is censored; supplied March labels may be evaluated separately as external ground truth."}
