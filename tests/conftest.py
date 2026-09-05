"""
Infrastructure de test.

Principe : aucun test ne doit toucher la base de développement
(data/job_assistant.db). Chaque test reçoit une base SQLite temporaire,
vide, dans laquelle il crée uniquement les données dont il a besoin.

Les services importent SessionLocal dans leur propre namespace
(`from database.db import SessionLocal`), donc on remplace l'attribut
module par module plutôt que dans database.db.
"""

from __future__ import annotations

import importlib
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.model_registry import Base


# Modules dont le SessionLocal doit pointer vers la base de test.
SERVICE_MODULES = (
    "database.seed_skill_catalog",
    "services.ai.interview",
    "services.ai.job_analysis",
    "services.ai.letter_authoring",
    "services.application_service",
    "services.catalog_hygiene",
    "services.interview_history_service",
    "services.cv.selection",
    "services.cv.validation",
    "services.cv.vocabulary",
    "services.esco_import",
    "services.generated_cv_service",
    "services.job_requirements_service",
    "services.job_service",
    "services.market_memory_service",
    "services.matching.analysis",
    "services.profile_import_service",
    "services.profile_service",
    "services.skill_candidate_service",
    "services.skill_catalog_service",
)


@pytest.fixture
def session_factory(tmp_path, monkeypatch):
    """
    Base SQLite temporaire + SessionLocal redirigé dans chaque service.

    Retourne la sessionmaker, pour que les tests puissent insérer
    leurs propres données.
    """

    database_path = tmp_path / "test_job_assistant.db"

    engine = create_engine(
        f"sqlite:///{database_path}",
        echo=False,
    )

    Base.metadata.create_all(engine)

    TestSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    for module_name in SERVICE_MODULES:

        module = importlib.import_module(module_name)

        if hasattr(module, "SessionLocal"):

            monkeypatch.setattr(
                module,
                "SessionLocal",
                TestSessionLocal,
            )

    # Les index dérivés du référentiel sont mis en cache au niveau
    # module : sans remise à zéro, un test hériterait du catalogue
    # d'un test précédent.
    catalogue = importlib.import_module(
        "services.skill_catalog_service"
    )

    catalogue.invalidate_caches()

    yield TestSessionLocal

    engine.dispose()


# ============================================================
# HELPERS DE CREATION DE DONNEES
# ============================================================

def add_catalog_skill(
    session,
    canonical_name: str,
    aliases: list[str] | None = None,
    skill_id: str | None = None,
    category: str = "Test",
    related_skills: list[str] | None = None,
    is_inferable: bool = True,
    is_composite: bool = False,
):
    """Insère une compétence dans le référentiel skill_catalog."""

    from database.models import SkillCatalogDB

    skill = SkillCatalogDB(
        id=skill_id or f"catalog-{canonical_name.lower()}",
        canonical_name=canonical_name,
        category=category,
        subcategory="",
        description="",
        aliases=json.dumps(
            aliases if aliases is not None else [canonical_name],
            ensure_ascii=False,
        ),
        parent_skill_id=None,
        related_skills=json.dumps(
            related_skills or [],
            ensure_ascii=False,
        ),
        is_inferable=is_inferable,
        is_composite=is_composite,
        is_active=True,
    )

    session.add(skill)
    session.commit()

    return skill


def add_candidate(
    session,
    candidate_id: str = "candidate-test",
):
    """Insère un candidat minimal."""

    from database.models import CandidateDB

    candidate = CandidateDB(
        id=candidate_id,
        first_name="Test",
        last_name="Candidat",
        email="test@example.com",
        phone="",
        location="",
        linkedin_url="",
        portfolio_url="",
        summary="",
    )

    session.add(candidate)
    session.commit()

    return candidate


def add_candidate_skill(
    session,
    candidate_id: str,
    name: str,
    skill_id: str | None = None,
    description: str = "",
):
    """Insère une compétence déclarée du Master CV."""

    from database.models import SkillDB

    skill = SkillDB(
        id=skill_id or f"skill-{name.lower().replace(' ', '-')}",
        candidate_id=candidate_id,
        name=name,
        category="Expérience professionnelle",
        level="",
        years_experience=None,
        description=description,
    )

    session.add(skill)
    session.commit()

    return skill


def add_evidence(
    session,
    candidate_id: str,
    skill_id: str,
    description: str,
    evidence_id: str | None = None,
    metric: str = "",
):
    """Insère une preuve rattachée à une compétence."""

    from database.models import EvidenceDB

    evidence = EvidenceDB(
        id=evidence_id or f"evidence-{skill_id}",
        candidate_id=candidate_id,
        skill_id=skill_id,
        experience_id=None,
        achievement_id=None,
        evidence_type="realisation",
        description=description,
        metric=metric,
        context="",
    )

    session.add(evidence)
    session.commit()

    return evidence
