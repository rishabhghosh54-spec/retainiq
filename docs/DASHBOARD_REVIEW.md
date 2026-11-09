# Open and review RetainIQ

## Open the current real-data dashboard

In this existing project folder, double-click **Start-RetainIQ.cmd**. Keep its window open. The browser should open automatically after startup; otherwise visit http://localhost:8501.

The trained model and real-data reports are already present in this workspace. The source ZIP intentionally excludes private data and trained binaries, so a freshly extracted copy elsewhere must first run the README's data/training instructions. Launch from the existing project folder for this review.

The launcher uses an existing project virtual environment when present, checks dependencies, and reports missing requirements. On this original Python 3.14 build machine it can also use the workspace libraries if needed. It makes no system-setting changes, downloads nothing, and serves only on localhost. Press Ctrl+C to stop the service.

## Review flow

1. **Historical backtest:** inspect validation selection, the later reference-target result and calibration. The January test is a revised retrospective backtest.
2. **Supplied-label evaluation:** confirm March shows 4,034 matched subscribers, ROC-AUC 0.762 and log loss 0.213. This uses supplied labels and the previously frozen model.
3. **Review queue:** select March 2017 and 10% capacity. It should contain 404 subscribers sorted by risk. At 20%, expect 807. Switching to Historical test gives 413 at 10% and 825 at 20%. Rounding now matches the evaluation's top-K calculation.
4. **Model & evidence:** check the source/label audit, known discrepancies and the limits on interpreting retention benefit. Subscriber-level exports are local; keep them out of public demos and GitHub.

No claim is made that an offer will prevent a predicted churn outcome. A review-capacity scenario is not an intervention experiment.

## Optional local API

Double-click **Start-RetainIQ-API.cmd**, keep its window open and visit http://localhost:8000/docs. A ready model has synthetic/real provenance and an explicit label definition. The launcher uses the current `artifacts/reference/model.joblib`.

## Checks completed in this environment

The Streamlit application test rendered all four tabs, matched the displayed supplied-label metrics to the saved report, switched both review cohorts, and verified queue sizes, descending risk order, unique IDs and hidden target labels at capacities of 1%, 10%, 20% and 50%. A synthetic 83-subscriber regression fixture checks the rounding edge case (nine users at 10%, 17 at 20%).

After the rounding correction, the full runnable suite completed with **30 passed, two deselected in 27.09 seconds**. The two excluded HTTP transport cases remain blocked by the same local networking restriction. The Python package wheel rebuilt successfully. Predictive models and measured evaluation results were unchanged by this interface correction.

Initial automatic Streamlit and Uvicorn startup attempts used bounded diagnostic processes. Both timed out in Windows/Python's internal socket-pair setup before serving requests. Those diagnostic processes were stopped. A separate socket-pair probe timed out after three seconds. Those initial checks did not establish browser or live HTTP success; the follow-up below records the subsequently completed dashboard review.

Aggregate evidence: `examples/dashboard-review.json` and `examples/local-launch-check.json`. No private rows are included in those reports. Docker and remote publishing remain unverified.

## Follow-up: live dashboard reviewed on 2026-11-09

The user launched the existing project from Windows File Explorer and skipped Streamlit's optional first-run email field by leaving it blank. The service then ran at http://127.0.0.1:8501. Opening a `.cmd` link inside Codex shows its source; it must be executed from Windows File Explorer. A ZIP copy lacks the ignored trained artifacts, so the existing project folder is the appropriate location on this machine.

The assistant opened the live service in the in-app browser and reviewed Historical backtest, Supplied-label evaluation, Review queue, and Model & evidence. The March page visibly showed 4,034 matched subscribers, log loss 0.213, average precision 0.309, ROC-AUC 0.762 and lift 4.993, matching saved reports. The capacity slider changed from 10 to 11 and back to 10. The cohort selector changed from March to Historical test and back to March. No data export or deployment was performed.

The service was left running in the user's launcher window, and the March supplied-label tab was left visible. The aggregate-results screenshot is `docs/screenshots/live-march-evaluation.png`; the machine-readable record is `examples/live-browser-review.json`. That review verified the dashboard. A subsequent [live API review](API_REVIEW.md) verified seven HTTP checks and offline prediction parity. Docker, hosted deployment and remote CI remain unverified.
