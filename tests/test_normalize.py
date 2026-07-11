from lps.normalize import normalize_slug, normalize_text, content_hash


def test_slug_basic():
    assert normalize_slug("https://www.linkedin.com/in/An-Nguyen-123/") == "an-nguyen-123"


def test_slug_country_subdomain_and_query():
    url = "https://vn.linkedin.com/in/An-Nguyen-123/?trk=abc"
    assert normalize_slug(url) == "an-nguyen-123"


def test_slug_none_when_no_in_path():
    assert normalize_slug("https://linkedin.com/company/acme") is None
    assert normalize_slug(None) is None


def test_normalize_text_unaccent_lower_collapse():
    assert normalize_text("  Nguyễn   Văn An ") == "nguyen van an"
    assert normalize_text(None) is None


def test_content_hash_stable_and_order_independent():
    a = content_hash({"x": 1, "y": 2})
    b = content_hash({"y": 2, "x": 1})
    assert a == b
    assert a != content_hash({"x": 1, "y": 3})
