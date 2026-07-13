import json
from src.models import CanonicalProfile
from src.normalize import normalize_slug, content_hash
from utilities.database import get_candidate_by_slug, insert_candidate, update_candidate, SCALAR_COLUMNS


def _dedup_list(items: list) -> list:
    seen, out = set(), []
    for it in items:
        key = json.dumps(it, sort_keys=True, ensure_ascii=False, default=str)
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def deep_merge_data(existing: dict, incoming: dict) -> dict:
    out = dict(existing)
    for k, v in incoming.items():
        if isinstance(v, list) and isinstance(out.get(k), list):
            out[k] = _dedup_list(out[k] + v)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge_data(out[k], v)
        elif k not in out or out[k] in (None, "", [], {}):
            out[k] = v
    return out


def _empty(x) -> bool:
    return x is None or x == "" or x == [] or x == {}


def merge_scalars(row: dict, profile: CanonicalProfile) -> dict:
    out = {}
    for col in SCALAR_COLUMNS:
        if col == "linkedin_slug":
            continue
        new = getattr(profile, col)
        if _empty(row.get(col)) and not _empty(new):
            out[col] = new
    return out


def ingest_profile(conn, profile: CanonicalProfile) -> str:
    slug = profile.linkedin_slug or normalize_slug(profile.linkedin_url)
    profile.linkedin_slug = slug
    chash = content_hash(profile.raw or profile.data)

    if not slug:
        insert_candidate(conn, profile, needs_review=True, content_hash=chash)
        conn.commit()
        return "needs_review"

    row = get_candidate_by_slug(conn, slug)
    if row is None:
        insert_candidate(conn, profile, needs_review=False, content_hash=chash)
        conn.commit()
        return "inserted"

    hashes = dict(row["source_hashes"])
    if hashes.get(profile.source) == chash:
        return "unchanged"

    merged_data = deep_merge_data(row["data"], profile.data)
    scalars = merge_scalars(row, profile)
    sources = list(dict.fromkeys(list(row["sources"]) + [profile.source]))
    hashes[profile.source] = chash
    update_candidate(conn, row["id"], scalars=scalars, data=merged_data,
                     sources=sources, source_hashes=hashes)
    conn.commit()
    return "enriched"
