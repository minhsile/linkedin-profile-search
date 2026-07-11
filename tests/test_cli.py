from lps.cli import build_parser


def test_parser_crawl():
    args = build_parser().parse_args(["crawl", "--config", "config.json"])
    assert args.command == "crawl"
    assert args.config == "config.json"


def test_parser_status_and_migrate():
    assert build_parser().parse_args(["migrate"]).command == "migrate"
    assert build_parser().parse_args(["status", "--run", "r1"]).run == "r1"
