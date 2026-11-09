"""KKBOX reference-style monthly cohorts and cancellation-aware renewal labels.

Independent Python oracle and vectorized SQL implement the supplied Scala
WSDMChurnLabeller's ordering and gap rule. They do not invent event timestamps.
"""
import pandas as pd

LABEL_METHOD = "kkbox_reference_gap_v1"


def validate_reference_dates(cutoff, observation_end):
    cutoff, end = pd.Timestamp(cutoff), pd.Timestamp(observation_end)
    if pd.isna(cutoff) or pd.isna(end) or cutoff.tzinfo is not None or end.tzinfo is not None:
        raise ValueError("Use finite timezone-free calendar dates for the day-granularity dataset")
    if cutoff != cutoff.normalize() or end != end.normalize() or cutoff.day != 1 or end <= cutoff:
        raise ValueError("Reference cutoff must be midnight on a month start before the observation end date")
    return cutoff, end


def ordered_events(events):
    """Independent small-fixture oracle matching the reference's string comparator."""
    def key(row):
        return (pd.Timestamp(row["transaction_date"]),)
    # Stable successive sorts express mixed ascending/descending directions.
    rows = [dict(row) for row in events]
    rows.sort(key=lambda r: (-pd.Timestamp(r["membership_expire_date"]).toordinal()
                            if int(r["is_cancel"]) else pd.Timestamp(r["membership_expire_date"]).toordinal()))
    rows.sort(key=lambda r: int(r["is_cancel"]))
    rows.sort(key=lambda r: "".join(str(int(r[k])) for k in ["plan_list_price", "payment_plan_days", "payment_method_id"]), reverse=True)
    rows.sort(key=key)
    return rows


def renewal_gap(events, expiry):
    """Reference: cancellations shorten expiry until the first noncancel event."""
    effective = pd.Timestamp(expiry)
    for row in ordered_events(events):
        if int(row["is_cancel"]):
            effective = min(effective, pd.Timestamp(row["membership_expire_date"]))
        else:
            return (pd.Timestamp(row["transaction_date"]) - effective).days
    return None


def python_labels(transactions, cutoff, observation_end):
    """Slow independent oracle for audits, not the production feature pipeline."""
    cutoff, end = pd.Timestamp(cutoff), pd.Timestamp(observation_end)
    past = transactions.loc[(transactions.transaction_date >= cutoff-pd.DateOffset(months=1)) & (transactions.transaction_date < cutoff)]
    future = {u: g.to_dict("records") for u, g in transactions.loc[(transactions.transaction_date >= cutoff) & (transactions.transaction_date <= end)].groupby("msno")}
    rows = []
    for user, group in past.groupby("msno"):
        expiry = pd.Timestamp(ordered_events(group.to_dict("records"))[-1]["membership_expire_date"])
        if not cutoff <= expiry < cutoff+pd.DateOffset(months=1) or expiry+pd.Timedelta(days=30)>end:
            continue
        gap = renewal_gap(future.get(user, []), expiry)
        rows.append({"msno": user, "expiry": expiry, "is_churn": int(gap is None or gap>=30)})
    return pd.DataFrame(rows, columns=["msno", "expiry", "is_churn"]).sort_values("msno").reset_index(drop=True)


ORDER_FORWARD = "transaction_date ASC, signature DESC, is_cancel ASC, expiry_order ASC"
ORDER_REVERSE = "transaction_date DESC, signature ASC, is_cancel DESC, expiry_order DESC"


def reference_ctes():
    return f"""
    events AS (
      SELECT *, concat(CAST(CAST(plan_list_price AS BIGINT) AS VARCHAR),
        CAST(CAST(payment_plan_days AS BIGINT) AS VARCHAR),
        CAST(CAST(payment_method_id AS BIGINT) AS VARCHAR)) signature,
        CASE WHEN is_cancel=1 THEN -date_diff('day',DATE '1970-01-01',membership_expire_date)
          ELSE date_diff('day',DATE '1970-01-01',membership_expire_date) END expiry_order
      FROM transactions
    ), monthly_history AS (
      SELECT *,row_number() OVER(PARTITION BY msno ORDER BY {ORDER_REVERSE}, is_auto_renew ASC,actual_amount_paid ASC) rn
      FROM events WHERE transaction_date >= $cutoff - INTERVAL 1 MONTH AND transaction_date < $cutoff
    ), candidates AS (
      SELECT msno,membership_expire_date expiry,is_auto_renew auto_renew
      FROM monthly_history WHERE rn=1 AND membership_expire_date >= $cutoff
        AND membership_expire_date < $cutoff + INTERVAL 1 MONTH
    ), matured AS (
      SELECT *, expiry + INTERVAL 30 DAY label_end FROM candidates
      WHERE expiry + INTERVAL 30 DAY <= $observation_end
    ), future_ordered AS (
      SELECT e.*,row_number() OVER(PARTITION BY e.msno ORDER BY {ORDER_FORWARD}) event_index
      FROM events e JOIN matured m USING(msno)
      WHERE transaction_date >= $cutoff AND transaction_date <= m.label_end
    ), first_renewal AS (
      SELECT msno,min(event_index) FILTER(WHERE is_cancel=0) renewal_index
      FROM future_ordered GROUP BY msno
    ), outcome_state AS (
      SELECT m.msno,m.expiry,m.label_end,
        min(f.transaction_date) FILTER(WHERE f.event_index=r.renewal_index) renewal_date,
        least(m.expiry,min(f.membership_expire_date) FILTER(
          WHERE f.is_cancel=1 AND (r.renewal_index IS NULL OR f.event_index<r.renewal_index))) effective_expiry
      FROM matured m LEFT JOIN first_renewal r USING(msno) LEFT JOIN future_ordered f ON f.msno=m.msno
      GROUP BY m.msno,m.expiry,m.label_end
    ), reference_labels AS (
      SELECT msno,expiry,label_end,date_diff('day',effective_expiry,renewal_date) renewal_gap_days,
        CAST(renewal_date IS NULL OR date_diff('day',effective_expiry,renewal_date)>=30 AS INTEGER) is_churn
      FROM outcome_state
    )
    """


def ensure_reference_columns(con):
    cols = set(con.execute("DESCRIBE transactions").df().column_name)
    if not {"payment_method_id", "plan_list_price"} <= cols:
        raise ValueError("Reference labels require payment_method_id and plan_list_price. Re-ingest source transactions; old database discarded these fields.")


def reference_labels(con, cutoff, observation_end):
    cutoff, end = validate_reference_dates(cutoff, observation_end)
    ensure_reference_columns(con)
    return con.execute("WITH " + reference_ctes() + " SELECT * FROM reference_labels ORDER BY msno",
        {"cutoff": cutoff.to_pydatetime(), "observation_end": end.to_pydatetime()}).df()
