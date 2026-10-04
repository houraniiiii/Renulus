from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Rights(BaseModel):
    """Permission is per operation; public access never implies processing rights."""

    model_config = ConfigDict(extra="forbid")
    display: bool = False
    cache: bool = False
    index: bool = False
    embedding: bool = False
    model_input: bool = False
    derivation: bool = False
    evaluation: bool = False
    redistribution: bool = False
    licence: str = "unverified"
    permission_reference: str = ""
    attribution: str = ""


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = "R02"
    source_owner: str = "User"
    canonical_url: str | None = None
    access_class: str = "user-owned"
    edition: str | None = None
    publication_date: str | None = None
    revision_date: str | None = None
    received_at: str | None = None
    retrieved_at: str | None = None
    checked_at: str | None = None
    review_due: str | None = None
    publication_status: Literal["final", "draft", "preprint", "commentary", "unknown"] = "unknown"
    latest_final_verified: bool = False
    content_reviewed: bool = False
    retracted: bool = False
    superseded: bool = False
    repository_removed: bool = False
    access_changed: bool = False
    correction: str | None = None
    supersedes: list[str] = Field(default_factory=list)
    replaced_topics: list[str] = Field(default_factory=list)
    excluded_pages: list[int] = Field(default_factory=list)
    topic_ids: list[str] = Field(default_factory=list)
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    jurisdiction: str | None = None
    collection_section: str | None = None
    collection_chapter: str | None = None
    asset_role: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def own_text_rights() -> Rights:
    return Rights(display=True, cache=True, index=True, embedding=True, model_input=True,
                  derivation=True, licence="user-owned",
                  permission_reference="User deliberately added their own text to the library")
