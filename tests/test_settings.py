import json
from lps.settings import load_settings, load_search_config


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("APIFY_TOKEN", "tok")
    s = load_settings()
    assert s.database_url == "postgresql://x/y"
    assert s.apify_token == "tok"


def test_load_search_config(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"maxItems": 5}), encoding="utf-8")
    assert load_search_config(str(p))["maxItems"] == 5
