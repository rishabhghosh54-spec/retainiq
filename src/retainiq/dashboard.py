import json
import os
from math import ceil
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="RetainIQ", page_icon="🎧", layout="wide")
st.title("RetainIQ")
st.caption("Subscription risk · chronological validation · auditable evidence")
folder = Path(os.getenv("RETAINIQ_ARTIFACTS", "artifacts/demo"))
if not (folder/"report.json").is_file():
    st.info("No trained model. Run: retainiq demo")
    st.stop()
report = json.loads((folder/"report.json").read_text())
if report["provenance"] == "synthetic":
    st.warning("SYNTHETIC DEMO — these results verify software behavior, not KKBOX predictive performance.")
else:
    st.info("KKBOX research cohort: reference reconstruction and supplied labels are evaluated separately.")
    audit = report.get("data_audit") or {}
    comparison = audit.get("official_label_comparison")
    if comparison:
        st.warning(f'Target audit: reconstruction disagrees on {comparison["official_churn_missed_by_proxy"]} supplied churn cases out of {comparison["official_churn_rows_matched"]} in the matched audit cohort. The two targets remain distinct.')
scored = pd.read_parquet(folder/"scored.parquet")
external = json.loads((folder/"official-evaluation.json").read_text()) if (folder/"official-evaluation.json").is_file() else None
tabs = st.tabs(["Historical backtest", "Supplied-label evaluation", "Review queue", "Model & evidence"])
with tabs[0]:
    cols = st.columns(4)
    for col, key in zip(cols, ["log_loss", "average_precision", "brier", "lift_at_10pct"]):
        col.metric(key.replace("_", " ").title(), f'{report["test"][key]:.3f}')
    st.write("Validation comparison (selection happens here)")
    st.dataframe(pd.DataFrame(report["validation"]).T)
    st.write(f'Frozen winner: {report["selected_model"]}. Test period: {report["split_dates"][-1]}')
    st.line_chart(pd.DataFrame(report["calibration"]).set_index("predicted"))
    st.bar_chart(scored.risk.value_counts(bins=10, sort=False).rename_axis("risk interval").rename("subscribers").set_axis([str(x) for x in scored.risk.value_counts(bins=10, sort=False).index]))
with tabs[1]:
    if external:
        st.subheader("March 2017 · supplied labels")
        st.caption(f'{external["matched_rows"]:,} matched subscribers. Model frozen before this cohort. Metrics describe this sampled eligible population.')
        cols = st.columns(4)
        for col,key in zip(cols,["log_loss","average_precision","roc_auc","lift_at_10pct"]):
            col.metric(key.replace("_"," ").title(),f'{external["test"][key]:.3f}')
        st.dataframe(pd.DataFrame({"Frozen model":external["test"],"Prevalence baseline":external["baseline"]}).drop(index="log_loss_bootstrap_95pct",errors="ignore"))
        st.write(external["protocol"])
        calibration = pd.DataFrame(external["calibration"])
        calibration["ideal"] = calibration.predicted
        st.line_chart(calibration.set_index("predicted"))
        for limitation in external["limitations"]:
            st.caption(limitation)
    else:
        st.info("No separate supplied-label evaluation loaded. Run evaluate-official after freezing the model.")
with tabs[2]:
    review = scored
    if external and (folder/"official-evaluation.scored.parquet").is_file():
        period = st.selectbox("Review cohort",["March 2017", "Historical test"])
        if period == "March 2017":
            review = pd.read_parquet(folder/"official-evaluation.scored.parquet")
    capacity = st.slider("Review capacity (% of cohort)", 1, 50, 10)
    queue = review.sort_values("risk", ascending=False,kind="stable").head(max(1, ceil(len(review)*capacity/100)))
    st.caption("Risk prioritization only. No claim that an offer will prevent churn. Subscriber IDs stay local.")
    st.dataframe(queue.drop(columns="is_churn"), hide_index=True)
    st.download_button("Download review queue", queue.drop(columns="is_churn").to_csv(index=False), "review_queue.csv")
with tabs[3]:
    st.write(f'Outcome definition: {report.get("label_method", "legacy extension proxy")}')
    st.write(report["protocol"])
    st.bar_chart(pd.Series(report["validation_permutation_importance"]).sort_values())
    st.caption("Validation permutation importance measures predictive dependence, not causal drivers or individual explanations.")
    for limitation in report["limitations"]:
        st.write("• " + limitation)
    if (folder/"full-label-audit.json").is_file():
        full = json.loads((folder/"full-label-audit.json").read_text())
        st.write(f'Full transaction audit: {full["raw_transaction_rows"]:,} source rows; {full["matched_rows"]:,} matched supplied labels.')
        st.json(full)
    st.json(report)
