# RetainIQ data card

Source: the user's downloaded [KKBOX competition files](https://www.kaggle.com/competitions/kkbox-churn-prediction-challenge/data), inspected on 2026-11-09. This is historical music-subscription data; transfer to SaaS or FinTech requires new validation. Competition access does not imply raw-data redistribution permission.

## Source coverage

Original transactions: 21,547,746 rows, 2015-01-01–2017-02-28. Refresh transactions: 1,431,009 rows, including historical backfills and March 2017. Original logs: 392,106,543 rows through 2017-02-28; refresh logs: 18,396,362 March rows. Combined daily coverage has no missing calendar days, but that cannot prove every user's history complete. Source SHA-256 hashes and daily counts are retained. Archives passed extraction integrity checks; originals in Downloads were unchanged.

Modeling uses `md5_number_lower(msno) % 1000 < 5` on transaction subscribers, with all available history for those users. The same subscriber set selects listening rows by an enforced small-side semi-join. There are 11,944 selected transaction subscribers and 9,571 with listening rows. Sampling is independent of outcome and dates. A completed manifest is required before ingestion; interrupted samples are rejected. Full raw scans and the full transaction label audit must not be confused with full-population model training.

## Validation

Transactions require msno, transaction_date, membership_expire_date, is_cancel, is_auto_renew, actual_amount_paid and payment_plan_days. Reference labeling additionally requires plan_list_price and payment_method_id, which older database versions discarded. Re-ingest instead of inventing these fields. Required values are nonnull, dates valid YYYYMMDD, numerics finite/nonnegative, flags binary, ordering fields integer. Full transaction audit separately validates every source numeric/key field before casting. Exact duplicates are removed; the full audit retains 22,975,416 distinct rows from 22,978,755 source rows.

Listening requires msno, date, total_secs and num_unq. Strict mode rejects negative or >=1e12-second durations. Opt-in quarantine preserves values and reasons in `invalid_logs`; the sampled run contains 252 negative and two positive sentinel-scale rows affecting 153 subscribers. Exclusion is strictly pre-cutoff. Less extreme positive values remain unaltered and need further investigation. Original rows are never silently clipped or replaced. Missing listening is zero-filled for modeling, not asserted to be inactivity.

Ingestion is transactional. Malformed inputs cause rollback. File hashes, row counts, ranges, duplicate counts, conflicts, sampling and quality policy are in the database manifest. Same-day transactions are ordered by the supplied reference comparator rather than excluding all such users. Same-day conflicting listening rows remain a pre-cutoff exclusion. Exact transaction ordering ties use a deterministic feature convention; they do not reveal an actual timestamp.

## Targets and source uncertainty

The Python and SQL ports of `WSDMChurnLabeller.scala` agree on all 4,186 sampled February candidates, including expiries. On the full transaction source, 856,085 candidates intersect supplied February labels; 10,525 outcomes differ (98.7706% agreement). This residual is reported, not repaired to force agreement. Independent reference fidelity is evidence about implementation, not proof that provided label files use identical source revisions/rules.

Reference March outcomes cannot all mature by 2017-03-31. Supplied March labels can nevertheless be evaluated as external ground truth with pre-March features, without pretending to reconstruct missing April events. Their validity is inherited from the supplied file, not independently established from available transactions.

No arrival timestamps are supplied. Historical features obey event dates, but refresh backfills and unknown observation completeness limit production point-in-time claims. Demographic snapshots are excluded because their historical state is unverified. Raw IDs, model binaries, features and scores remain local and ignored by Git; only aggregate evidence is distributed.
