from typing import Iterator
from apify_client import ApifyClient
from lps.models import CanonicalProfile
from lps.normalize import normalize_slug

ACTOR_ID = "harvestapi/linkedin-profile-search"


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
        first = raw.get("firstName")
        last = raw.get("lastName")
        full = raw.get("name") or " ".join(x for x in [first, last] if x) or None
        exp = raw.get("experience") or []
        cur = exp[0] if isinstance(exp, list) and exp else {}
        url = raw.get("linkedinUrl") or raw.get("url") or raw.get("profileUrl")
        return CanonicalProfile(
            source=self.name,
            linkedin_url=url,
            linkedin_slug=normalize_slug(url),
            full_name=full,
            first_name=first,
            last_name=last,
            headline=raw.get("headline"),
            location=raw.get("location") or raw.get("locationName"),
            country=raw.get("country"),
            current_company=cur.get("companyName") or raw.get("companyName"),
            current_title=cur.get("title") or raw.get("jobTitle"),
            connections=raw.get("connectionsCount") or raw.get("connections"),
            followers=raw.get("followersCount") or raw.get("followers"),
            email=raw.get("email"),
            data=raw,
            raw=raw,
        )
