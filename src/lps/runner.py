import time
import logging
from lps.db import create_run, set_checkpoint, finish_run, get_run
from lps.ingest import ingest_profile

log = logging.getLogger("lps.runner")

_TERMINAL = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT"}


def _zero():
    return {"fetched": 0, "inserted": 0, "enriched": 0, "unchanged": 0, "errors": 0}


def run_crawl(conn, adapter, run_input, token, *, run_id=None,
              poll_every=2.0, now=time.monotonic, sleep=time.sleep):
    """
    Giai doan 1 (chi khi crawl moi): khoi dong actor async + poll cho toi khi
      Apify cao xong, in 1 dong tong ket throughput (so profile / thoi gian).
    Giai doan 2: ingest toan bo dataset + dedup.
    """
    if run_id is None:
        apify_run_id, dataset_id = adapter.start_run(run_input, token)
        run_id = create_run(conn, adapter.name, run_input, apify_run_id, dataset_id)
        start = now()
        status, count = "RUNNING", 0
        while status not in _TERMINAL:
            status, count = adapter.poll(apify_run_id, dataset_id, token)
            if status in _TERMINAL:
                break
            sleep(poll_every)
        elapsed = max(now() - start, 1e-9)
        print(f"    Apify cao xong: {count} profiles / {elapsed:.0f}s "
              f"(~{count / elapsed:.1f} profiles/s) [{status}]")
        if status != "SUCCEEDED":
            finish_run(conn, run_id, "failed", _zero())
            raise RuntimeError(f"Apify run ket thuc voi status {status}")
        offset = 0
    else:
        run = get_run(conn, run_id)
        if run is None:
            raise RuntimeError(f"run {run_id} not found")
        dataset_id = run["dataset_id"]
        offset = run["checkpoint"].get("offset", 0)

    totals = _zero()
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
            offset += 1
        set_checkpoint(conn, run_id, offset)
        finish_run(conn, run_id, "succeeded", totals)
    except Exception:
        finish_run(conn, run_id, "failed", totals)
        raise
    totals["run_id"] = run_id
    return totals
