"""Strict Pydantic models for the model's extraction response."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class SkillEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    skill: Annotated[str, Field(min_length=1, max_length=80)]
    evidence: Annotated[str, Field(min_length=1, max_length=400)]


class ExtractionResult(BaseModel):
    """Facts extracted from a candidate document and job description."""

    model_config = ConfigDict(extra="forbid", strict=True)

    candidate_document_is_job_related: bool
    job_description_is_job_related: bool
    resume_skills: list[SkillEvidence]
    required_skills: list[str]
    preferred_skills: list[str]
    years_experience: Annotated[float | None, Field(ge=0, le=80)]
    minimum_years_experience: Annotated[float | None, Field(ge=0, le=80)]
    candidate_summary: Annotated[str, Field(max_length=800)]

