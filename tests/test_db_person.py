from lps.db import get_person_by_slug, insert_person, update_person
from lps.models import CanonicalProfile


def _profile(**kw):
    base = dict(source="harvestapi", linkedin_slug="an-nguyen-123",
                linkedin_url="https://linkedin.com/in/an-nguyen-123",
                full_name="An Nguyen", current_company="Shopee",
                data={"experience": [{"companyName": "Shopee"}]})
    base.update(kw)
    return CanonicalProfile(**base)


def test_insert_and_get(conn):
    pid = insert_person(conn, _profile(), needs_review=False, content_hash="h1",
                        norm_name="an nguyen", norm_company="shopee")
    row = get_person_by_slug(conn, "an-nguyen-123")
    assert str(row["id"]) == pid
    assert row["full_name"] == "An Nguyen"
    assert row["sources"] == ["harvestapi"]
    assert row["source_hashes"] == {"harvestapi": "h1"}


def test_get_missing_returns_none(conn):
    assert get_person_by_slug(conn, "nope") is None


def test_update_person(conn):
    pid = insert_person(conn, _profile(), needs_review=False, content_hash="h1",
                        norm_name="an nguyen", norm_company="shopee")
    update_person(conn, pid, scalars={"email": "a@shopee.com"},
                  data={"experience": [{"companyName": "Shopee"}], "email": "a@shopee.com"},
                  sources=["harvestapi", "other"],
                  source_hashes={"harvestapi": "h1", "other": "h2"})
    row = get_person_by_slug(conn, "an-nguyen-123")
    assert row["email"] == "a@shopee.com"
    assert set(row["sources"]) == {"harvestapi", "other"}
