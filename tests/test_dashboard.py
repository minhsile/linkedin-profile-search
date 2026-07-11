import os
import psycopg
from fastapi.testclient import TestClient


def test_stats_endpoint(monkeypatch):
    dsn = os.environ.get("TEST_DATABASE_URL", "postgresql://lps:lps@localhost:5433/lps_test")
    from lps.db import run_migrations
    with psycopg.connect(dsn, autocommit=True) as c:
        run_migrations(c)
    monkeypatch.setenv("DATABASE_URL", dsn)
    from dashboard.app import app
    client = TestClient(app)
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert "persons" in body and "needs_review" in body and "by_source" in body
