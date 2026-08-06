"""地点稳定资料提议与 AI 摘要接口 Schema。"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


FACT_KEYS = {
    "normal_hours",
    "services",
    "price_note",
    "contact",
    "access",
    "booking",
    "other",
}


def _validate_fact_key(value: str) -> str:
    value = value.strip()
    if value not in FACT_KEYS:
        raise ValueError(f"不支持的地点资料类型：{value}")
    return value


class LocationFactUpsert(BaseModel):
    fact_key: str = Field(..., max_length=40)
    label: Optional[str] = Field(None, max_length=100)
    value: str = Field(..., min_length=1, max_length=2000)
    sort_order: int = Field(default=0, ge=0, le=1000)
    source_note: Optional[str] = Field(None, max_length=500)

    @field_validator("fact_key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        return _validate_fact_key(value)


class LocationFactProposalCreate(BaseModel):
    upserts: list[LocationFactUpsert] = Field(default_factory=list, max_length=20)
    remove_keys: list[str] = Field(default_factory=list, max_length=20)
    reason: Optional[str] = Field(None, max_length=1000)

    @field_validator("remove_keys")
    @classmethod
    def validate_remove_keys(cls, values: list[str]) -> list[str]:
        return [_validate_fact_key(value) for value in values]

    @model_validator(mode="after")
    def validate_non_empty(self) -> "LocationFactProposalCreate":
        if not self.upserts and not self.remove_keys:
            raise ValueError("至少提交一项资料变更")
        keys = [item.fact_key for item in self.upserts]
        if len(keys) != len(set(keys)):
            raise ValueError("同一份提议中不能重复修改同一资料类型")
        return self


class LocationFactResponse(BaseModel):
    id: int
    location_id: int
    fact_key: str
    label: str
    value: str
    sort_order: int = 0
    source_note: Optional[str] = None
    approved_at: Optional[datetime] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocationFactProposalResponse(BaseModel):
    id: int
    location_id: int
    school_id: int
    proposer_id: int
    changes_json: dict
    reason: Optional[str] = None
    status: str
    reviewer_id: Optional[int] = None
    review_reason: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LocationProposalReview(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000)


class LocationSummarySource(BaseModel):
    source_type: Literal["post", "review", "fact"]
    source_id: int
    title: Optional[str] = None
    snippet: Optional[str] = None
    created_at: Optional[datetime] = None
    author_name: Optional[str] = None
    score: Optional[int] = None
    confirmation_count: int = 0
    refutation_count: int = 0


class LocationSummaryClaim(BaseModel):
    claim_id: str
    text: str
    confidence_level: str
    source_refs: list[dict] = Field(default_factory=list)


class LocationSummaryConflict(BaseModel):
    text: str
    source_refs: list[dict] = Field(default_factory=list)


class LocationSummaryResponse(BaseModel):
    id: Optional[int] = None
    version: Optional[int] = None
    status: str = "insufficient"
    summary_text: Optional[str] = None
    confidence_level: str = "insufficient"
    claims: list[LocationSummaryClaim] = Field(default_factory=list)
    conflicts: list[LocationSummaryConflict] = Field(default_factory=list)
    source_count: int = 0
    generated_at: Optional[datetime] = None
    stale_at: Optional[datetime] = None
    sources: list[LocationSummarySource] = Field(default_factory=list)


class LocationSummaryReview(BaseModel):
    reason: Optional[str] = Field(None, max_length=1000)
