import json
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    database_url: str
    apify_token: str | None


def load_settings() -> Settings:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set (see .env.example)")
    return Settings(database_url=url, apify_token=os.environ.get("APIFY_TOKEN"))


def load_search_config(path: str):
    """Trả về nội dung JSON: 1 object (dict) hoặc danh sách object (list)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_configs(raw) -> list[dict]:
    """Chuẩn hóa về LIST config. Cho phép file là 1 object hoặc 1 array object."""
    if isinstance(raw, list):
        return raw
    return [raw]
