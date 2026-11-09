import json

import duckdb
import pandas as pd

FEATURES = ["days_to_expiry", "tenure_days", "transactions_90d", "paid_90d", "auto_renew", "active_days_30d", "seconds_30d", "unique_songs_30d"]


def _legacy_snapshot(database, cutoff, observation_end, labels=True):
    """At midnight cutoff, use only strictly earlier events. Horizon is expiry+30d."""
    cutoff, end = pd.Timestamp(cutoff), pd.Timestamp(observation_end)
    if cutoff >= end:
        raise ValueError("cutoff must precede observation_end")
    con = duckdb.connect(str(database), read_only=True)
    try:
        meta = json.loads(con.execute("SELECT payload FROM metadata").fetchone()[0])
        has_invalid = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='invalid_logs'").fetchone()[0] > 0
        quality_exclusion = "UNION SELECT msno FROM invalid_logs WHERE date < $cutoff" if has_invalid else ""
        # Exclude subscribers with any same-day revision in available history. Conservative
        # research cohort; this is selection bias and must be reported, not hidden.
        query = f"""
        WITH ambiguous AS (
          SELECT msno FROM transactions WHERE transaction_date < $cutoff GROUP BY msno,transaction_date HAVING count(*)>1
          UNION SELECT msno FROM user_logs WHERE date < $cutoff GROUP BY msno,date HAVING count(*)>1
          {quality_exclusion}
        ), history AS (
          SELECT * FROM transactions WHERE transaction_date < $cutoff
          AND msno NOT IN (SELECT msno FROM ambiguous)
        ), latest AS (
          SELECT *, row_number() OVER(PARTITION BY msno ORDER BY transaction_date DESC) rn FROM history
        ), cohort AS (
          SELECT msno, membership_expire_date expiry, is_auto_renew auto_renew
          FROM latest WHERE rn=1 AND is_cancel=0 AND membership_expire_date >= $cutoff
          AND membership_expire_date < $cutoff + INTERVAL 30 DAY
        ), tx AS (
          SELECT msno, date_diff('day', min(transaction_date), $cutoff) tenure_days,
          count(*) FILTER(WHERE transaction_date >= $cutoff - INTERVAL 90 DAY) transactions_90d,
          sum(actual_amount_paid) FILTER(WHERE transaction_date >= $cutoff - INTERVAL 90 DAY) paid_90d
          FROM history GROUP BY msno
        ), logs AS (
          SELECT msno, count(*) active_days_30d, sum(total_secs) seconds_30d,
          sum(num_unq) unique_songs_30d FROM user_logs
          WHERE date >= $cutoff - INTERVAL 30 DAY AND date < $cutoff GROUP BY msno
        )
        SELECT c.msno,c.expiry,date_diff('day',$cutoff,c.expiry) days_to_expiry,
          tx.tenure_days,tx.transactions_90d,coalesce(tx.paid_90d,0) paid_90d,c.auto_renew,
          coalesce(l.active_days_30d,0) active_days_30d,coalesce(l.seconds_30d,0) seconds_30d,
          coalesce(l.unique_songs_30d,0) unique_songs_30d
        FROM cohort c JOIN tx USING(msno) LEFT JOIN logs l USING(msno)
        """
        frame = con.execute(query, {"cutoff": cutoff.to_pydatetime()}).df()
        frame["cutoff"] = cutoff
        frame["label_end"] = frame.expiry + pd.Timedelta(days=30)
        if labels:
            frame = frame.loc[frame.label_end <= end].copy()
            con.register("cohort_frame", frame)
            outcomes = con.execute("""
              SELECT c.msno, CAST(NOT EXISTS (
                SELECT 1 FROM transactions t WHERE t.msno=c.msno
                AND t.transaction_date >= c.cutoff AND t.transaction_date <= c.label_end
                AND t.is_cancel=0 AND t.actual_amount_paid>=0
                AND t.membership_expire_date>c.expiry
              ) AS INTEGER) is_churn FROM cohort_frame c
            """).df()
            frame = frame.merge(outcomes, on="msno", validate="one_to_one")
        frame["provenance"] = meta["provenance"]
        frame["label_method"] = "legacy_extension_proxy"
        return frame.sort_values("msno").reset_index(drop=True)
    finally:
        con.close()


def snapshot(database, cutoff, observation_end, labels=True, label_method="reference"):
    if label_method == "legacy":
        return _legacy_snapshot(database, cutoff, observation_end, labels=labels)
    if label_method != "reference":
        raise ValueError("Unknown label method")
    from retainiq.labels import ensure_reference_columns, reference_ctes, LABEL_METHOD, validate_reference_dates
    cutoff, end = validate_reference_dates(cutoff, observation_end)
    with duckdb.connect(str(database), read_only=True) as con:
        ensure_reference_columns(con)
        meta = json.loads(con.execute("SELECT payload FROM metadata").fetchone()[0])
        has_invalid = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='invalid_logs'").fetchone()[0] > 0
        quality = "UNION SELECT msno FROM invalid_logs WHERE date < $cutoff" if has_invalid else ""
        cohort = "reference_labels" if labels else "candidates"
        target = ", c.is_churn" if labels else ""
        query = "WITH " + reference_ctes() + f""",
        excluded AS (
          SELECT msno FROM user_logs WHERE date < $cutoff GROUP BY msno,date HAVING count(*)>1
          {quality}
        ), tx AS (
          SELECT msno,date_diff('day',min(transaction_date),$cutoff) tenure_days,
            count(*) FILTER(WHERE transaction_date >= $cutoff-INTERVAL 90 DAY) transactions_90d,
            sum(actual_amount_paid) FILTER(WHERE transaction_date >= $cutoff-INTERVAL 90 DAY) paid_90d
          FROM transactions WHERE transaction_date < $cutoff GROUP BY msno
        ), logs AS (
          SELECT msno,count(*) active_days_30d,sum(total_secs) seconds_30d,sum(num_unq) unique_songs_30d
          FROM user_logs WHERE date >= $cutoff-INTERVAL 30 DAY AND date < $cutoff GROUP BY msno
        )
        SELECT c.msno,c.expiry,date_diff('day',$cutoff,c.expiry) days_to_expiry,
          tx.tenure_days,tx.transactions_90d,coalesce(tx.paid_90d,0) paid_90d,m.auto_renew,
          coalesce(l.active_days_30d,0) active_days_30d,coalesce(l.seconds_30d,0) seconds_30d,
          coalesce(l.unique_songs_30d,0) unique_songs_30d,c.expiry+INTERVAL 30 DAY label_end
          {target}
        FROM {cohort} c JOIN candidates m USING(msno) JOIN tx USING(msno) LEFT JOIN logs l USING(msno)
        WHERE c.msno NOT IN (SELECT msno FROM excluded) ORDER BY c.msno
        """
        frame = con.execute(query, {"cutoff": cutoff.to_pydatetime(), "observation_end": end.to_pydatetime()}).df()
        frame["cutoff"] = cutoff
        frame["provenance"] = meta["provenance"]
        frame["label_method"] = LABEL_METHOD
        return frame
