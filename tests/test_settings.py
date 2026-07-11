import json
from lps.settings import load_settings, load_search_config, normalize_configs


def test_load_settings_reads_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("APIFY_TOKEN", "tok")
    s = load_settings()
    assert s.database_url == "postgresql://x/y"
    assert s.apify_token == "tok"


def test_load_search_config_single(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"maxItems": 5}), encoding="utf-8")
    assert load_search_config(str(p))["maxItems"] == 5


def test_load_search_config_array(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps([{"maxItems": 5}, {"maxItems": 9}]), encoding="utf-8")
    assert load_search_config(str(p)) == [{"maxItems": 5}, {"maxItems": 9}]


def test_normalize_configs_wraps_single():
    assert normalize_configs({"a": 1}) == [{"a": 1}]


def test_normalize_configs_passes_list():
    assert normalize_configs([{"a": 1}, {"b": 2}]) == [{"a": 1}, {"b": 2}]
