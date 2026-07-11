# LinkedIn Profile Crawl Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crawl LinkedIn profiles from Apify (`harvestapi/linkedin-profile-search`) by filters into Postgres, deduped by normalized slug (enrich, never duplicate), with a resumable job runner, throughput metrics, and a local FastAPI + Chart.js dashboard.

**Architecture:** A source adapter turns raw Apify items into a canonical profile; an ingest engine matches on a normalized LinkedIn slug and either inserts a new row or deep-merges into the existing one (idempotent via per-source content hash); a job runner orchestrates a tracked, resumable run and samples throughput into a metrics table; a small FastAPI app reads those tables for a dashboard.

**Tech Stack:** Python 3.12 (conda env), Postgres 16 (Docker), psycopg 3, pydantic 2, FastAPI + uvicorn, apify-client, pytest.

## Global Constraints

- Python **3.12** (create via conda; system python is 3.8 — do not use it).
- Postgres **16** in Docker via `docker-compose.yml`; connect with a single `DATABASE_URL`.
- **Single profile data table** `person` (all detail in a JSONB `data` column) + two ops tables `crawl_run`, `run_metric`. No normalized child tables.
- Dedup key = **normalized LinkedIn slug**, `UNIQUE`. No fuzzy matching (keep `norm_name`/`norm_company` columns unused for future).
- No-slug records: **insert with `needs_review = true`**, never dropped.
- Enrich policy: **fill missing only** (never overwrite a non-empty value with empty); deep-merge JSONB arrays with dedup by natural key.
- Idempotent: re-processing a payload already seen (per-source `content_hash`) is a no-op (`unchanged`).
- Email is an **optional** nullable column; not crawled yet.
- All secrets in `.env` (never committed). All tools local; no third-party API keys beyond the Apify token.
- TDD: every behavior gets a failing test first. Frequent commits.

---

## File Structure

- `docker-compose.yml` — Postgres 16 service + volume.
- `.env.example` — `DATABASE_URL`, `APIFY_TOKEN`.
- `requirements.txt` — pinned deps.
- `config.example.json` — harvestapi search filters template.
- `db/migrations/001_init.sql` — schema.
- `src/lps/__init__.py`
- `src/lps/settings.py` — load env/config.
- `src/lps/normalize.py` — `normalize_slug`, `normalize_text`, `content_hash`.
- `src/lps/models.py` — `CanonicalProfile` (pydantic).
- `src/lps/sources/base.py` — `SourceAdapter` protocol.
- `src/lps/sources/harvestapi.py` — Apify harvestapi adapter (`start_run`, `iter_items`, `normalize`).
- `src/lps/db.py` — connection + person/run/metric SQL helpers.
- `src/lps/ingest.py` — `deep_merge_data`, `ingest_profile`.
- `src/lps/runner.py` — `run_crawl`.
- `src/lps/cli.py` — `migrate` / `crawl` / `status`.
- `dashboard/app.py` — FastAPI (`/`, `/api/stats`, `/api/runs`, `/api/runs/{id}/metrics`).
- `dashboard/static/index.html` — Chart.js dashboard page.
- `dashboard/static/vendor/chart.umd.js` — vendored Chart.js (offline).
- `tests/conftest.py` — test DB connection fixture (transaction rollback).
- `tests/test_*.py` — one per module.

---

### Task 1: Project scaffolding + Docker Postgres

**Files:**
- Create: `docker-compose.yml`, `.env.example`, `requirements.txt`, `config.example.json`
- Create: `src/lps/__init__.py`, `src/lps/settings.py`
- Modify: `.gitignore` (already ignores `.env`, `output/`)
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `lps.settings.load_settings() -> Settings` where `Settings` has `.database_url: str` and `.apify_token: str | None`; `lps.settings.load_search_config(path: str) -> dict`.

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    container_name: lps_pg
    environment:
      POSTGRES_USER: lps
      POSTGRES_PASSWORD: lps
      POSTGRES_DB: lps
    ports:
      - "5433:5432"
    volumes:
      - lps_pgdata:/var/lib/postgresql/data
volumes:
  lps_pgdata:
```

- [ ] **Step 2: Create `.env.example`**

```bash
# copy to .env and fill in
DATABASE_URL=postgresql://lps:lps@localhost:5433/lps
APIFY_TOKEN=apify_api_xxx
```

- [ ] **Step 3: Create `requirements.txt`**

```
apify-client==1.7.1
psycopg[binary]==3.2.1
pydantic==2.8.2
fastapi==0.111.1
uvicorn==0.30.3
python-dotenv==1.0.1
pytest==8.3.2
```

- [ ] **Step 4: Create `config.example.json`**

```json
{
  "profileScraperMode": "Full",
  "searchQuery": "Marketing Manager",
  "currentJobTitles": ["Marketing Manager"],
  "locations": ["Ho Chi Minh City"],
  "currentCompanies": [],
  "industryIds": [],
  "maxItems": 50,
  "startPage": 1
}
```

- [ ] **Step 5: Create `src/lps/__init__.py`** (empty file)

- [ ] **Step 6: Write the failing test** — `tests/test_settings.py`

```python
import json
from lps.settings import load_settings, load_search_config


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("APIFY_TOKEN", "tok")
    s = load_settings()
    assert s.database_url == "postgresql://x/y"
    assert s.apify_token == "tok"


def test_load_search_config(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"maxItems": 5}), encoding="utf-8")
    assert load_search_config(str(p))["maxItems"] == 5
```

- [ ] **Step 7: Run test to verify it fails**

Run: `pytest tests/test_settings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lps'` or import error.

- [ ] **Step 8: Create `src/lps/settings.py`**

```python
import json
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    database_url: str
    apify_token: str | None


def load_settings() -> Settings:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set (see .env.example)")
    return Settings(database_url=url, apify_token=os.environ.get("APIFY_TOKEN"))


def load_search_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 9: Configure test discovery** — create `pytest.ini`

```ini
[pytest]
pythonpath = src
testpaths = tests
```

- [ ] **Step 10: Run test to verify it passes**

Run: `pytest tests/test_settings.py -v`
Expected: PASS (2 passed).

- [ ] **Step 11: Start Postgres and verify**

Run: `docker compose up -d && docker compose ps`
Expected: `lps_pg` running, port 5433 mapped.

- [ ] **Step 12: Commit**

```bash
git add docker-compose.yml .env.example requirements.txt config.example.json src/lps/__init__.py src/lps/settings.py pytest.ini tests/test_settings.py
git commit -m "chore: scaffold project, docker postgres, settings loader"
```

---

### Task 2: Database schema + migrate runner

**Files:**
- Create: `db/migrations/001_init.sql`
- Create: `src/lps/db.py` (connection + `run_migrations`)
- Test: `tests/test_migrate.py`

**Interfaces:**
- Produces: `lps.db.connect(dsn: str) -> psycopg.Connection`; `lps.db.run_migrations(conn, migrations_dir: str = "db/migrations") -> list[str]` (returns applied filenames).

- [ ] **Step 1: Create `db/migrations/001_init.sql`**

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TABLE IF NOT EXISTS person (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    linkedin_slug    text UNIQUE,
    linkedin_url     text,
    full_name        text,
    first_name       text,
    last_name        text,
    headline         text,
    location         text,
    country          text,
    current_company  text,
    current_title    text,
    connections      int,
    followers        int,
    email            text,
    norm_name        text,
    norm_company     text,
    data             jsonb NOT NULL DEFAULT '{}'::jsonb,
    sources          text[] NOT NULL DEFAULT '{}',
    source_hashes    jsonb NOT NULL DEFAULT '{}'::jsonb,
    needs_review     boolean NOT NULL DEFAULT false,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),
    last_enriched_at timestamptz
);
CREATE INDEX IF NOT EXISTS person_current_company_idx ON person (current_company);
CREATE INDEX IF NOT EXISTS person_data_gin ON person USING gin (data);

CREATE TABLE IF NOT EXISTS crawl_run (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source        text NOT NULL,
    status        text NOT NULL DEFAULT 'running',
    params        jsonb NOT NULL DEFAULT '{}'::jsonb,
    apify_run_id  text,
    dataset_id    text,
    checkpoint    jsonb NOT NULL DEFAULT '{"offset": 0}'::jsonb,
    fetched       int NOT NULL DEFAULT 0,
    inserted      int NOT NULL DEFAULT 0,
    enriched      int NOT NULL DEFAULT 0,
    unchanged     int NOT NULL DEFAULT 0,
    errors        int NOT NULL DEFAULT 0,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz
);

CREATE TABLE IF NOT EXISTS run_metric (
    id           bigserial PRIMARY KEY,
    run_id       uuid NOT NULL REFERENCES crawl_run(id) ON DELETE CASCADE,
    ts           timestamptz NOT NULL DEFAULT now(),
    processed    int NOT NULL,
    inserted     int NOT NULL,
    enriched     int NOT NULL,
    errors       int NOT NULL,
    rate_per_sec double precision NOT NULL
);
CREATE INDEX IF NOT EXISTS run_metric_run_idx ON run_metric (run_id, ts);

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
```

- [ ] **Step 2: Write the failing test** — `tests/test_migrate.py`

```python
from lps.db import connect, run_migrations


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
```

- [ ] **Step 3: Create test fixtures** — `tests/conftest.py`

```python
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
    # dedicated connection for DDL tests (committed, then dropped by reset)
    conn = psycopg.connect(TEST_DSN, autocommit=True)
    with conn.cursor() as cur:
        cur.execute(
            "DROP TABLE IF EXISTS run_metric, crawl_run, person, schema_migrations CASCADE"
        )
    yield conn
    conn.close()


@pytest.fixture
def conn(admin_conn):
    # migrated schema, work inside a rolled-back transaction
    from lps.db import run_migrations
    run_migrations(admin_conn)
    tx = psycopg.connect(TEST_DSN)
    yield tx
    tx.rollback()
    tx.close()
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_migrate.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_migrations'`.

- [ ] **Step 5: Create `src/lps/db.py` (connection + migrations)**

```python
import os
import psycopg


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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_migrate.py -v`
Expected: PASS (2 passed). (Requires `docker compose up -d` running.)

- [ ] **Step 7: Commit**

```bash
git add db/migrations/001_init.sql src/lps/db.py tests/conftest.py tests/test_migrate.py
git commit -m "feat: db schema and idempotent migration runner"
```

---

### Task 3: Normalization utilities

**Files:**
- Create: `src/lps/normalize.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Produces:
  - `normalize_slug(url: str | None) -> str | None`
  - `normalize_text(s: str | None) -> str | None`
  - `content_hash(payload: dict) -> str`

- [ ] **Step 1: Write the failing test** — `tests/test_normalize.py`

```python
from lps.normalize import normalize_slug, normalize_text, content_hash


def test_slug_basic():
    assert normalize_slug("https://www.linkedin.com/in/An-Nguyen-123/") == "an-nguyen-123"


def test_slug_country_subdomain_and_query():
    url = "https://vn.linkedin.com/in/An-Nguyen-123/?trk=abc"
    assert normalize_slug(url) == "an-nguyen-123"


def test_slug_none_when_no_in_path():
    assert normalize_slug("https://linkedin.com/company/acme") is None
    assert normalize_slug(None) is None


def test_normalize_text_unaccent_lower_collapse():
    assert normalize_text("  Nguyễn   Văn An ") == "nguyen van an"
    assert normalize_text(None) is None


def test_content_hash_stable_and_order_independent():
    a = content_hash({"x": 1, "y": 2})
    b = content_hash({"y": 2, "x": 1})
    assert a == b
    assert a != content_hash({"x": 1, "y": 3})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lps.normalize'`.

- [ ] **Step 3: Create `src/lps/normalize.py`**

```python
import hashlib
import json
import re
import unicodedata


def normalize_slug(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"/in/([^/?#]+)", url)
    if not m:
        return None
    return m.group(1).strip().lower()


def normalize_text(s: str | None) -> str | None:
    if s is None:
        return None
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_str = ascii_str.replace("đ", "d").replace("Đ", "D")
    ascii_str = ascii_str.lower()
    ascii_str = re.sub(r"\s+", " ", ascii_str).strip()
    return ascii_str


def content_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_normalize.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lps/normalize.py tests/test_normalize.py
git commit -m "feat: url slug + text normalization + content hash"
```

---

### Task 4: Canonical profile model

**Files:**
- Create: `src/lps/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `lps.models.CanonicalProfile` (pydantic `BaseModel`) with fields:
  `source: str`, `linkedin_url: str | None`, `linkedin_slug: str | None`,
  `full_name/first_name/last_name/headline/location/country/current_company/current_title: str | None`,
  `connections: int | None`, `followers: int | None`, `email: str | None`,
  `data: dict` (default `{}`), `raw: dict` (default `{}`).

- [ ] **Step 1: Write the failing test** — `tests/test_models.py`

```python
from lps.models import CanonicalProfile


def test_canonical_profile_defaults():
    p = CanonicalProfile(source="harvestapi", full_name="An Nguyen")
    assert p.source == "harvestapi"
    assert p.data == {}
    assert p.raw == {}
    assert p.email is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lps.models'`.

- [ ] **Step 3: Create `src/lps/models.py`**

```python
from pydantic import BaseModel, Field


class CanonicalProfile(BaseModel):
    source: str
    linkedin_url: str | None = None
    linkedin_slug: str | None = None
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    headline: str | None = None
    location: str | None = None
    country: str | None = None
    current_company: str | None = None
    current_title: str | None = None
    connections: int | None = None
    followers: int | None = None
    email: str | None = None
    data: dict = Field(default_factory=dict)
    raw: dict = Field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lps/models.py tests/test_models.py
git commit -m "feat: CanonicalProfile model"
```

---

### Task 5: Source adapter (base + harvestapi)

**Files:**
- Create: `src/lps/sources/__init__.py` (empty)
- Create: `src/lps/sources/base.py`
- Create: `src/lps/sources/harvestapi.py`
- Test: `tests/test_harvestapi.py`

**Interfaces:**
- Consumes: `CanonicalProfile` (Task 4), `normalize_slug` (Task 3).
- Produces:
  - `lps.sources.base.SourceAdapter` (Protocol): attr `name: str`; `normalize(self, raw: dict) -> CanonicalProfile`; `start_run(self, run_input: dict, token: str) -> tuple[str, str]` (returns `(apify_run_id, dataset_id)`); `iter_items(self, dataset_id: str, token: str, offset: int = 0) -> Iterator[dict]`.
  - `lps.sources.harvestapi.HarvestApiSource` implementing it (`name = "harvestapi"`, actor id `"harvestapi/linkedin-profile-search"`).

- [ ] **Step 1: Write the failing test** — `tests/test_harvestapi.py`

```python
from lps.sources.harvestapi import HarvestApiSource


def test_normalize_maps_core_fields():
    src = HarvestApiSource()
    raw = {
        "firstName": "An",
        "lastName": "Nguyen",
        "headline": "Marketing Manager at Shopee",
        "linkedinUrl": "https://www.linkedin.com/in/an-nguyen-123/",
        "location": "Ho Chi Minh City",
        "experience": [{"companyName": "Shopee", "title": "Marketing Manager"}],
    }
    p = src.normalize(raw)
    assert p.source == "harvestapi"
    assert p.linkedin_slug == "an-nguyen-123"
    assert p.full_name == "An Nguyen"
    assert p.current_company == "Shopee"
    assert p.current_title == "Marketing Manager"
    assert p.data["experience"][0]["companyName"] == "Shopee"
    assert p.raw == raw


def test_normalize_handles_missing_url():
    src = HarvestApiSource()
    p = src.normalize({"firstName": "Bich", "lastName": "Tran"})
    assert p.linkedin_slug is None
    assert p.full_name == "Bich Tran"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_harvestapi.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lps.sources'`.

- [ ] **Step 3: Create `src/lps/sources/__init__.py`** (empty file)

- [ ] **Step 4: Create `src/lps/sources/base.py`**

```python
from typing import Iterator, Protocol
from lps.models import CanonicalProfile


class SourceAdapter(Protocol):
    name: str

    def start_run(self, run_input: dict, token: str) -> tuple[str, str]:
        ...

    def iter_items(self, dataset_id: str, token: str, offset: int = 0) -> Iterator[dict]:
        ...

    def normalize(self, raw: dict) -> CanonicalProfile:
        ...
```

- [ ] **Step 5: Create `src/lps/sources/harvestapi.py`**

```python
from typing import Iterator
from apify_client import ApifyClient
from lps.models import CanonicalProfile
from lps.normalize import normalize_slug

ACTOR_ID = "harvestapi/linkedin-profile-search"


class HarvestApiSource:
    name = "harvestapi"

    def start_run(self, run_input: dict, token: str) -> tuple[str, str]:
        client = ApifyClient(token)
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        if not run or run.get("status") != "SUCCEEDED":
            raise RuntimeError(f"Apify run failed: {run.get('status') if run else None}")
        return run["id"], run["defaultDatasetId"]

    def iter_items(self, dataset_id: str, token: str, offset: int = 0) -> Iterator[dict]:
        client = ApifyClient(token)
        for item in client.dataset(dataset_id).iterate_items(offset=offset):
            yield item

    def normalize(self, raw: dict) -> CanonicalProfile:
        first = raw.get("firstName")
        last = raw.get("lastName")
        full = raw.get("name") or " ".join(x for x in [first, last] if x) or None
        exp = raw.get("experience") or []
        cur = exp[0] if isinstance(exp, list) and exp else {}
        url = raw.get("linkedinUrl") or raw.get("url") or raw.get("profileUrl")
        return CanonicalProfile(
            source=self.name,
            linkedin_url=url,
            linkedin_slug=normalize_slug(url),
            full_name=full,
            first_name=first,
            last_name=last,
            headline=raw.get("headline"),
            location=raw.get("location") or raw.get("locationName"),
            country=raw.get("country"),
            current_company=cur.get("companyName") or raw.get("companyName"),
            current_title=cur.get("title") or raw.get("jobTitle"),
            connections=raw.get("connectionsCount") or raw.get("connections"),
            followers=raw.get("followersCount") or raw.get("followers"),
            email=raw.get("email"),
            data=raw,
            raw=raw,
        )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_harvestapi.py -v`
Expected: PASS (2 passed).

- [ ] **Step 7: Commit**

```bash
git add src/lps/sources/ tests/test_harvestapi.py
git commit -m "feat: source adapter base + harvestapi adapter"
```

---

### Task 6: Person DB helpers

**Files:**
- Modify: `src/lps/db.py` (append person/run/metric helpers)
- Test: `tests/test_db_person.py`

**Interfaces:**
- Consumes: `conn` fixture (Task 2), `CanonicalProfile` (Task 4).
- Produces (all in `lps.db`):
  - `get_person_by_slug(conn, slug: str) -> dict | None` (row as dict, includes `id, data, sources, source_hashes` and scalar columns).
  - `insert_person(conn, profile: CanonicalProfile, *, needs_review: bool, content_hash: str, norm_name: str | None, norm_company: str | None) -> str` (returns new id).
  - `update_person(conn, person_id: str, *, scalars: dict, data: dict, sources: list[str], source_hashes: dict) -> None`.

- [ ] **Step 1: Write the failing test** — `tests/test_db_person.py`

```python
from lps.db import get_person_by_slug, insert_person, update_person
from lps.models import CanonicalProfile


def _profile(**kw):
    base = dict(source="harvestapi", linkedin_slug="an-nguyen-123",
                linkedin_url="https://linkedin.com/in/an-nguyen-123",
                full_name="An Nguyen", current_company="Shopee",
                data={"experience": [{"companyName": "Shopee"}]})
    base.update(kw)
    return CanonicalProfile(**base)


def test_insert_and_get(conn):
    pid = insert_person(conn, _profile(), needs_review=False, content_hash="h1",
                        norm_name="an nguyen", norm_company="shopee")
    row = get_person_by_slug(conn, "an-nguyen-123")
    assert row["id"] == pid
    assert row["full_name"] == "An Nguyen"
    assert row["sources"] == ["harvestapi"]
    assert row["source_hashes"] == {"harvestapi": "h1"}


def test_get_missing_returns_none(conn):
    assert get_person_by_slug(conn, "nope") is None


def test_update_person(conn):
    pid = insert_person(conn, _profile(), needs_review=False, content_hash="h1",
                        norm_name="an nguyen", norm_company="shopee")
    update_person(conn, pid, scalars={"email": "a@shopee.com"},
                  data={"experience": [{"companyName": "Shopee"}], "email": "a@shopee.com"},
                  sources=["harvestapi", "other"],
                  source_hashes={"harvestapi": "h1", "other": "h2"})
    row = get_person_by_slug(conn, "an-nguyen-123")
    assert row["email"] == "a@shopee.com"
    assert set(row["sources"]) == {"harvestapi", "other"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db_person.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_person_by_slug'`.

- [ ] **Step 3: Append helpers to `src/lps/db.py`**

```python
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db_person.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lps/db.py tests/test_db_person.py
git commit -m "feat: person db helpers (get/insert/update)"
```

---

### Task 7: Ingest engine (dedup + enrich)

**Files:**
- Create: `src/lps/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `get_person_by_slug`, `insert_person`, `update_person` (Task 6); `normalize_text`, `content_hash` (Task 3); `CanonicalProfile` (Task 4).
- Produces:
  - `deep_merge_data(existing: dict, incoming: dict) -> dict` (union; list values concatenated then deduped by JSON identity preserving order).
  - `merge_scalars(row: dict, profile: CanonicalProfile) -> dict` (only keys whose row value is empty/None and profile value is non-empty).
  - `ingest_profile(conn, profile: CanonicalProfile) -> str` returning one of `"inserted" | "enriched" | "unchanged" | "needs_review"`.

- [ ] **Step 1: Write the failing test** — `tests/test_ingest.py`

```python
from lps.ingest import ingest_profile, deep_merge_data, merge_scalars
from lps.models import CanonicalProfile


def test_deep_merge_dedups_lists():
    a = {"experience": [{"c": "Shopee"}], "skills": ["a"]}
    b = {"experience": [{"c": "Shopee"}, {"c": "Grab"}], "skills": ["a", "b"]}
    out = deep_merge_data(a, b)
    assert out["experience"] == [{"c": "Shopee"}, {"c": "Grab"}]
    assert out["skills"] == ["a", "b"]


def test_merge_scalars_fills_only_missing():
    row = {"full_name": "An Nguyen", "email": None, "headline": ""}
    p = CanonicalProfile(source="x", full_name="OVERWRITE?", email="a@b.com", headline="Head")
    out = merge_scalars(row, p)
    assert out == {"email": "a@b.com", "headline": "Head"}


def test_insert_then_enrich_then_unchanged(conn):
    p1 = CanonicalProfile(source="harvestapi",
        linkedin_url="https://linkedin.com/in/an-nguyen-123",
        full_name="An Nguyen", current_company="Shopee",
        data={"experience": [{"companyName": "Shopee"}]})
    assert ingest_profile(conn, p1) == "inserted"

    p2 = CanonicalProfile(source="other",
        linkedin_url="https://vn.linkedin.com/in/An-Nguyen-123/",
        full_name="An Nguyen", email="a@shopee.com", current_company="Shopee",
        data={"education": [{"school": "UEH"}]})
    assert ingest_profile(conn, p2) == "enriched"

    assert ingest_profile(conn, p2) == "unchanged"


def test_missing_slug_needs_review(conn):
    p = CanonicalProfile(source="harvestapi", full_name="Bich Tran", current_company="FPT")
    assert ingest_profile(conn, p) == "needs_review"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lps.ingest'`.

- [ ] **Step 3: Create `src/lps/ingest.py`**

```python
import json
from lps.models import CanonicalProfile
from lps.normalize import normalize_slug, normalize_text, content_hash
from lps.db import get_person_by_slug, insert_person, update_person, SCALAR_COLUMNS


def _dedup_list(items: list) -> list:
    seen, out = set(), []
    for it in items:
        key = json.dumps(it, sort_keys=True, ensure_ascii=False, default=str)
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def deep_merge_data(existing: dict, incoming: dict) -> dict:
    out = dict(existing)
    for k, v in incoming.items():
        if isinstance(v, list) and isinstance(out.get(k), list):
            out[k] = _dedup_list(out[k] + v)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge_data(out[k], v)
        elif k not in out or out[k] in (None, "", [], {}):
            out[k] = v
    return out


def _empty(x) -> bool:
    return x is None or x == "" or x == [] or x == {}


def merge_scalars(row: dict, profile: CanonicalProfile) -> dict:
    out = {}
    for col in SCALAR_COLUMNS:
        if col == "linkedin_slug":
            continue
        new = getattr(profile, col)
        if _empty(row.get(col)) and not _empty(new):
            out[col] = new
    return out


def ingest_profile(conn, profile: CanonicalProfile) -> str:
    slug = profile.linkedin_slug or normalize_slug(profile.linkedin_url)
    profile.linkedin_slug = slug
    chash = content_hash(profile.raw or profile.data)
    norm_name = normalize_text(profile.full_name)
    norm_company = normalize_text(profile.current_company)

    if not slug:
        insert_person(conn, profile, needs_review=True, content_hash=chash,
                      norm_name=norm_name, norm_company=norm_company)
        conn.commit()
        return "needs_review"

    row = get_person_by_slug(conn, slug)
    if row is None:
        insert_person(conn, profile, needs_review=False, content_hash=chash,
                      norm_name=norm_name, norm_company=norm_company)
        conn.commit()
        return "inserted"

    hashes = dict(row["source_hashes"])
    if hashes.get(profile.source) == chash:
        return "unchanged"

    merged_data = deep_merge_data(row["data"], profile.data)
    scalars = merge_scalars(row, profile)
    sources = list(dict.fromkeys(list(row["sources"]) + [profile.source]))
    hashes[profile.source] = chash
    update_person(conn, row["id"], scalars=scalars, data=merged_data,
                  sources=sources, source_hashes=hashes)
    conn.commit()
    return "enriched"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest.py -v`
Expected: PASS (4 passed).

> Note: `ingest_profile` calls `conn.commit()`. The test `conn` fixture rolls back at teardown; commits inside the test are fine because each test uses a fresh admin-reset schema.

- [ ] **Step 5: Commit**

```bash
git add src/lps/ingest.py tests/test_ingest.py
git commit -m "feat: ingest engine with slug dedup and deep-merge enrich"
```

---

### Task 8: Job runner (resume + throughput metrics)

**Files:**
- Modify: `src/lps/db.py` (append run/metric helpers)
- Create: `src/lps/runner.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `ingest_profile` (Task 7); `SourceAdapter` (Task 5).
- Produces (in `lps.db`): `create_run(conn, source, params, apify_run_id, dataset_id) -> str`; `set_checkpoint(conn, run_id, offset) -> None`; `record_metric(conn, run_id, processed, inserted, enriched, errors, rate) -> None`; `finish_run(conn, run_id, status, totals: dict) -> None`; `get_run(conn, run_id) -> dict | None`.
- Produces (in `lps.runner`): `run_crawl(conn, adapter, run_input, token, *, run_id=None, metric_every=50, now=<callable>) -> dict` returning totals dict `{run_id, fetched, inserted, enriched, unchanged, errors}`. `now` is an injectable `() -> float` (defaults to `time.monotonic`) for testable throughput.

- [ ] **Step 1: Write the failing test** — `tests/test_runner.py`

```python
from itertools import count
from lps.runner import run_crawl
from lps.db import get_run
from lps.models import CanonicalProfile


class FakeAdapter:
    name = "fake"

    def __init__(self, items):
        self._items = items

    def start_run(self, run_input, token):
        return "apify-1", "ds-1"

    def iter_items(self, dataset_id, token, offset=0):
        return iter(self._items[offset:])

    def normalize(self, raw):
        return CanonicalProfile(
            source=self.name,
            linkedin_url=f"https://linkedin.com/in/{raw['slug']}",
            full_name=raw.get("name"), current_company=raw.get("company"),
            data=raw, raw=raw)


def test_run_crawl_counts_outcomes(conn):
    items = [
        {"slug": "a", "name": "A", "company": "X"},
        {"slug": "b", "name": "B", "company": "Y"},
        {"slug": "a", "name": "A", "company": "X"},  # duplicate -> unchanged
    ]
    ticks = count(0, 1)
    totals = run_crawl(conn, FakeAdapter(items), {"maxItems": 3}, "tok",
                       metric_every=1, now=lambda: next(ticks))
    assert totals["fetched"] == 3
    assert totals["inserted"] == 2
    assert totals["unchanged"] == 1
    run = get_run(conn, totals["run_id"])
    assert run["status"] == "succeeded"
    assert run["inserted"] == 2


def test_run_crawl_resumes_from_checkpoint(conn):
    items = [{"slug": "a", "name": "A", "company": "X"},
             {"slug": "b", "name": "B", "company": "Y"}]
    ticks = count(0, 1)
    t1 = run_crawl(conn, FakeAdapter(items), {}, "tok", now=lambda: next(ticks))
    # re-run same run id: offset at end -> nothing new, all unchanged/none
    t2 = run_crawl(conn, FakeAdapter(items), {}, "tok",
                   run_id=t1["run_id"], now=lambda: next(ticks))
    assert t2["fetched"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lps.runner'`.

- [ ] **Step 3: Append run/metric helpers to `src/lps/db.py`**

```python
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
```

- [ ] **Step 4: Create `src/lps/runner.py`**

```python
import time
import logging
from lps.db import (create_run, set_checkpoint, record_metric, finish_run, get_run)
from lps.ingest import ingest_profile

log = logging.getLogger("lps.runner")


def run_crawl(conn, adapter, run_input, token, *, run_id=None, metric_every=50, now=time.monotonic):
    if run_id is None:
        apify_run_id, dataset_id = adapter.start_run(run_input, token)
        run_id = create_run(conn, adapter.name, run_input, apify_run_id, dataset_id)
        offset = 0
    else:
        run = get_run(conn, run_id)
        if run is None:
            raise RuntimeError(f"run {run_id} not found")
        dataset_id = run["dataset_id"]
        offset = run["checkpoint"].get("offset", 0)

    totals = {"fetched": 0, "inserted": 0, "enriched": 0, "unchanged": 0, "errors": 0}
    start = now()
    processed = 0
    try:
        for raw in adapter.iter_items(dataset_id, token, offset=offset):
            totals["fetched"] += 1
            try:
                outcome = ingest_profile(conn, adapter.normalize(raw))
                totals[outcome if outcome != "needs_review" else "inserted"] += 1
            except Exception:
                conn.rollback()
                totals["errors"] += 1
                log.exception("ingest failed for item at offset %s", offset)
            processed += 1
            offset += 1
            if processed % metric_every == 0:
                elapsed = max(now() - start, 1e-9)
                set_checkpoint(conn, run_id, offset)
                record_metric(conn, run_id, processed, totals["inserted"],
                              totals["enriched"], totals["errors"], processed / elapsed)
        set_checkpoint(conn, run_id, offset)
        finish_run(conn, run_id, "succeeded", totals)
    except Exception:
        finish_run(conn, run_id, "failed", totals)
        raise
    totals["run_id"] = run_id
    return totals
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_runner.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add src/lps/db.py src/lps/runner.py tests/test_runner.py
git commit -m "feat: resumable job runner with throughput metrics"
```

---

### Task 9: CLI (migrate / crawl / status)

**Files:**
- Create: `src/lps/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_settings`, `load_search_config` (Task 1); `connect`, `run_migrations`, `get_run` (Tasks 2/8); `run_crawl` (Task 8); `HarvestApiSource` (Task 5).
- Produces: `lps.cli.main(argv: list[str]) -> int`. Subcommands: `migrate`; `crawl --config PATH [--resume RUN_ID]`; `status [--run RUN_ID]`.

- [ ] **Step 1: Write the failing test** — `tests/test_cli.py`

```python
from lps.cli import build_parser


def test_parser_crawl():
    args = build_parser().parse_args(["crawl", "--config", "config.json"])
    assert args.command == "crawl"
    assert args.config == "config.json"


def test_parser_status_and_migrate():
    assert build_parser().parse_args(["migrate"]).command == "migrate"
    assert build_parser().parse_args(["status", "--run", "r1"]).run == "r1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lps.cli'`.

- [ ] **Step 3: Create `src/lps/cli.py`**

```python
import argparse
import sys
from lps.settings import load_settings, load_search_config
from lps.db import connect, run_migrations, get_run
from lps.runner import run_crawl
from lps.sources.harvestapi import HarvestApiSource


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lps", description="LinkedIn profile crawl pipeline")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="apply DB migrations")
    c = sub.add_parser("crawl", help="run a crawl")
    c.add_argument("--config", required=True)
    c.add_argument("--resume", default=None, help="resume an existing run id")
    s = sub.add_parser("status", help="show run status")
    s.add_argument("--run", default=None)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    settings = load_settings()

    if args.command == "migrate":
        with connect(settings.database_url, autocommit=True) as conn:
            applied = run_migrations(conn)
        print("Applied:", applied or "(nothing new)")
        return 0

    if args.command == "crawl":
        if not settings.apify_token:
            print("APIFY_TOKEN not set", file=sys.stderr)
            return 2
        run_input = load_search_config(args.config)
        with connect(settings.database_url) as conn:
            totals = run_crawl(conn, HarvestApiSource(), run_input,
                               settings.apify_token, run_id=args.resume)
        print("Run:", totals["run_id"])
        for k in ("fetched", "inserted", "enriched", "unchanged", "errors"):
            print(f"  {k}: {totals[k]}")
        return 0

    if args.command == "status":
        with connect(settings.database_url) as conn:
            if args.run:
                run = get_run(conn, args.run)
                print(run)
            else:
                with conn.cursor() as cur:
                    cur.execute("SELECT id, source, status, fetched, inserted, enriched, "
                                "unchanged, errors, started_at FROM crawl_run "
                                "ORDER BY started_at DESC LIMIT 10")
                    for r in cur.fetchall():
                        print(r)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Manual smoke — migrate against real DB**

Run: `python -m lps.cli migrate`
Expected: `Applied: ['001_init.sql']` (or `(nothing new)` if already applied).

- [ ] **Step 6: Commit**

```bash
git add src/lps/cli.py tests/test_cli.py
git commit -m "feat: cli with migrate/crawl/status"
```

---

### Task 10: Dashboard (FastAPI + Chart.js)

**Files:**
- Create: `dashboard/app.py`
- Create: `dashboard/static/index.html`
- Create: `dashboard/static/vendor/chart.umd.js` (vendored, offline)
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `connect` (Task 2); tables `person`, `crawl_run`, `run_metric`.
- Produces: `dashboard.app.app` (FastAPI). Endpoints: `GET /api/stats` -> `{persons, needs_review, by_source}`; `GET /api/runs` -> list; `GET /api/runs/{run_id}/metrics` -> list of metric points; `GET /` -> static HTML.

- [ ] **Step 1: Write the failing test** — `tests/test_dashboard.py`

```python
import os
import psycopg
from fastapi.testclient import TestClient


def test_stats_endpoint(monkeypatch):
    dsn = os.environ.get("TEST_DATABASE_URL", "postgresql://lps:lps@localhost:5433/lps_test")
    # ensure schema exists
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'dashboard'`.

- [ ] **Step 3: Create `dashboard/__init__.py`** (empty) and **`dashboard/app.py`**

```python
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from psycopg.rows import dict_row
from lps.db import connect

app = FastAPI(title="LPS Dashboard")
STATIC = Path(__file__).parent / "static"


def _dsn() -> str:
    return os.environ["DATABASE_URL"]


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
        return [dict(r, id=str(r["id"])) for r in cur.fetchall()]


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
```

- [ ] **Step 4: Vendor Chart.js (offline)**

Run:
```bash
mkdir -p dashboard/static/vendor
curl -L -o dashboard/static/vendor/chart.umd.js https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.js
```
Expected: file ~200KB exists. (One-time download so the dashboard needs no network at runtime.)

- [ ] **Step 5: Create `dashboard/static/index.html`**

```html
<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>LPS Dashboard</title>
<script src="/static/vendor/chart.umd.js"></script>
<style>
  body{font-family:system-ui,sans-serif;background:#FAF9F5;color:#3D3D3A;margin:0;padding:32px;}
  h1{font-size:24px;color:#141413;}
  .cards{display:flex;gap:16px;margin:20px 0;flex-wrap:wrap;}
  .card{background:#fff;border:1px solid #D1CFC5;border-radius:12px;padding:16px 20px;min-width:140px;}
  .card .k{font-size:12px;color:#87867F;text-transform:uppercase;}
  .card .v{font-size:28px;color:#141413;font-weight:600;}
  table{border-collapse:collapse;width:100%;background:#fff;border:1px solid #D1CFC5;border-radius:8px;overflow:hidden;}
  th,td{padding:8px 12px;border-bottom:1px solid #eee;text-align:left;font-size:13px;}
  th{background:#F0EEE6;}
  canvas{background:#fff;border:1px solid #D1CFC5;border-radius:12px;padding:12px;margin-top:16px;max-width:900px;}
</style>
</head>
<body>
<h1>LinkedIn Profile Crawl — Dashboard</h1>
<div class="cards" id="cards"></div>
<h2>Runs</h2>
<table id="runs"><thead><tr><th>Started</th><th>Status</th><th>Fetched</th><th>Inserted</th><th>Enriched</th><th>Unchanged</th><th>Errors</th></tr></thead><tbody></tbody></table>
<h2>Throughput (run mới nhất)</h2>
<canvas id="chart" width="900" height="320"></canvas>
<script>
async function j(u){const r=await fetch(u);return r.json();}
async function load(){
  const s=await j('/api/stats');
  document.getElementById('cards').innerHTML=
    card('Total persons',s.persons)+card('Needs review',s.needs_review)+
    Object.entries(s.by_source).map(([k,v])=>card('src: '+k,v)).join('');
  const runs=await j('/api/runs');
  document.querySelector('#runs tbody').innerHTML=runs.map(r=>
    `<tr><td>${r.started_at||''}</td><td>${r.status}</td><td>${r.fetched}</td><td>${r.inserted}</td><td>${r.enriched}</td><td>${r.unchanged}</td><td>${r.errors}</td></tr>`).join('');
  if(runs.length){
    const m=await j('/api/runs/'+runs[0].id+'/metrics');
    draw(m);
  }
}
function card(k,v){return `<div class="card"><div class="k">${k}</div><div class="v">${v}</div></div>`;}
let chart;
function draw(m){
  const ctx=document.getElementById('chart');
  if(chart)chart.destroy();
  chart=new Chart(ctx,{type:'line',data:{labels:m.map(p=>p.processed),
    datasets:[{label:'profiles/sec',data:m.map(p=>p.rate_per_sec),borderColor:'#D97757',tension:.3}]},
    options:{scales:{x:{title:{display:true,text:'processed'}},y:{title:{display:true,text:'rate/sec'}}}}});
}
load();setInterval(load,5000);
</script>
</body>
</html>
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_dashboard.py -v`
Expected: PASS (1 passed).

- [ ] **Step 7: Manual smoke — launch dashboard**

Run: `uvicorn dashboard.app:app --port 8000`
Expected: open `http://localhost:8000` — cards + runs table render (empty until a crawl runs).

- [ ] **Step 8: Update `.gitignore` for vendored file decision + commit**

Keep the vendored Chart.js committed (offline reproducibility). Commit:
```bash
git add dashboard/ tests/test_dashboard.py
git commit -m "feat: fastapi + chart.js throughput dashboard"
```

---

### Task 11: README usage + end-to-end smoke

**Files:**
- Modify: `README.md` (append a "Chạy pipeline" section)
- Create: `docs/RUNBOOK.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Append run instructions to `README.md`**

```markdown
## Chạy pipeline

1. `conda create -n lps python=3.12 -y && conda activate lps`
2. `pip install -r requirements.txt`
3. `docker compose up -d`   # Postgres 16 tại localhost:5433
4. `cp .env.example .env`   # điền APIFY_TOKEN
5. `python -m lps.cli migrate`
6. `cp config.example.json config.json`  # sửa filter
7. `python -m lps.cli crawl --config config.json`
8. `uvicorn dashboard.app:app --port 8000`  # dashboard
9. `python -m lps.cli status`  # xem run
```

- [ ] **Step 2: Create `docs/RUNBOOK.md`** with resume + troubleshooting

```markdown
# Runbook

- **Resume a failed run:** `python -m lps.cli crawl --config config.json --resume <RUN_ID>`
- **Reset DB (danger):** `docker compose down -v && docker compose up -d && python -m lps.cli migrate`
- **needs_review rows:** `SELECT full_name, linkedin_url FROM person WHERE needs_review;`
- **Enable fuzzy later:** norm_name/norm_company already populated; add a fuzzy fallback in ingest_profile before insert.
```

- [ ] **Step 3: Full test suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/RUNBOOK.md
git commit -m "docs: usage + runbook"
```

---

## Self-Review

**Spec coverage:**
- Crawl harvestapi by filters → Tasks 5, 9 (config = filters), 8 (runner). ✓
- Save all info → Task 6/7 store full `data` JSONB. ✓
- Email optional → column present (Task 2), mapped (Task 5), never required. ✓
- Postgres in Docker → Task 1. ✓
- Single data table + 2 ops tables → Task 2. ✓
- Dedup by normalized slug UNIQUE, enrich not duplicate → Tasks 3, 7. ✓
- No-slug → needs_review → Task 7. ✓
- Idempotent via content_hash → Tasks 3, 7. ✓
- Deep-merge arrays dedup → Task 7. ✓
- Resumable runner + checkpoint → Task 8. ✓
- Throughput metrics → Task 8 (`run_metric`, rate_per_sec). ✓
- Dashboard FastAPI + Chart.js → Task 10. ✓
- CLI migrate/crawl/status → Task 9. ✓
- TDD + tests + rollback fixture → Task 2 conftest, every task. ✓
- Fuzzy kept for future (norm_* columns unused) → Task 2 schema, Task 7 populates them. ✓

**Placeholder scan:** No TBD/TODO; all code steps show full code. ✓

**Type consistency:** `ingest_profile(conn, profile) -> str`; `run_crawl(...) -> dict` with `run_id`; `get_person_by_slug/insert_person/update_person` signatures match between Task 6 definition and Task 7 usage; `SCALAR_COLUMNS` defined in Task 6, imported in Task 7. ✓

**Note on outcome counting:** In Task 8, `needs_review` outcomes are counted under `inserted` (a needs_review row is still a new insert). This is intentional and documented in the runner loop.
