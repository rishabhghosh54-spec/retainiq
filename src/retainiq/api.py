from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from retainiq.model import load_bundle, predict


class Features(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    days_to_expiry: float = Field(ge=0, le=30)
    tenure_days: float = Field(ge=0)
    transactions_90d: int = Field(ge=0)
    paid_90d: float = Field(ge=0)
    auto_renew: int = Field(ge=0, le=1)
    active_days_30d: int = Field(ge=0, le=30)
    seconds_30d: float = Field(ge=0)
    unique_songs_30d: float = Field(ge=0)


class Batch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    records: list[Features] = Field(min_length=1, max_length=1000)


@asynccontextmanager
async def lifespan(app):
    path = Path(os.getenv("RETAINIQ_MODEL", "artifacts/demo/model.joblib"))
    app.state.bundle = load_bundle(path) if path.is_file() else None
    yield


app = FastAPI(title="RetainIQ", version="0.2.0", lifespan=lifespan)


@app.get("/health")
async def health():
    bundle = getattr(app.state, "bundle", None)
    return {"status": "ready" if bundle else "model_missing", "provenance": bundle["provenance"] if bundle else None}


def score_records(batch: Batch):
    bundle = getattr(app.state, "bundle", None)
    if bundle is None:
        raise HTTPException(503, "Train a model and configure RETAINIQ_MODEL")
    return {"probabilities": predict(bundle, [r.model_dump() for r in batch.records]),
            "model": bundle["model_name"], "provenance": bundle["provenance"],
            "label_method": bundle.get("label_method", "legacy_extension_proxy"),
            "release_status": bundle.get("release_status", "research"),
            "meaning": "Risk of the model's documented renewal outcome; not an individual treatment effect"}


@app.post("/predict")
async def score(batch: Batch):
    return score_records(batch)
