"""
Historique des entretiens IA d'enrichissement du Master CV.

Avant ce module, questions et réponses ne vivaient que dans
`st.session_state` : un rechargement de page les effaçait, l'IA
reposait les mêmes questions d'une session à l'autre, et il était
impossible de revenir compléter une réponse.

Les réponses sont écrites ici **dès l'envoi**, avant toute extraction
de preuves : même si l'analyse échoue, ce que le candidat a dit n'est
jamais perdu.

Ce module ne stocke que la matière brute de l'entretien. Une preuve
validée rejoint EvidenceDB comme n'importe quelle autre preuve — voir
services/profile_service.py.
"""

from __future__ import annotations

from uuid import uuid4

from database.db import SessionLocal
from database.models import InterviewExchangeDB


def save_questions(
    candidate_id: str,
    questions: list,
    target_role: str = "",
) -> list[str]:
    """
    Enregistre les questions générées (sans réponse pour l'instant)
    et retourne leurs identifiants, dans le même ordre.

    `questions` est une liste de services.ai.interview.InterviewQuestion.
    """

    db = SessionLocal()

    try:
        identifiants = []

        for question in questions:

            echange = InterviewExchangeDB(
                id=f"exchange-{uuid4()}",
                candidate_id=candidate_id,
                question=question.question,
                answer="",
                experience_id=question.experience_id,
                experience_label=question.experience_label,
                target_role=target_role,
            )

            db.add(echange)
            identifiants.append(echange.id)

        db.commit()

        return identifiants

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def save_answer(exchange_id: str, answer: str) -> None:
    """Enregistre ou met à jour la réponse d'un échange."""

    db = SessionLocal()

    try:
        echange = db.get(InterviewExchangeDB, exchange_id)

        if echange is None:
            raise ValueError(f"Échange introuvable : {exchange_id}")

        echange.answer = answer

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def get_exchanges(
    candidate_id: str,
    only_answered: bool = False,
) -> list[dict]:
    """
    Historique complet, du plus récent au plus ancien, en dicts de
    primitives — jamais d'objet ORM détaché de sa session.
    """

    db = SessionLocal()

    try:
        requete = (
            db.query(InterviewExchangeDB)
            .filter(InterviewExchangeDB.candidate_id == candidate_id)
            .order_by(InterviewExchangeDB.created_at.desc())
        )

        return [
            {
                "id": echange.id,
                "question": echange.question,
                "answer": echange.answer or "",
                "experience_id": echange.experience_id,
                "experience_label": echange.experience_label or "",
                "target_role": echange.target_role or "",
                "created_at": echange.created_at,
            }
            for echange in requete.all()
            if not only_answered or (echange.answer or "").strip()
        ]

    finally:
        db.close()


def get_asked_questions(candidate_id: str) -> list[str]:
    """
    Toutes les questions déjà posées à ce candidat — transmises au
    générateur pour qu'il n'en repose aucune équivalente.
    """

    db = SessionLocal()

    try:
        return [
            echange.question
            for echange in (
                db.query(InterviewExchangeDB)
                .filter(
                    InterviewExchangeDB.candidate_id == candidate_id
                )
                .all()
            )
        ]

    finally:
        db.close()


def delete_exchange(exchange_id: str) -> None:

    db = SessionLocal()

    try:
        echange = db.get(InterviewExchangeDB, exchange_id)

        if echange is not None:
            db.delete(echange)
            db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
