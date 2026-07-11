import time
import logging
from lps.db import create_run, set_checkpoint, record_metric, finish_run, get_run
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
