import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
import threading
import time
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from . import etl, kpis

logging.basicConfig(level=logging.INFO)
INTERVAL = int(os.getenv("ETL_INTERVAL_SECONDS", "0"))  # 0 = solo manual
_lock = threading.Lock()


def run_once():
    with _lock:  # nunca dos cargas a la vez
        return etl.run()


def _loop():
    time.sleep(10)  # deja que los sistemas creen sus tablas
    while True:
        run_once()
        time.sleep(INTERVAL)


@asynccontextmanager
async def lifespan(app):
    if INTERVAL > 0:
        threading.Thread(target=_loop, daemon=True, name="etl-loop").start()
    yield

app = FastAPI(title="RetailNova ETL y panel gerencial", version="0.3.0", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"status": "ok", "service": "etl", "interval_s": INTERVAL}


@app.post("/api/run")
def run_now():
    return run_once()


@app.get("/api/kpis")
def get_kpis():
    etl.md.create_all(etl.engines()["dw"])
    return kpis.compute()
