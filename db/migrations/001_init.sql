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

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename   text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
