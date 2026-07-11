from lps.ingest import ingest_profile, deep_merge_data, merge_scalars
from lps.models import CanonicalProfile


def test_deep_merge_dedups_lists():
    a = {"experience": [{"c": "Shopee"}], "skills": ["a"]}
    b = {"experience": [{"c": "Shopee"}, {"c": "Grab"}], "skills": ["a", "b"]}
    out = deep_merge_data(a, b)
    assert out["experience"] == [{"c": "Shopee"}, {"c": "Grab"}]
    assert out["skills"] == ["a", "b"]


def test_merge_scalars_fills_only_missing():
    row = {"full_name": "An Nguyen", "email": None, "headline": ""}
    p = CanonicalProfile(source="x", full_name="OVERWRITE?", email="a@b.com", headline="Head")
    out = merge_scalars(row, p)
    assert out == {"email": "a@b.com", "headline": "Head"}


def test_insert_then_enrich_then_unchanged(conn):
    p1 = CanonicalProfile(source="harvestapi",
        linkedin_url="https://linkedin.com/in/an-nguyen-123",
        full_name="An Nguyen", current_company="Shopee",
        data={"experience": [{"companyName": "Shopee"}]})
    assert ingest_profile(conn, p1) == "inserted"

    p2 = CanonicalProfile(source="other",
        linkedin_url="https://vn.linkedin.com/in/An-Nguyen-123/",
        full_name="An Nguyen", email="a@shopee.com", current_company="Shopee",
        data={"education": [{"school": "UEH"}]})
    assert ingest_profile(conn, p2) == "enriched"

    assert ingest_profile(conn, p2) == "unchanged"


def test_missing_slug_needs_review(conn):
    p = CanonicalProfile(source="harvestapi", full_name="Bich Tran", current_company="FPT")
    assert ingest_profile(conn, p) == "needs_review"
