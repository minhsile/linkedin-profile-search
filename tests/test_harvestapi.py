from lps.sources.harvestapi import HarvestApiSource


def test_normalize_maps_core_fields():
    src = HarvestApiSource()
    raw = {
        "firstName": "An",
        "lastName": "Nguyen",
        "headline": "Marketing Manager at Shopee",
        "linkedinUrl": "https://www.linkedin.com/in/an-nguyen-123/",
        "location": "Ho Chi Minh City",
        "experience": [{"companyName": "Shopee", "title": "Marketing Manager"}],
    }
    p = src.normalize(raw)
    assert p.source == "harvestapi"
    assert p.linkedin_slug == "an-nguyen-123"
    assert p.full_name == "An Nguyen"
    assert p.current_company == "Shopee"
    assert p.current_title == "Marketing Manager"
    assert p.data["experience"][0]["companyName"] == "Shopee"
    assert p.raw == raw


def test_normalize_handles_missing_url():
    src = HarvestApiSource()
    p = src.normalize({"firstName": "Bich", "lastName": "Tran"})
    assert p.linkedin_slug is None
    assert p.full_name == "Bich Tran"


def test_normalize_coerces_dict_location():
    src = HarvestApiSource()
    raw = {
        "firstName": "An",
        "lastName": "Nguyen",
        "linkedinUrl": "https://www.linkedin.com/in/an-nguyen-123/",
        "location": {"linkedinText": "Ho Chi Minh City", "city": "Ho Chi Minh City",
                     "countryFull": "Vietnam"},
        "connections": "500+",
    }
    p = src.normalize(raw)
    assert p.location == "Ho Chi Minh City"
    assert p.country == "Vietnam"
    assert p.connections == 500


def test_normalize_coerces_dict_company():
    src = HarvestApiSource()
    raw = {
        "linkedinUrl": "https://www.linkedin.com/in/x-y-1/",
        "experience": [{"companyName": {"name": "Grab"}, "position": "PM"}],
    }
    p = src.normalize(raw)
    assert p.current_company == "Grab"
    assert p.current_title == "PM"
