"""Public hosting entrypoint: synthetic records only, independent of real mode."""
import os
from pathlib import Path
import runpy
import sys

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/"src"))

import streamlit as st
from retainiq.public_demo import ensure_public_demo


@st.cache_resource(show_spinner=False)
def prepare_demo():
    return ensure_public_demo(ROOT/"artifacts"/"public-demo")


# Do not honor a real-data artifact path configured in the host environment.
os.environ["RETAINIQ_ARTIFACTS"] = str(prepare_demo())
runpy.run_path(str(ROOT/"src"/"retainiq"/"dashboard.py"), run_name="__main__")
