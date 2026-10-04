"""Explicit source evidence and partial metadata changes, independent of fetching."""
from datetime import date
import re
from typing import Literal
from urllib.parse import unquote, urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def article_identity(value):
    result = {}
    for key in ("doi", "pmid", "pmcid"):
        raw = value.get(key)
        if raw:
            text = str(raw).strip()
            if key == "doi":
                text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text, flags=re.I).lower()
                if not re.fullmatch(r"10\.\d{4,9}/[^\s\"<>]+", text):
                    raise ValueError("A complete DOI is required")
            elif key == "pmid":
                if not text.isdigit() or not 1 <= len(text) <= 12:
                    raise ValueError("A numeric PMID is required")
            else:
                text = text.upper()
                if not re.fullmatch(r"PMC\d{1,12}", text):
                    raise ValueError("A complete PMCID is required")
            result[key] = text
    return result


def identity_from_url(url):
    parts = urlparse(url or "")
    path = unquote(parts.path).strip("/")
    if parts.hostname in ("doi.org", "dx.doi.org"):
        return article_identity({"doi": path})
    if parts.hostname in ("europepmc.org", "www.europepmc.org"):
        match = re.fullmatch(r"article/(MED|PMC)/([A-Za-z0-9]+)", path, re.I)
        if match:
            return article_identity({"pmid" if match[1].upper() == "MED" else "pmcid": match[2]})
    if parts.hostname == "pubmed.ncbi.nlm.nih.gov" and path.isdigit():
        return article_identity({"pmid": path})
    if parts.hostname in ("pmc.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov"):
        match = re.search(r"(?:^|/)articles/(PMC\d+)(?:/|$)", path, re.I)
        if match:
            return article_identity({"pmcid": match[1]})
    return {}


class SourceTarget(StrictModel):
    register_id: str = Field(pattern=r"^[A-Z]\d{2}$")
    canonical_url: str | None = Field(default=None, max_length=2000)
    pinned_source_id: str | None = Field(default=None, max_length=120)
    doi: str | None = Field(default=None, max_length=500)
    pmid: str | None = Field(default=None, max_length=12)
    pmcid: str | None = Field(default=None, max_length=15)
    edition: str | None = Field(default=None, min_length=1, max_length=160)
    original_sha256: str | None = Field(default=None, min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    topic_ids: list[str] = Field(default_factory=list, max_length=100)
    locators: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("edition", mode="before")
    @classmethod
    def acquired_edition(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def identify(self):
        if (self.edition is None) != (self.original_sha256 is None):
            raise ValueError("An acquired version requires both its edition and original SHA256")
        identities = article_identity(self.model_dump())
        for key, value in identities.items():
            setattr(self, key, value)
        if self.canonical_url:
            parts = urlparse(self.canonical_url)
            if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
                raise ValueError("A public canonical HTTPS URL is required")
            # If the canonical URL encodes a different article, never OR-match it.
            inferred = identity_from_url(self.canonical_url)
            if any(key in identities and identities[key] != value for key, value in inferred.items()):
                raise ValueError("Article identifiers conflict with the canonical URL")
        if not self.canonical_url and not identities and not self.pinned_source_id:
            raise ValueError("Specify an exact publication, not only its register family")
        return self


class ReviewedEvidence(StrictModel):
    url: str = Field(min_length=1, max_length=2000)
    locator: str = Field(min_length=1, max_length=1000)
    finding: str = Field(min_length=1, max_length=4000)
    checked_on: date
    inspected: Literal[True]
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @field_validator("url")
    @classmethod
    def public_evidence_url(cls, value):
        parts = urlparse(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
            raise ValueError("Use the public canonical evidence URL")
        return value

    @field_validator("locator", "finding")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Reviewed evidence cannot be blank")
        return value.strip()

    @field_validator("checked_on")
    @classmethod
    def checked_date(cls, value):
        if value > date.today():
            raise ValueError("An evidence check cannot be in the future")
        return value


class SourceChanges(StrictModel):
    # Optional fields are a patch, never default claims that no notice exists.
    publication_status: Literal["unknown", "final", "draft", "preprint", "commentary"] | None = None
    publication_date: date | None = None
    revision_date: date | None = None
    latest_final_verified: bool | None = None
    content_reviewed: bool | None = None
    review_due: date | None = None
    correction: str | None = Field(default=None, max_length=4000)
    retracted: bool | None = None
    superseded: bool | None = None
    repository_removed: bool | None = None
    access_changed: bool | None = None
    supersedes: list[str] | None = Field(default=None, max_length=100)
    replaced_topics: list[str] | None = Field(default=None, max_length=100)
    excluded_pages: list[int] | None = Field(default=None, max_length=2000)

    @field_validator("publication_status", "latest_final_verified", "content_reviewed", "retracted", "superseded",
                     "repository_removed", "access_changed", "supersedes", "replaced_topics", "excluded_pages", mode="before")
    @classmethod
    def explicit_states(cls, value):
        if value is None:
            raise ValueError("Omit an unreviewed state instead of publishing null")
        return value

    @model_validator(mode="after")
    def validate_states(self):
        if self.latest_final_verified and self.publication_status != "final":
            raise ValueError("Latest-final verification requires explicit final status")
        if self.latest_final_verified and (self.retracted or self.superseded or self.repository_removed):
            raise ValueError("Retracted, removed or superseded content cannot be verified latest final")
        if self.excluded_pages and any(page < 1 for page in self.excluded_pages):
            raise ValueError("Excluded pages start at 1")
        if self.correction is not None and not self.correction.strip():
            raise ValueError("Use a correction reference or null, not blank text")
        return self
