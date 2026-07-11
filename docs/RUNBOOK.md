# Runbook

- **Resume a failed run:** `python -m lps.cli crawl --config config.json --resume <RUN_ID>`
- **Reset DB (danger):** `docker compose down -v && docker compose up -d && python -m lps.cli migrate`
- **needs_review rows:** `SELECT full_name, linkedin_url FROM person WHERE needs_review;`
- **Enable fuzzy later:** norm_name/norm_company already populated; add a fuzzy fallback in ingest_profile before insert.
