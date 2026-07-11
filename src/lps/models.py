from pydantic import BaseModel, Field


class CanonicalProfile(BaseModel):
    source: str
    linkedin_url: str | None = None
    linkedin_slug: str | None = None
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    headline: str | None = None
    location: str | None = None
    country: str | None = None
    current_company: str | None = None
    current_title: str | None = None
    connections: int | None = None
    followers: int | None = None
    email: str | None = None
    data: dict = Field(default_factory=dict)
    raw: dict = Field(default_factory=dict)
