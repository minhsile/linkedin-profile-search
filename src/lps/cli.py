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
                print(get_run(conn, args.run))
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
