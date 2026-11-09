# Defending RetainIQ in an interview

**Problem.** Rank upcoming-expiry subscribers for review using information available before a historical decision date. Keep probability estimation, capacity planning and causal intervention benefit separate.

**What was actually built?** Source hashing and complete-user sampling across more than 410 million listening rows, strict transactional ingestion, explicit telemetry quarantine, SQL historical features, a cancellation-aware label port, an independent Python oracle, chronological models, an external supplied-label evaluation, FastAPI and Streamlit.

**The important bug.** An extension-only label proxy missed cancellations that shorten expiry. Replacing it with the supplied reference's ordered state walk changed the cohort and targets. Day 30 is churn; monthly eligibility and lexical plan-signature ordering matter. A high overall label-agreement percentage hid weak agreement on the churn class, so the audit also reports the confusion matrix and churn recall.

**Why not force 100% official-label agreement?** Reference-rule fidelity and reproduction of supplied labels are different claims. SQL and a separately written Python implementation agree on the sample, while full-file supplied labels still differ. Overwriting targets to improve agreement would hide uncertainty. March supplied labels therefore get a separate evaluation, with the model frozen and no test-driven tuning.

**Leakage defenses.** Strict pre-cutoff features; no IDs/targets/profile exports as features; prior outcomes mature before subsequent decisions; uniform censoring; future-event and future-quarantine invariance tests; whole-user sampling. Without source arrival timestamps, event-date safety cannot prove original ingestion-time availability.

**Why these metrics?** Log loss and Brier evaluate probabilities; AP and top-K recall evaluate rare-case ranking; ROC-AUC is secondary. March Recall@10%=50% is useful for a capacity scenario, not proof that offers save half the churners. Calibration plots and label shift remain visible.

**What is novel?** The defensible contribution is the auditable temporal/label contract and independent validation, not a new algorithm or inflated score. The modest official-label AUC is reported honestly.

**Scale and limitations.** Full source scanning and full transaction-label auditing were executed; model training used a 0.5% subscriber sample. No claim of a production deployment, distributed training, business revenue gains, or modern SaaS population performance.

**Example portfolio wording.** Built RetainIQ, a reproducible churn research system that audited 22.98M transaction rows, implemented and independently checked cancellation-aware historical labels, and evaluated a frozen model on 4,034 sampled subscribers using supplied March labels (ROC-AUC 0.762; 50% recall at 10% review capacity). Delivered tested feature pipelines, Streamlit, FastAPI and documented target/availability limitations.

Use that statement only with its sample and target qualifications; do not describe it as full-data model training or a Kaggle score.
