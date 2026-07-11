import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from lps.db import connect

# nạp .env ở gốc repo để có DATABASE_URL khi chạy uvicorn (không override env đã set sẵn)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = FastAPI(title="LPS Dashboard")
STATIC = Path(__file__).parent / "static"


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL chưa được set (tạo .env từ .env.example)")
    return dsn


@app.get("/api/stats")
def stats():
    with connect(_dsn()) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT count(*) AS persons, "
                    "count(*) FILTER (WHERE needs_review) AS needs_review FROM person")
        base = cur.fetchone()
        cur.execute("SELECT unnest(sources) AS source, count(*) AS n "
                    "FROM person GROUP BY 1 ORDER BY 2 DESC")
        by_source = {r["source"]: r["n"] for r in cur.fetchall()}
    return {"persons": base["persons"], "needs_review": base["needs_review"],
            "by_source": by_source}


@app.get("/api/runs")
def runs():
    with connect(_dsn()) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, source, status, fetched, inserted, enriched, unchanged, "
                    "errors, started_at, finished_at FROM crawl_run "
                    "ORDER BY started_at DESC LIMIT 50")
        return [dict(r, id=str(r["id"]),
                     started_at=r["started_at"].isoformat() if r["started_at"] else None,
                     finished_at=r["finished_at"].isoformat() if r["finished_at"] else None)
                for r in cur.fetchall()]


@app.get("/api/runs/{run_id}/metrics")
def run_metrics(run_id: str):
    with connect(_dsn()) as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT ts, processed, inserted, enriched, errors, rate_per_sec "
                    "FROM run_metric WHERE run_id = %s ORDER BY ts", (run_id,))
        return [dict(r, ts=r["ts"].isoformat()) for r in cur.fetchall()]


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
