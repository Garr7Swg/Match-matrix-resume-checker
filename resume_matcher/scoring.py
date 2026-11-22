"""Deterministic skill and experience comparison."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .models import ExtractionResult


WEIGHTS = {"Required skills": 70.0, "Preferred skills": 20.0, "Experience": 10.0}
ALIASES = {
    "js": "javascript",
    "nodejs": "node js",
    "react js": "react",
    "k8s": "kubernetes",
    "postgres": "postgresql",
    "ml": "machine learning",
    "ci cd": "continuous integration continuous delivery",
    "amazon web services": "aws",
    "google cloud": "google cloud platform",
    "gcp": "google cloud platform",
    "c plus plus": "cplusplus",
    "c sharp": "csharp",
}


def normalize_skill(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = value.replace("c++", "cplusplus").replace("c#", "csharp")
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return ALIASES.get(value, value)


@dataclass(frozen=True)
class SkillMatch:
    skill: str
    status: str


@dataclass(frozen=True)
class MatchReport:
    overall_score: float
    required_score: float | None
    preferred_score: float | None
    experience_score: float | None
    experience_years: float | None
    minimum_experience_years: float | None
    required: tuple[SkillMatch, ...]
    preferred: tuple[SkillMatch, ...]
    matched_skills: tuple[str, ...]
    missing_skills: tuple[str, ...]
    weight_shares: dict[str, float]


def _skill_dimension(skills: list[str], resume_skills: set[str]) -> tuple[float | None, tuple[SkillMatch, ...]]:
    unique: dict[str, str] = {}
    for skill in skills:
        canonical = normalize_skill(skill)
        if canonical:
            unique.setdefault(canonical, skill.strip())
    if not unique:
        return None, ()
    rows = tuple(
        SkillMatch(name, "Matched" if canonical in resume_skills else "Missing")
        for canonical, name in unique.items()
    )
    matched = sum(row.status == "Matched" for row in rows)
    return round(matched / len(rows) * 100, 1), rows


def calculate_match(extraction: ExtractionResult) -> MatchReport:
    resume_skill_set = {
        normalize_skill(item.skill)
        for item in extraction.resume_skills
        if normalize_skill(item.skill)
    }
    required_score, required = _skill_dimension(extraction.required_skills, resume_skill_set)
    preferred_score, preferred = _skill_dimension(extraction.preferred_skills, resume_skill_set)

    experience_score: float | None = None
    if extraction.minimum_years_experience is not None:
        if extraction.minimum_years_experience == 0:
            experience_score = 100.0
        elif extraction.years_experience is None:
            experience_score = 0.0
        else:
            experience_score = round(
                min(extraction.years_experience / extraction.minimum_years_experience, 1.0) * 100,
                1,
            )

    active: list[tuple[str, float, float]] = []
    if required_score is not None:
        active.append(("Required skills", WEIGHTS["Required skills"], required_score))
    if preferred_score is not None:
        active.append(("Preferred skills", WEIGHTS["Preferred skills"], preferred_score))
    if experience_score is not None:
        active.append(("Experience", WEIGHTS["Experience"], experience_score))
    if not active:
        raise ValueError("No measurable job criteria were extracted")

    active_weight_total = sum(weight for _, weight, _ in active)
    shares = {name: round(weight / active_weight_total * 100, 1) for name, weight, _ in active}
    overall = round(sum(weight * score for _, weight, score in active) / active_weight_total, 1)

    required_rows = [row for row in required if row.status == "Matched"]
    preferred_rows = [row for row in preferred if row.status == "Matched"]
    matched_skills = tuple(row.skill for row in required_rows + preferred_rows)
    missing_skills = tuple(
        row.skill for row in required + preferred if row.status == "Missing"
    )

    return MatchReport(
        overall_score=overall,
        required_score=required_score,
        preferred_score=preferred_score,
        experience_score=experience_score,
        experience_years=extraction.years_experience,
        minimum_experience_years=extraction.minimum_years_experience,
        required=required,
        preferred=preferred,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        weight_shares=shares,
    )

