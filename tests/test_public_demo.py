import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from retainiq.public_demo import ensure_public_demo


def test_public_demo_refuses_real_reports(tmp_path):
    report = tmp_path/"report.json"
    original = json.dumps({"provenance": "kkbox_subscriber_sample"})
    report.write_text(original)
    with pytest.raises(ValueError, match="non-synthetic"):
        ensure_public_demo(tmp_path)
    assert report.read_text() == original


def test_public_entry_ignores_real_artifact_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("RETAINIQ_ARTIFACTS", str(tmp_path/"private-artifacts"))
    root = Path(__file__).parents[1]
    ui = AppTest.from_file(str(root/"streamlit_app.py")).run(timeout=60)
    assert not ui.exception
    assert "SYNTHETIC" in ui.warning[0].value
    report = json.loads((root/"artifacts/public-demo/report.json").read_text())
    assert report["provenance"] == "synthetic"
    scored = pd.read_parquet(root/"artifacts/public-demo/scored.parquet")
    assert scored.msno.str.startswith("synthetic-").all()
