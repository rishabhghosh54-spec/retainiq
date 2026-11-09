# Live API verification — 2026-11-09

The user started `Start-RetainIQ-API.cmd` in the existing project folder and confirmed Uvicorn was running. The assistant then tested the actual HTTP service through Swagger UI at http://127.0.0.1:8000/docs in the in-app browser. These are live service results, separate from the previously restricted in-process HTTP tests.

| Check | Observed result |
|---|---|
| GET /health | HTTP 200; `ready`; `kkbox_subscriber_sample` provenance |
| POST /predict, two valid illustrative records | HTTP 200; two probabilities and reference-target metadata |
| Renewal flag of 2 | HTTP 422; `less_than_equal` validation error |
| Extra target field `is_churn` | HTTP 422; `extra_forbidden` validation error |
| Empty records list | HTTP 422; `too_short` validation error |
| Batch of 1,001 records | HTTP 422; `too_long`; maximum 1,000 |
| Batch of 1,000 records | HTTP 200; exactly 1,000 probabilities |

The two valid example records use manually entered features, not exported subscriber records. Their probabilities were `0.02089953943780349` and `0.7329359122980194`. Exact equality with predictions from the saved local reference model was verified afterward. No predicted example probability is presented as a measured individual outcome or treatment effect.

The response identified the boosted model, `kkbox_subscriber_sample` provenance, `kkbox_reference_gap_v1` label method, and `reference_reconstruction_research` release status. Model SHA-256 and request examples are in `examples/live-api-review.json`. A successful compact response is shown in `docs/screenshots/live-api-prediction.png`.

Large request examples briefly made the Swagger/browser automation slow to render. The HTTP response was inspected after each timeout: the oversized request was rejected and the maximum allowed batch succeeded. Those UI delays are not model-latency measurements; no latency or load benchmark was performed. The documentation page was restored to the compact two-record successful example.

Both dashboard and API were left running in the user's existing launcher windows. The missing-model branch was unit-checked earlier, including inference returning 503, but was not tested by disabling the running real service. No claim is made of live missing-model HTTP coverage, a successful remote CI run, Docker execution, public hosting, production authentication or concurrent-load performance.

To stop either local service, focus its launcher window and press Ctrl+C. To open the API again, double-click `Start-RetainIQ-API.cmd` from Windows File Explorer, then visit http://localhost:8000/docs.
