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
        {"slug": "a", "name": "A", "company": "X"},
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
    t2 = run_crawl(conn, FakeAdapter(items), {}, "tok",
                   run_id=t1["run_id"], now=lambda: next(ticks))
    assert t2["fetched"] == 0


def test_run_crawl_records_at_least_one_metric_for_short_run(conn):
    items = [{"slug": f"p{i}", "name": f"N{i}", "company": "X"} for i in range(3)]
    ticks = count(0, 1)
    t = run_crawl(conn, FakeAdapter(items), {}, "tok",
                  metric_every=10, now=lambda: next(ticks))
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM run_metric WHERE run_id = %s", (t["run_id"],))
        assert cur.fetchone()[0] >= 1
