from lps.db import run_migrations


def test_run_migrations_creates_tables(admin_conn):
    applied = run_migrations(admin_conn)
    assert "001_init.sql" in applied
    with admin_conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.person')")
        assert cur.fetchone()[0] == "person"


def test_run_migrations_is_idempotent(admin_conn):
    run_migrations(admin_conn)
    applied_again = run_migrations(admin_conn)
    assert applied_again == []
