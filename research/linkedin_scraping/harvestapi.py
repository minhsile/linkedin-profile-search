import re
from typing import Iterator
from apify_client import ApifyClient
from src.models import CanonicalProfile
from src.normalize import normalize_slug

ACTOR_ID = "harvestapi/linkedin-profile-search"

_TEXT_KEYS = ("linkedinText", "text", "name", "title", "position", "city", "countryFull", "default")


def _text(v):
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
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        digits = re.sub(r"[^0-9]", "", v)
        return int(digits) if digits else None
    return None


def _sanitize_run_input(run_input: dict) -> dict:
    """Actor yêu cầu các field ID (industryIds, seniorityLevelIds, functionIds,
    yearsOfExperienceIds...) là mảng STRING. Cho phép user viết số -> tự ép sang string."""
    out = dict(run_input)
    for k, v in list(out.items()):
        if k.endswith("Ids") and isinstance(v, list):
            out[k] = [str(x) for x in v]
    return out


class HarvestApiSource:
    name = "harvestapi"

    def start_run(self, run_input: dict, token: str) -> tuple[str, str]:
        """Khởi động actor BẤT ĐỒNG BỘ (không chờ cào xong) để còn theo dõi throughput."""
        client = ApifyClient(token)
        run = client.actor(ACTOR_ID).start(run_input=_sanitize_run_input(run_input))
        return run["id"], run["defaultDatasetId"]

    def poll(self, apify_run_id: str, dataset_id: str, token: str) -> tuple[str, int]:
        """Trả (status, số_item_đã_cào) để đo tốc độ Apify cào theo thời gian."""
        client = ApifyClient(token)
        run = client.run(apify_run_id).get()
        status = (run or {}).get("status", "RUNNING")
        ds = client.dataset(dataset_id).get()
        count = (ds or {}).get("itemCount", 0) or 0
        return status, count

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
