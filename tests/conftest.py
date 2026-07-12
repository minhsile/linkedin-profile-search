import os
import pytest
import psycopg

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://lps:lps@localhost:5433/lps_test"
)


def _ensure_test_db():
    admin = "postgresql://lps:lps@localhost:5433/lps"
    with psycopg.connect(admin, autocommit=True) as c:
        with c.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = 'lps_test'")
            if cur.fetchone() is None:
                cur.execute("CREATE DATABASE lps_test")


@pytest.fixture(scope="session", autouse=True)
def _bootstrap():
    _ensure_test_db()


@pytest.fixture
def admin_conn():
    conn = psycopg.connect(TEST_DSN, autocommit=True)
    with conn.cursor() as cur:
        cur.execute(
            "DROP TABLE IF EXISTS crawl_run, person, schema_migrations CASCADE"
        )
    yield conn
    conn.close()


@pytest.fixture
def conn(admin_conn):
    from lps.db import run_migrations
    run_migrations(admin_conn)
    tx = psycopg.connect(TEST_DSN)
    yield tx
    tx.rollback()
    tx.close()
