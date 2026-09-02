from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import dataclass

from database.db import SessionLocal
from models.job import JobOfferDB
from models.matching import JobMatchDB


@dataclass
class MarketSkillSummary:
    skill: str
    demand_count: int
    frequency_percent: float
    proven_count: int
    inferred_count: int
    missing_count: int
    gap_rate_percent: float
    priority_score: float
    priority: str


@dataclass
class MarketMemoryResult:
    analyzed_jobs_count: int
    skills: list[MarketSkillSummary]


def _skill_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return " ".join(normalized.casefold().split())


def _priority_label(
    priority_score: float,
    missing_count: int,
    inferred_count: int,
    total_jobs: int,
) -> str:
    if missing_count == 0:
        if inferred_count > 0:
            return "À documenter"
        return "Couvert"

    if total_jobs < 3:
        return "Signal initial"

    if priority_score >= 60:
        return "Prioritaire"

    if priority_score >= 25:
        return "À renforcer"

    return "À surveiller"


def get_market_skill_memory(
    candidate_id: str,
    included_job_statuses: set[str] | None = None,
) -> MarketMemoryResult:
    db = SessionLocal()

    try:
        query = (
            db.query(JobMatchDB, JobOfferDB)
            .join(
                JobOfferDB,
                JobMatchDB.job_offer_id == JobOfferDB.id,
            )
            .filter(JobMatchDB.candidate_id == candidate_id)
        )

        if included_job_statuses is not None:
            query = query.filter(
                JobOfferDB.status.in_(included_job_statuses)
            )

        rows = query.all()
    finally:
        db.close()

    skill_data = defaultdict(
        lambda: {
            "name": "",
            "demand_count": 0,
            "proven_count": 0,
            "inferred_count": 0,
            "missing_count": 0,
        }
    )

    for match, _job_offer in rows:
        statuses = {
            "proven": match.matched_skills or [],
            "inferred": match.inferred_skills or [],
            "missing": match.missing_skills or [],
        }

        for status, skills in statuses.items():
            for skill in skills:
                key = _skill_key(skill)
                data = skill_data[key]

                if not data["name"]:
                    data["name"] = skill

                data["demand_count"] += 1
                data[f"{status}_count"] += 1

    total_jobs = len(rows)
    summaries: list[MarketSkillSummary] = []

    for data in skill_data.values():
        demand_count = data["demand_count"]

        frequency_percent = round(
            demand_count / total_jobs * 100,
            1,
        )

        gap_rate_percent = round(
            data["missing_count"] / demand_count * 100,
            1,
        )

        priority_score = round(
            frequency_percent
            * (
                data["missing_count"] / demand_count
                + (data["inferred_count"] / demand_count) * 0.35
            ),
            1,
        )

        summaries.append(
            MarketSkillSummary(
                skill=data["name"],
                demand_count=demand_count,
                frequency_percent=frequency_percent,
                proven_count=data["proven_count"],
                inferred_count=data["inferred_count"],
                missing_count=data["missing_count"],
                gap_rate_percent=gap_rate_percent,
                priority_score=priority_score,
               priority=_priority_label(
    priority_score=priority_score,
    missing_count=data["missing_count"],
    inferred_count=data["inferred_count"],
    total_jobs=total_jobs,
),
            )
        )

    summaries.sort(
        key=lambda item: (
            item.priority_score,
            item.frequency_percent,
            item.skill.casefold(),
        ),
        reverse=True,
    )

    return MarketMemoryResult(
        analyzed_jobs_count=total_jobs,
        skills=summaries,
    )