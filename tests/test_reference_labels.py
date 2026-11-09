import duckdb
import pandas as pd
import pytest

from retainiq.data import normalize
from retainiq.labels import ordered_events, reference_labels, renewal_gap, validate_reference_dates


def event(date, expiry, cancel=0, price=149, plan=30, method=41, user="a"):
    return {"msno": user, "transaction_date": date, "membership_expire_date": expiry,
            "is_cancel": cancel, "plan_list_price": price, "payment_plan_days": plan,
            "payment_method_id": method, "is_auto_renew": 1, "actual_amount_paid": price}


@pytest.mark.parametrize("future,expected", [
    ([], 1),
    ([event("20170311", "20170401")], 0),  # 29 days after Feb 10
    ([event("20170312", "20170401")], 1),  # exactly 30: churn
    ([event("20170313", "20170401")], 1),
    ([event("20170201", "20170301")], 0),  # early renewal
    ([event("20170202", "20170101", 1), event("20170203", "20170315")], 1),
    ([event("20170202", "20170315"), event("20170203", "20170101", 1)], 0),
    ([event("20170202", "20170101", 1)], 1),
    ([event("20170203", "20170101", 1), event("20170203", "20170315")], 0),  # same plan: renew before cancel
    ([event("20170203", "20170101", 1, price=200), event("20170203", "20170315")], 1),
    ([event("20170203", "20170101", 1, price=10), event("20170203", "20170315", price=9)], 0),  # lexical signature, not numeric price
    ([event("20170202", "20170120", 1), event("20170202", "20170101", 1), event("20170205", "20170315")], 1),
])
def test_sql_labels_against_independent_oracle(future, expected):
    history = event("20170110", "20170210")
    frame = normalize(pd.DataFrame([history]+future), "transactions")
    with duckdb.connect() as con:
        con.register("input_events", frame)
        con.execute("CREATE TABLE transactions AS SELECT * FROM input_events")
        result = reference_labels(con, "2017-02-01", "2017-03-31")
    oracle_events = normalize(pd.DataFrame(future or [history]), "transactions").to_dict("records") if future else []
    gap = renewal_gap(oracle_events, "2017-02-10")
    assert int(gap is None or gap >= 30) == expected
    assert result.is_churn.tolist() == [expected]


def test_reference_monthly_cohort_and_expiry_order():
    rows = [
        event("20161215", "20170210", user="no_january_transaction"),
        event("20170115", "20170228", user="renew"),
        event("20170115", "20170201", user="renew"),
        event("20170115", "20170228", 1, user="cancel"),
        event("20170115", "20170210", 1, user="cancel"),
        event("20170115", "20170301", user="march_expiry"),
    ]
    with duckdb.connect() as con:
        con.register("inputs", normalize(pd.DataFrame(rows), "transactions"))
        con.execute("CREATE TABLE transactions AS SELECT * FROM inputs")
        result = reference_labels(con, "2017-02-01", "2017-03-31").set_index("msno")
    assert set(result.index) == {"renew", "cancel"}
    assert result.loc["renew", "expiry"] == pd.Timestamp("2017-02-28")
    assert result.loc["cancel", "expiry"] == pd.Timestamp("2017-02-10")


def test_uniform_censoring_even_if_early_renewal():
    rows = [event("20170110", "20170228"), event("20170201", "20170401")]
    with duckdb.connect() as con:
        con.register("inputs", normalize(pd.DataFrame(rows), "transactions"))
        con.execute("CREATE TABLE transactions AS SELECT * FROM inputs")
        assert reference_labels(con, "2017-02-01", "2017-03-15").empty


@pytest.mark.parametrize("cutoff", ["2017-02-02", "2017-02-01T12:00:00", "2017-02-01T00:00:00Z", "NaT"])
def test_day_level_cutoff_contract(cutoff):
    with pytest.raises(ValueError):
        validate_reference_dates(cutoff,"2017-03-31")
