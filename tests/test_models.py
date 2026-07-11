from lps.models import CanonicalProfile


def test_canonical_profile_defaults():
    p = CanonicalProfile(source="harvestapi", full_name="An Nguyen")
    assert p.source == "harvestapi"
    assert p.data == {}
    assert p.raw == {}
    assert p.email is None
