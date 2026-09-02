from database.db import SessionLocal
from database.models import (
    CandidateDB,
    ExperienceDB,
    AchievementDB,
    SkillDB,
    EvidenceDB,
)


def get_candidate():
    db = SessionLocal()

    try:
        return db.query(CandidateDB).first()
    finally:
        db.close()


def get_experiences():
    db = SessionLocal()

    try:
        return db.query(ExperienceDB).all()
    finally:
        db.close()


def get_achievements(experience_id):
    db = SessionLocal()

    try:
        return (
            db.query(AchievementDB)
            .filter(AchievementDB.experience_id == experience_id)
            .all()
        )
    finally:
        db.close()


def get_skills(candidate_id):
    db = SessionLocal()

    try:
        return (
            db.query(SkillDB)
            .filter(SkillDB.candidate_id == candidate_id)
            .all()
        )
    finally:
        db.close()


def get_evidence(candidate_id):
    db = SessionLocal()

    try:
        return (
            db.query(EvidenceDB)
            .filter(EvidenceDB.candidate_id == candidate_id)
            .all()
        )
    finally:
        db.close()