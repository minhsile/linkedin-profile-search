import argparse
import sys
from config import load_settings, load_search_config, normalize_configs
from utilities.database import connect, run_migrations, get_run
from src.runner import run_crawl
from research.linkedin_scraping.harvestapi import HarvestApiSource

_KEYS = ("fetched", "inserted", "enriched", "unchanged", "errors")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="linkedin-crawl", description="LinkedIn profile crawl pipeline")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="apply DB migrations")
    c = sub.add_parser("crawl", help="run a crawl (config may be 1 object or an array)")
    c.add_argument("--config", required=True)
    c.add_argument("--resume", default=None, help="resume an existing run id")
    s = sub.add_parser("status", help="show run status")
    s.add_argument("--run", default=None)
    return p


def _print_totals(totals: dict) -> None:
    print(f"  run: {totals['run_id']}")
    for k in _KEYS:
        print(f"  {k}: {totals[k]}")


def _label(cfg: dict, i: int) -> str:
    return (cfg.get("searchQuery")
            or ", ".join(cfg.get("currentJobTitles", []))
            or f"config {i}")


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
        raw = load_search_config(args.config)
        adapter = HarvestApiSource()
        with connect(settings.database_url) as conn:
            if args.resume:
                totals = run_crawl(conn, adapter, {}, settings.apify_token, run_id=args.resume)
                _print_totals(totals)
                return 0
            configs = normalize_configs(raw)
            agg = {k: 0 for k in _KEYS}
            for i, cfg in enumerate(configs, 1):
                print(f"\n[{i}/{len(configs)}] crawl: {_label(cfg, i)}")
                try:
                    totals = run_crawl(conn, adapter, cfg, settings.apify_token)
                except Exception as e:
                    print(f"  LỖI (bỏ qua config này): {e}", file=sys.stderr)
                    continue
                _print_totals(totals)
                for k in _KEYS:
                    agg[k] += totals[k]
            if len(configs) > 1:
                print("\n=== TỔNG tất cả config ===")
                for k in _KEYS:
                    print(f"  {k}: {agg[k]}")
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
