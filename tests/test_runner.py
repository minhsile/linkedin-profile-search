from itertools import count
from lps.runner import run_crawl
from lps.db import get_run
from lps.models import CanonicalProfile

NOOP = lambda *a, **k: None


class FakeAdapter:
    name = "fake"

    def __init__(self, items, poll_sequence=None):
        self._items = items
        # danh sach (status, count) tra dan moi lan poll; mac dinh: xong ngay
        self._polls = poll_sequence or [("SUCCEEDED", len(items))]
        self._i = 0

    def start_run(self, run_input, token):
        return "apify-1", "ds-1"

    def poll(self, apify_run_id, dataset_id, token):
        r = self._polls[min(self._i, len(self._polls) - 1)]
        self._i += 1
        return r

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
    ticks = count(1, 1)
    totals = run_crawl(conn, FakeAdapter(items), {"maxItems": 3}, "tok",
                       poll_every=0, now=lambda: next(ticks), sleep=NOOP,
                       on_progress=NOOP)
    assert totals["fetched"] == 3
    assert totals["inserted"] == 2
    assert totals["unchanged"] == 1
    run = get_run(conn, totals["run_id"])
    assert run["status"] == "succeeded"
    assert run["inserted"] == 2


def test_run_crawl_resumes_from_checkpoint(conn):
    items = [{"slug": "a", "name": "A", "company": "X"},
             {"slug": "b", "name": "B", "company": "Y"}]
    ticks = count(1, 1)
    t1 = run_crawl(conn, FakeAdapter(items), {}, "tok",
                   poll_every=0, now=lambda: next(ticks), sleep=NOOP, on_progress=NOOP)
    t2 = run_crawl(conn, FakeAdapter(items), {}, "tok",
                   run_id=t1["run_id"], now=lambda: next(ticks), on_progress=NOOP)
    assert t2["fetched"] == 0


def test_crawl_reports_progress_each_poll(conn):
    # poll loop cho actor cao xong (SUCCEEDED) roi moi ingest; on_progress goi moi lan poll
    items = [{"slug": f"p{i}", "name": f"N{i}", "company": "X"} for i in range(3)]
    polls = [("RUNNING", 1), ("RUNNING", 2), ("SUCCEEDED", 3)]
    seen = []
    ticks = count(1, 1)
    t = run_crawl(conn, FakeAdapter(items, polls), {}, "tok",
                  poll_every=0, now=lambda: next(ticks), sleep=NOOP,
                  on_progress=lambda c, r, s: seen.append((c, s)))
    assert seen == [(1, "RUNNING"), (2, "RUNNING"), (3, "SUCCEEDED")]
    assert t["inserted"] == 3


def test_crawl_fails_when_actor_not_succeeded(conn):
    items = [{"slug": "a", "name": "A", "company": "X"}]
    polls = [("RUNNING", 0), ("FAILED", 0)]
    ticks = count(1, 1)
    try:
        run_crawl(conn, FakeAdapter(items, polls), {}, "tok",
                  poll_every=0, now=lambda: next(ticks), sleep=NOOP, on_progress=NOOP)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
