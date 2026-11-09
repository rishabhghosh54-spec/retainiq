import pandas as pd
import pytest

from retainiq.data import ingest
from retainiq.features import snapshot


def test_negative_duration_is_explicit_and_point_in_time(tmp_path):
    raw = tmp_path/"raw"
    raw.mkdir()
    tx = pd.DataFrame([["a", 20170215, 20170310, 0, 1, 149, 30], ["b", 20170215, 20170310, 0, 1, 149, 30], ["a", 20170301, 20170405, 0, 1, 149, 30], ["b", 20170301, 20170405, 0, 1, 149, 30]], columns=["msno", "transaction_date", "membership_expire_date", "is_cancel", "is_auto_renew", "actual_amount_paid", "payment_plan_days"])
    tx["plan_list_price"] = 149
    tx["payment_method_id"] = 41
    tx.to_csv(raw/"transactions.csv", index=False)
    pd.DataFrame([["a", 20170315, -9223372036854130, 4], ["b", 20170315, 100, 2]], columns=["msno", "date", "total_secs", "num_unq"]).to_csv(raw/"user_logs.csv", index=False)
    database = tmp_path/"quality.duckdb"
    with pytest.raises(ValueError, match="negative"):
        ingest(raw, database)
    manifest = ingest(raw, database, quarantine_negative_logs=True)
    assert manifest["quality"]["negative_listening_rows_quarantined"] == 1
    assert manifest["quality"]["affected_subscribers_all_dates"] == 1
    before = snapshot(database, "2017-03-12", "2017-05-31", labels=False, label_method="legacy")
    after = snapshot(database, "2017-03-20", "2017-05-31", labels=False, label_method="legacy")
    assert set(before.msno) == {"a", "b"}
    assert set(after.msno) == {"b"}
    assert set(snapshot(database, "2017-03-01", "2017-05-31", labels=False).msno) == {"a", "b"}
    assert set(snapshot(database, "2017-04-01", "2017-05-31", labels=False).msno) == {"b"}
    logs = pd.read_csv(raw/"user_logs.csv")
    logs.loc[logs.msno == "a", "total_secs"] = 9223372036854776
    logs.to_csv(raw/"user_logs.csv", index=False)
    with pytest.raises(ValueError, match="overflow-scale"):
        ingest(raw, database)
    positive = ingest(raw, database, quarantine_negative_logs=True)
    assert positive["quality"]["negative_listening_rows_quarantined"] == 0
    assert positive["quality"]["overflow_scale_positive_rows_quarantined"] == 1
    assert set(snapshot(database, "2017-03-20", "2017-05-31", labels=False, label_method="legacy").msno) == {"b"}
