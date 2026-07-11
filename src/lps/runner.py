import time
import logging
from lps.db import create_run, set_checkpoint, record_metric, finish_run, get_run
from lps.ingest import ingest_profile

log = logging.getLogger("lps.runner")

_TERMINAL = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT"}


def _zero():
    return {"fetched": 0, "inserted": 0, "enriched": 0, "unchanged": 0, "errors": 0}


def run_crawl(conn, adapter, run_input, token, *, run_id=None,
              poll_every=2.0, now=time.monotonic, sleep=time.sleep):
    """
    Giai đoạn 1 (chỉ khi crawl mới): khởi động actor async + poll số item Apify cào được
      theo thời gian -> ghi run_metric = TỐC ĐỘ APIFY CÀO (profiles/giây).
    Giai đoạn 2: ingest toàn bộ dataset + dedup (không ghi vào chart throughput).
    """
    if run_id is None:
        apify_run_id, dataset_id = adapter.start_run(run_input, token)
        run_id = create_run(conn, adapter.name, run_input, apify_run_id, dataset_id)
        start = now()
        status = "RUNNING"
        while True:
            status, count = adapter.poll(apify_run_id, dataset_id, token)
            elapsed = max(now() - start, 1e-9)
            record_metric(conn, run_id, count, 0, 0, 0, count / elapsed)
            if status in _TERMINAL:
                break
            sleep(poll_every)
        if status != "SUCCEEDED":
            finish_run(conn, run_id, "failed", _zero())
            raise RuntimeError(f"Apify run kết thúc với status {status}")
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
