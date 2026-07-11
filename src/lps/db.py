import os
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def connect(dsn: str, autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(dsn, autocommit=autocommit)


def run_migrations(conn, migrations_dir: str = "db/migrations") -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        if not conn.autocommit:
            conn.commit()
        cur.execute("SELECT filename FROM schema_migrations")
        done = {r[0] for r in cur.fetchall()}

    applied = []
    for name in sorted(os.listdir(migrations_dir)):
        if not name.endswith(".sql") or name in done:
            continue
        with open(os.path.join(migrations_dir, name), "r", encoding="utf-8") as f:
            sql = f.read()
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (name,))
        if not conn.autocommit:
            conn.commit()
        applied.append(name)
    return applied


SCALAR_COLUMNS = [
    "linkedin_slug", "linkedin_url", "full_name", "first_name", "last_name",
    "headline", "location", "country", "current_company", "current_title",
    "connections", "followers", "email",
]


def get_person_by_slug(conn, slug: str) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM person WHERE linkedin_slug = %s", (slug,))
        return cur.fetchone()


def insert_person(conn, profile, *, needs_review, content_hash, norm_name, norm_company) -> str:
    vals = {c: getattr(profile, c) for c in SCALAR_COLUMNS}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO person (linkedin_slug, linkedin_url, full_name, first_name,
                last_name, headline, location, country, current_company, current_title,
                connections, followers, email, norm_name, norm_company, data, sources,
                source_hashes, needs_review)
            VALUES (%(linkedin_slug)s, %(linkedin_url)s, %(full_name)s, %(first_name)s,
                %(last_name)s, %(headline)s, %(location)s, %(country)s, %(current_company)s,
                %(current_title)s, %(connections)s, %(followers)s, %(email)s, %(norm_name)s,
                %(norm_company)s, %(data)s, %(sources)s, %(source_hashes)s, %(needs_review)s)
            RETURNING id
            """,
            {**vals, "norm_name": norm_name, "norm_company": norm_company,
             "data": Jsonb(profile.data), "sources": [profile.source],
             "source_hashes": Jsonb({profile.source: content_hash}),
             "needs_review": needs_review},
        )
        return str(cur.fetchone()[0])


def update_person(conn, person_id, *, scalars, data, sources, source_hashes) -> None:
    sets = ", ".join(f"{k} = %({k})s" for k in scalars)
    prefix = (sets + ", ") if sets else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE person SET {prefix}
                data = %(data)s, sources = %(sources)s, source_hashes = %(source_hashes)s,
                updated_at = now(), last_enriched_at = now()
            WHERE id = %(id)s
            """,
            {**scalars, "data": Jsonb(data), "sources": sources,
             "source_hashes": Jsonb(source_hashes), "id": person_id},
        )


def create_run(conn, source, params, apify_run_id=None, dataset_id=None) -> str:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO crawl_run (source, params, apify_run_id, dataset_id)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (source, Jsonb(params), apify_run_id, dataset_id),
        )
        rid = str(cur.fetchone()[0])
    conn.commit()
    return rid


def set_checkpoint(conn, run_id, offset) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE crawl_run SET checkpoint = %s WHERE id = %s",
                    (Jsonb({"offset": offset}), run_id))
    conn.commit()


def record_metric(conn, run_id, processed, inserted, enriched, errors, rate) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO run_metric (run_id, processed, inserted, enriched, errors, rate_per_sec)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (run_id, processed, inserted, enriched, errors, rate),
        )
    conn.commit()


def finish_run(conn, run_id, status, totals) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE crawl_run SET status = %s, fetched = %s, inserted = %s,
               enriched = %s, unchanged = %s, errors = %s, finished_at = now()
               WHERE id = %s""",
            (status, totals["fetched"], totals["inserted"], totals["enriched"],
             totals["unchanged"], totals["errors"], run_id),
        )
    conn.commit()


def get_run(conn, run_id) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM crawl_run WHERE id = %s", (run_id,))
        return cur.fetchone()
