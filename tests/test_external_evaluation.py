import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier

from retainiq.data import ingest
from retainiq.evaluation import evaluate_official
from retainiq.features import FEATURES


def test_supplied_labels_can_evaluate_without_future_transactions(tmp_path):
    raw = tmp_path/"raw"
    raw.mkdir()
    tx = pd.DataFrame({"msno": [f"u{i}" for i in range(50)], "transaction_date": 20160915,
        "membership_expire_date": 20161015, "is_cancel": 0,"is_auto_renew": 1,
        "actual_amount_paid": 149,"payment_plan_days": 30,"plan_list_price":149,"payment_method_id":41})
    tx.to_csv(raw/"transactions.csv",index=False)
    pd.DataFrame([["u0",20160920,100,2]],columns=["msno","date","total_secs","num_unq"]).to_csv(raw/"user_logs.csv",index=False)
    ingest(raw,tmp_path/"data.duckdb","synthetic")
    labels = pd.DataFrame({"msno":tx.msno,"is_churn":np.arange(50)%2})
    labels.to_csv(tmp_path/"labels.csv",index=False)
    model=DummyClassifier(strategy="prior").fit(pd.DataFrame(np.zeros((50,len(FEATURES))),columns=FEATURES),labels.is_churn)
    bundle={"model":model,"features":FEATURES,"model_name":"prevalence","provenance":"synthetic",
            "training_prevalence":.5,"training_cutoff":"2016-01-01","validation_cutoff":"2016-04-01",
            "test_cutoff":"2016-07-01","label_method":"kkbox_reference_gap_v1"}
    joblib.dump(bundle,tmp_path/"model.joblib")
    report=evaluate_official(tmp_path/"data.duckdb",tmp_path/"model.joblib",tmp_path/"labels.csv","2016-10-01","2016-10-31",tmp_path/"evaluation.json")
    assert report["matched_rows"]==50
    assert report["test"]["log_loss"]==pytest.approx(np.log(2))
    with pytest.raises(ValueError,match="follow"):
        evaluate_official(tmp_path/"data.duckdb",tmp_path/"model.joblib",tmp_path/"labels.csv","2016-07-01","2016-10-31",tmp_path/"bad.json")
