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


def load_search_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
