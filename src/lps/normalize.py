import hashlib
import json
import re
import unicodedata


def normalize_slug(url: str | None) -> str | None:
    if not url:
        return None
    m = re.search(r"/in/([^/?#]+)", url)
    if not m:
        return None
    return m.group(1).strip().lower()


def normalize_text(s: str | None) -> str | None:
    if s is None:
        return None
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    ascii_str = ascii_str.replace("đ", "d").replace("Đ", "D")
    ascii_str = ascii_str.lower()
    ascii_str = re.sub(r"\s+", " ", ascii_str).strip()
    return ascii_str


def content_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
