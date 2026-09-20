"""FastAPI server: serves the dashboard and a small JSON API. Run with `surfaced serve`."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .models import Product
from .pipeline import NoEnginesError, load_state, run_pipeline

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "ui" / "index.html"
DATA = os.getenv("SURFACED_DATA", "data")
PRODUCT_FILE = Path(os.getenv("SURFACED_PRODUCT", "product.yaml"))

app = FastAPI(title="Surfaced", version="0.1.0")


class RunRequest(BaseModel):
    demo: bool = False
    steps: list[str] = ["score", "optimize", "content"]
    render: bool = False


@app.get("/")
def index() -> FileResponse:
    return FileResponse(UI)


@app.get("/api/state")
def state() -> JSONResponse:
    s = load_state(DATA)
    if not s:
        raise HTTPException(404, "No results yet. POST /api/run or run `surfaced run product.yaml --demo`.")
    return JSONResponse(s)


@app.post("/api/run")
def run(req: RunRequest) -> JSONResponse:
    path = PRODUCT_FILE if PRODUCT_FILE.exists() else ROOT / "examples" / "product.yaml"
    try:
        s = run_pipeline(Product.from_yaml(path), demo=req.demo, data_dir=DATA, steps=tuple(req.steps),
                         render=req.render, log=lambda *_: None)
    except NoEnginesError as e:
        raise HTTPException(400, str(e)) from e
    return JSONResponse(s)
