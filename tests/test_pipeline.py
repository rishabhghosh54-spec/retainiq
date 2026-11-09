import asyncio

import duckdb
import numpy as np
import pandas as pd
import pytest
from httpx import AsyncClient, ASGITransport
from streamlit.testing.v1 import AppTest

from retainiq.api import app, lifespan
from retainiq.data import ingest, normalize
from retainiq.demo import generate
from retainiq.features import FEATURES, snapshot
from retainiq.model import load_bundle, predict, train


@pytest.fixture
def database(tmp_path):
    generate(tmp_path/"raw", n=83)
    db = tmp_path/"demo.duckdb"
    ingest(tmp_path/"raw", db, "synthetic", chunksize=71)
    return db


def test_future_events_cannot_change_features(database):
    before = snapshot(database, "2016-04-01", "2016-09-30", labels=False)
    with duckdb.connect(str(database)) as con:
        con.execute("INSERT INTO user_logs SELECT * REPLACE (DATE '2017-01-01' AS date, 999999 AS total_secs) FROM user_logs LIMIT 1")
        con.execute("INSERT INTO transactions SELECT * REPLACE (DATE '2017-01-01' AS transaction_date, 0 AS is_auto_renew) FROM transactions LIMIT 1")
        con.execute("INSERT INTO transactions SELECT * REPLACE (DATE '2017-01-01' AS transaction_date, 1 AS is_auto_renew) FROM transactions LIMIT 1")
    after = snapshot(database, "2016-04-01", "2016-09-30", labels=False)
    pd.testing.assert_frame_equal(before, after)


def test_cutoff_boundary_and_censoring(database):
    base = snapshot(database, "2016-01-01", "2016-09-30", labels=False)
    with duckdb.connect(str(database)) as con:
        con.execute("INSERT INTO user_logs SELECT * REPLACE (DATE '2016-01-01' AS date, 999999 AS total_secs) FROM user_logs LIMIT 1")
    after = snapshot(database, "2016-01-01", "2016-09-30", labels=False)
    pd.testing.assert_frame_equal(base, after)
    censored = snapshot(database, "2016-01-01", "2016-01-15")
    assert censored.empty


def test_validation_rejects_bad_input():
    with pytest.raises(ValueError, match="missing columns"):
        normalize(pd.DataFrame({"msno": ["a"]}), "transactions")
    with pytest.raises(ValueError, match="negative"):
        normalize(pd.DataFrame({"msno": ["a"], "date": [20160101], "num_unq": [1], "total_secs": [-1]}), "user_logs")


def test_reference_tie_feature_convention(database):
    with duckdb.connect(str(database)) as con:
        con.execute("INSERT INTO transactions SELECT * REPLACE (1-is_auto_renew AS is_auto_renew) FROM transactions WHERE msno='synthetic-00000' AND transaction_date < DATE '2016-01-01'")
    result = snapshot(database, "2016-01-01", "2016-09-30")
    assert "synthetic-00000" in result.msno.tolist()
    assert result.set_index("msno").loc["synthetic-00000", "auto_renew"] == 0


def test_renewal_deadline_is_inclusive(tmp_path):
    raw = tmp_path/"raw"
    raw.mkdir()
    pd.DataFrame([
        ["a", 20151201, 20160110, 0, 1, 149, 30],
        ["b", 20151201, 20160110, 0, 1, 149, 30],
        ["a", 20160209, 20160310, 0, 1, 149, 30],
        ["b", 20160210, 20160310, 0, 1, 149, 30],
    ], columns=["msno", "transaction_date", "membership_expire_date", "is_cancel", "is_auto_renew", "actual_amount_paid", "payment_plan_days"]).to_csv(raw/"transactions.csv", index=False)
    pd.DataFrame([["a", 20151230, 10, 1]], columns=["msno", "date", "total_secs", "num_unq"]).to_csv(raw/"user_logs.csv", index=False)
    ingest(raw, tmp_path/"test.duckdb")
    labels = snapshot(tmp_path/"test.duckdb", "2016-01-01", "2016-03-31", label_method="legacy").set_index("msno").is_churn
    assert labels.to_dict() == {"a": 0, "b": 1}


@pytest.fixture
def trained(database, tmp_path):
    frame = pd.concat([snapshot(database, d, "2016-09-30") for d in ["2016-01-01", "2016-04-01", "2016-07-01"]], ignore_index=True)
    report = train(frame, tmp_path/"artifacts")
    return frame, report, tmp_path/"artifacts"


def test_train_and_api(trained, monkeypatch):
    frame, report, folder = trained
    assert report["provenance"] == "synthetic"
    bundle = load_bundle(folder/"model.joblib")
    records = frame[FEATURES].iloc[:2].to_dict("records")
    monkeypatch.setenv("RETAINIQ_MODEL", str(folder/"model.joblib"))
    async def scenario():
        async with lifespan(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://retainiq.test", trust_env=False) as client:
                assert (await client.get("/health")).json()["status"] == "ready"
                response = await client.post("/predict", json={"records": records})
                assert response.status_code == 200
                assert response.json()["probabilities"] == predict(bundle, records)
                assert response.json()["label_method"] == "kkbox_reference_gap_v1"
                assert (await client.post("/predict", json={"records": []})).status_code == 422
                records[0]["is_churn"] = 1
                assert (await client.post("/predict", json={"records": records})).status_code == 422
    asyncio.run(scenario())
    frame.loc[frame.cutoff == frame.cutoff.min(), "label_end"] = pd.Timestamp("2016-04-01")
    with pytest.raises(ValueError, match="embargo"):
        train(frame, folder)


def test_missing_model(monkeypatch, tmp_path):
    monkeypatch.setenv("RETAINIQ_MODEL", str(tmp_path/"missing"))
    async def scenario():
        async with lifespan(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://retainiq.test", trust_env=False) as client:
                assert (await client.get("/health")).json()["status"] == "model_missing"
                assert (await client.post("/predict", json={"records": [{k: 0 for k in FEATURES}]})).status_code == 503
    asyncio.run(scenario())


def test_inference_contract_without_network(trained):
    from pydantic import ValidationError
    from fastapi import HTTPException
    from retainiq.api import Batch, score_records
    frame, report, folder = trained
    app.state.bundle = load_bundle(folder/"model.joblib")
    records = frame[FEATURES].iloc[:2].to_dict("records")
    response = score_records(Batch(records=records))
    assert response["probabilities"] == predict(app.state.bundle, records)
    assert response["label_method"] == "kkbox_reference_gap_v1"
    with pytest.raises(ValidationError):
        Batch(records=[{**records[0], "days_to_expiry": 31}])
    with pytest.raises(ValidationError):
        Batch(records=[{**records[0], "auto_renew": 2}])
    with pytest.raises(ValidationError):
        Batch(records=[{**records[0], "seconds_30d": float("nan")}])
    app.state.bundle = None
    with pytest.raises(HTTPException) as error:
        score_records(Batch(records=records))
    assert error.value.status_code == 503


def test_dashboard(trained, monkeypatch):
    _, _, folder = trained
    monkeypatch.setenv("RETAINIQ_ARTIFACTS", str(folder))
    from pathlib import Path
    dashboard = Path(__file__).parents[1]/"src"/"retainiq"/"dashboard.py"
    ui = AppTest.from_file(str(dashboard)).run(timeout=30)
    assert not ui.exception
    assert "SYNTHETIC" in ui.warning[0].value
    # 83 held-out users: top 10% in the evaluation includes 9, not 8.
    assert len(ui.dataframe[-1].value) == 9
    ui.slider[0].set_value(20).run()
    assert not ui.exception
    assert len(ui.dataframe[-1].value) == 17


def test_import_duplicate_and_rollback(tmp_path):
    raw = tmp_path/"raw"
    generate(raw, n=30)
    original = pd.read_csv(raw/"transactions.csv")
    original.iloc[:3].to_csv(raw/"transactions_v2.csv", index=False)
    db = tmp_path/"data.duckdb"
    manifest = ingest(raw, db, "synthetic", chunksize=11)
    assert manifest["tables"]["transactions"]["duplicates_removed"] == 3
    malformed = original.copy()
    malformed.loc[0, "transaction_date"] = 20161399
    malformed.to_csv(raw/"transactions.csv", index=False)
    with pytest.raises(ValueError):
        ingest(raw, db, "synthetic")
    with duckdb.connect(str(db)) as con:
        assert con.execute("SELECT count(*) FROM transactions").fetchone()[0] == len(original)
