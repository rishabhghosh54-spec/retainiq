from pathlib import Path

import pandas as pd

from retainiq.data import ingest
from retainiq.demo import generate
from retainiq.sample import sample_sources


def test_sampling_preserves_whole_histories_and_manifest(tmp_path):
    raw, sample = tmp_path/"raw", tmp_path/"sample"
    generate(raw, n=50)
    report = sample_sources(raw, sample, 500, 1000)
    assert len(report["files"]) == 2
    for name in ["transactions.csv", "user_logs.csv"]:
        original = pd.read_csv(raw/name)
        selected = pd.read_csv(sample/name)
        expected = original.loc[original.msno.isin(selected.msno)]
        pd.testing.assert_frame_equal(selected.reset_index(drop=True), expected.reset_index(drop=True))
    tx_users = set(pd.read_csv(sample/"transactions.csv").msno)
    log_users = set(pd.read_csv(sample/"user_logs.csv").msno)
    assert tx_users == log_users
    manifest = ingest(sample, tmp_path/"sample.duckdb")
    assert manifest["provenance"] == "kkbox_subscriber_sample"
    assert manifest["sampling"]["sampling"]["expected_fraction"] == .5
