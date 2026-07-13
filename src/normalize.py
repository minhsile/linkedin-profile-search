import hashlib
import json
import re


def normalize_slug(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"/in/([^/?#]+)", url)
    if not m:
        return None
    return m.group(1).strip().lower()


def content_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
