"""Pydantic schemas for Excel HR Consultancy CV screening app.

These schemas define the strict JSON contracts that Claude Code CLI
responses are validated against. Nothing from a JD or CV file is trusted
until it passes through one of these models.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

_LIST_FIELDS_JD = (
    "required_skills", "preferred_skills", "education_requirements",
    "certifications", "industry_experience", "responsibilities",
    "role_requirements", "languages", "important_keywords",
    "mandatory_requirements", "preferred_requirements",
    "knockout_requirements", "other_requirements",
)

_LIST_FIELDS_CV = (
    "education", "skills", "mandatory_requirements_met",
    "mandatory_requirements_missing", "strengths", "gaps",
    "missing_information",
)

_SCORE_FIELDS_CV = (
    "overall_match_score", "required_skills_score", "preferred_skills_score",
    "experience_score", "role_relevance_score", "education_score",
    "industry_relevance_score",
)


class JobRequirements(BaseModel):
    """Structured requirements extracted from a Job Description.

    This becomes the FIXED evaluation criteria for an entire screening
    session. It is created once, from the JD, and never changes while
    CVs are being scored against it.
    """

    job_title: str = Field(default="Unknown Role")
    department: Optional[str] = None
    location: Optional[str] = None
    work_mode: Optional[str] = None  # Remote / Hybrid / On-site / Unknown
    min_experience_years: Optional[float] = None
    max_experience_years: Optional[float] = None
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    education_requirements: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    industry_experience: List[str] = Field(default_factory=list)
    responsibilities: List[str] = Field(default_factory=list)
    role_requirements: List[str] = Field(default_factory=list)
    notice_period: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    important_keywords: List[str] = Field(default_factory=list)
    mandatory_requirements: List[str] = Field(default_factory=list)
    preferred_requirements: List[str] = Field(default_factory=list)
    knockout_requirements: List[str] = Field(default_factory=list)
    other_requirements: List[str] = Field(default_factory=list)
    notes: Optional[str] = None  # anything genuinely uncertain / not stated

    @field_validator(*_LIST_FIELDS_JD, mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        return v

    @field_validator("min_experience_years", "max_experience_years", mode="before")
    @classmethod
    def _coerce_float(cls, v):
        if v in (None, "", "null", "unknown", "Unknown", "UNKNOWN"):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None


class CandidateAssessment(BaseModel):
    """Claude's structured assessment of one CV against one JobRequirements."""

    source_file: str = ""  # filled in locally by the app, not by Claude

    # Contact & profile -- ONLY ever taken verbatim from the CV text.
    candidate_name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    current_role: Optional[str] = None
    current_company: Optional[str] = None
    current_location: Optional[str] = None
    total_experience_years: Optional[float] = None
    education: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)

    # Assessment (0-100 each)
    overall_match_score: int = Field(ge=0, le=100, default=0)
    required_skills_score: int = Field(ge=0, le=100, default=0)
    preferred_skills_score: int = Field(ge=0, le=100, default=0)
    experience_score: int = Field(ge=0, le=100, default=0)
    role_relevance_score: int = Field(ge=0, le=100, default=0)
    education_score: int = Field(ge=0, le=100, default=0)
    industry_relevance_score: int = Field(ge=0, le=100, default=0)

    mandatory_requirements_met: List[str] = Field(default_factory=list)
    mandatory_requirements_missing: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)

    # Strong Match / Review Recommended / Not a Match
    recommendation: str = "Review Recommended"
    # High / Medium / Low
    confidence: str = "Medium"
    assessment_reason: str = ""

    # Set locally when a file has no extractable text -- never by Claude.
    extraction_note: Optional[str] = None

    @field_validator(*_LIST_FIELDS_CV, mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        return v

    @field_validator(*_SCORE_FIELDS_CV, mode="before")
    @classmethod
    def _coerce_score(cls, v):
        if v is None:
            return 0
        try:
            return max(0, min(100, int(round(float(v)))))
        except (TypeError, ValueError):
            return 0

    @field_validator("total_experience_years", mode="before")
    @classmethod
    def _coerce_experience(cls, v):
        if v in (None, "", "null", "unknown", "Unknown", "UNKNOWN"):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @field_validator("recommendation", mode="before")
    @classmethod
    def _coerce_recommendation(cls, v):
        allowed = {"Strong Match", "Review Recommended", "Not a Match"}
        if v in allowed:
            return v
        return "Review Recommended"

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        allowed = {"High", "Medium", "Low"}
        if v in allowed:
            return v
        return "Medium"
