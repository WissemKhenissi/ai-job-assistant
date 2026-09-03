"""
Trace des CV générés : ce qui a été retenu, écarté, et pourquoi.

Le fichier exporté ne dit rien des décisions qui l'ont produit. Sans
cette trace, impossible de répondre plus tard à « pourquoi cette
expérience figure-t-elle dans ce CV et pas celle-là ? », ni de
comparer deux générations successives.

Un CV généré reste une **vue datée** du Master CV pour une offre
donnée — jamais un profil concurrent. Rien n'est recopié ici du
contenu du CV : uniquement les identifiants des éléments retenus, ce
qui garantit qu'on relit toujours le Master CV comme source.
"""

from __future__ import annotations

from uuid import uuid4

from database.db import SessionLocal
from database.models import GeneratedCVDB


def record_generated_cv(
    candidate_id: str,
    job_offer_id: str,
    cv,
    mode: str = "deterministe",
    llm_model: str = "",
    match_score: float = 0.0,
    validation_status: str = "ok",
    validation_issues: list | None = None,
) -> str:
    """
    Enregistre les décisions d'une génération et retourne son
    identifiant.

    `cv` est un TargetedCV : on n'en conserve que les identifiants et
    les noms de compétences, pas les textes.
    """

    db = SessionLocal()

    try:

        exclues = (
            [
                {"skill": nom, "motif": "declaree_sans_preuve"}
                for nom in cv.declared_skills
            ]
            + [
                {"skill": nom, "motif": "seulement_deduite"}
                for nom in cv.inferred_skills
            ]
            + [
                {"skill": nom, "motif": "absente_du_master_cv"}
                for nom in cv.missing_skills
            ]
        )

        trace = GeneratedCVDB(
            id=f"generated-cv-{uuid4()}",
            candidate_id=candidate_id,
            job_offer_id=job_offer_id,
            mode=mode,
            llm_model=llm_model,
            selected_experience_ids=[
                experience.experience_id for experience in cv.experiences
            ],
            selected_evidence_ids=[
                ligne.evidence_id
                for experience in cv.experiences
                for ligne in experience.lines
            ],
            selected_achievement_ids=[
                realisation.achievement_id
                for experience in cv.experiences
                for realisation in experience.achievement_lines
            ],
            selected_skills=list(cv.skills),
            excluded_skills=exclues,
            match_score_at_generation=match_score,
            validation_status=validation_status,
            validation_issues=validation_issues or [],
        )

        db.add(trace)
        db.commit()

        return trace.id

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_generated_cvs(
    candidate_id: str,
    job_offer_id: str | None = None,
) -> list[dict]:
    """
    Historique des générations, de la plus récente à la plus ancienne,
    en dicts de primitives — jamais d'objet ORM détaché.
    """

    db = SessionLocal()

    try:

        requete = db.query(GeneratedCVDB).filter(
            GeneratedCVDB.candidate_id == candidate_id
        )

        if job_offer_id is not None:
            requete = requete.filter(
                GeneratedCVDB.job_offer_id == job_offer_id
            )

        return [
            {
                "id": trace.id,
                "job_offer_id": trace.job_offer_id,
                "mode": trace.mode,
                "llm_model": trace.llm_model or "",
                "selected_experience_ids": list(
                    trace.selected_experience_ids or []
                ),
                "selected_evidence_ids": list(
                    trace.selected_evidence_ids or []
                ),
                "selected_achievement_ids": list(
                    trace.selected_achievement_ids or []
                ),
                "selected_skills": list(trace.selected_skills or []),
                "excluded_skills": list(trace.excluded_skills or []),
                "match_score_at_generation": trace.match_score_at_generation,
                "validation_status": trace.validation_status,
                "validation_issues": list(trace.validation_issues or []),
                "created_at": trace.created_at,
            }
            for trace in requete.order_by(
                GeneratedCVDB.created_at.desc()
            ).all()
        ]

    finally:
        db.close()
