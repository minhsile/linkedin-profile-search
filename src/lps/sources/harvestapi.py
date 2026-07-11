import re
from typing import Iterator
from apify_client import ApifyClient
from lps.models import CanonicalProfile
from lps.normalize import normalize_slug

ACTOR_ID = "harvestapi/linkedin-profile-search"

# Các key thường gặp khi 1 field text bị bọc trong dict (harvestapi trả location/company... dạng object)
_TEXT_KEYS = ("linkedinText", "text", "name", "title", "position", "city", "countryFull", "default")


def _text(v):
    """Ép field (str | dict | khác) về string hiển thị, hoặc None."""
    if v is None or isinstance(v, str):
        return v or None
    if isinstance(v, dict):
        for k in _TEXT_KEYS:
            val = v.get(k)
            if isinstance(val, str) and val.strip():
                return val
        return None
    return str(v)


def _int(v):
    """Ép field số (int | '500+' | None) về int, hoặc None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        digits = re.sub(r"[^0-9]", "", v)
        return int(digits) if digits else None
    return None


class HarvestApiSource:
    name = "harvestapi"

    def start_run(self, run_input: dict, token: str) -> tuple[str, str]:
        client = ApifyClient(token)
        run = client.actor(ACTOR_ID).call(run_input=run_input)
        if not run or run.get("status") != "SUCCEEDED":
            raise RuntimeError(f"Apify run failed: {run.get('status') if run else None}")
        return run["id"], run["defaultDatasetId"]

    def iter_items(self, dataset_id: str, token: str, offset: int = 0) -> Iterator[dict]:
        client = ApifyClient(token)
        for item in client.dataset(dataset_id).iterate_items(offset=offset):
            yield item

    def normalize(self, raw: dict) -> CanonicalProfile:
        first = _text(raw.get("firstName"))
        last = _text(raw.get("lastName"))
        full = _text(raw.get("name")) or " ".join(x for x in [first, last] if x) or None

        exp = raw.get("experience") or raw.get("positions") or []
        cur = exp[0] if isinstance(exp, list) and exp else (exp if isinstance(exp, dict) else {})

        url = raw.get("linkedinUrl") or raw.get("url") or raw.get("profileUrl")

        loc_raw = raw.get("location") or raw.get("locationName")
        location = _text(loc_raw)
        country = _text(raw.get("country"))
        if country is None and isinstance(loc_raw, dict):
            country = loc_raw.get("countryFull") or loc_raw.get("country")

        return CanonicalProfile(
            source=self.name,
            linkedin_url=url,
            linkedin_slug=normalize_slug(url),
            full_name=full,
            first_name=first,
            last_name=last,
            headline=_text(raw.get("headline")),
            location=location,
            country=country,
            current_company=_text(cur.get("companyName") or cur.get("company")) or _text(raw.get("companyName")),
            current_title=_text(cur.get("title") or cur.get("position")) or _text(raw.get("jobTitle")),
            connections=_int(raw.get("connectionsCount") or raw.get("connections")),
            followers=_int(raw.get("followersCount") or raw.get("followers")),
            email=_text(raw.get("email")),
            data=raw,
            raw=raw,
        )
