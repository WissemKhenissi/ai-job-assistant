"""
Contrôle déterministe d'un CV ciblé avant envoi.

Aucune IA ici, et c'est délibéré : faire vérifier une IA par une autre
IA remplacerait une garantie par une probabilité. Tout ce qui est
contrôlé ci-dessous est vérifiable exactement, en confrontant le CV
produit à la base :

- chaque ligne affichée porte un `evidence_id` : la preuve doit
  exister et appartenir au candidat ;
- une ligne reformulée par l'IA ne doit contenir aucun chiffre absent
  de la preuve d'origine ;
- le résumé reformulé ne doit contenir aucun chiffre absent du résumé
  du Master CV ;
- toute compétence affichée doit être au statut "proven" pour CETTE
  offre — une compétence déclarée sans preuve, déduite ou manquante
  n'a rien à y faire ;
- les dates des expériences doivent correspondre à celles du Master
  CV, être cohérentes entre elles et ne pas être dans le futur ;
- une même ligne ne doit pas apparaître deux fois.

Le validateur ne modifie rien : il constate. C'est l'appelant qui
décide quoi faire d'un signalement — et l'utilisateur qui tranche.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from database.db import SessionLocal
from database.models import CandidateDB, EvidenceDB, ExperienceDB
from models.matching import JobMatchDB
from models.skill_match import JobSkillMatchDB

from services.text_numbers import numbers_in


# Un signalement bloquant met en cause la véracité du document ; un
# avertissement signale une anomalie qui mérite un coup d'œil sans
# rendre le CV faux pour autant.
BLOQUANT = "bloquant"
AVERTISSEMENT = "avertissement"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = BLOQUANT


@dataclass(frozen=True)
class ValidationReport:
    issues: list[ValidationIssue]

    @property
    def is_valid(self) -> bool:
        """Aucun signalement bloquant — des avertissements restent possibles."""

        return not any(
            issue.severity == BLOQUANT for issue in self.issues
        )

    @property
    def status(self) -> str:
        return "ok" if not self.issues else "avertissements"

    def as_dicts(self) -> list[dict]:
        """Forme sérialisable, pour la trace en base."""

        return [
            {
                "code": issue.code,
                "message": issue.message,
                "severity": issue.severity,
            }
            for issue in self.issues
        ]


def validate_targeted_cv(
    cv,
    candidate_id: str,
    job_offer_id: str,
    today: date | None = None,
) -> ValidationReport:
    """
    Confronte un TargetedCV (déterministe ou reformulé) au Master CV.

    Ne lève jamais d'exception : une anomalie devient un signalement,
    pas un plantage — un CV douteux doit pouvoir être montré à
    l'utilisateur avec ses réserves, plutôt que disparaître.
    """

    today = today or date.today()

    issues: list[ValidationIssue] = []

    db = SessionLocal()

    try:

        # ----------------------------------------------------
        # PREUVES ET CHIFFRES
        # ----------------------------------------------------

        textes_vus: set[str] = set()

        for experience in cv.experiences:

            for ligne in experience.lines:

                preuve = db.get(EvidenceDB, ligne.evidence_id)

                if preuve is None:
                    issues.append(
                        ValidationIssue(
                            code="preuve_introuvable",
                            message=(
                                "Ligne sans preuve correspondante dans "
                                f"le Master CV : « {ligne.text[:60]} »"
                            ),
                        )
                    )
                    continue

                if preuve.candidate_id != candidate_id:
                    issues.append(
                        ValidationIssue(
                            code="preuve_autre_candidat",
                            message=(
                                "Ligne rattachée à la preuve d'un autre "
                                f"candidat : « {ligne.text[:60]} »"
                            ),
                        )
                    )
                    continue

                chiffres_inventes = numbers_in(ligne.text) - numbers_in(
                    preuve.description
                )

                if chiffres_inventes:
                    issues.append(
                        ValidationIssue(
                            code="chiffre_invente",
                            message=(
                                "Chiffre absent de la preuve d'origine "
                                f"({', '.join(sorted(chiffres_inventes))}) "
                                f"dans : « {ligne.text[:60]} »"
                            ),
                        )
                    )

                cle = " ".join(ligne.text.casefold().split())

                if cle in textes_vus:
                    issues.append(
                        ValidationIssue(
                            code="ligne_en_double",
                            message=(
                                f"Ligne répétée : « {ligne.text[:60]} »"
                            ),
                            severity=AVERTISSEMENT,
                        )
                    )

                textes_vus.add(cle)

        # ----------------------------------------------------
        # RESUME
        # ----------------------------------------------------

        candidate = db.get(CandidateDB, candidate_id)

        if candidate is not None and cv.summary:

            chiffres_inventes = numbers_in(cv.summary) - numbers_in(
                candidate.summary or ""
            )

            if chiffres_inventes:
                issues.append(
                    ValidationIssue(
                        code="chiffre_invente_resume",
                        message=(
                            "Le résumé contient des chiffres absents du "
                            "Master CV : "
                            f"{', '.join(sorted(chiffres_inventes))}"
                        ),
                    )
                )

        # ----------------------------------------------------
        # COMPETENCES : SEUL LE PROUVE A SA PLACE
        # ----------------------------------------------------

        job_match = (
            db.query(JobMatchDB)
            .filter(
                JobMatchDB.candidate_id == candidate_id,
                JobMatchDB.job_offer_id == job_offer_id,
            )
            .one_or_none()
        )

        if job_match is None:
            issues.append(
                ValidationIssue(
                    code="analyse_absente",
                    message=(
                        "Aucune analyse de matching trouvée pour cette "
                        "offre : impossible de vérifier les compétences."
                    ),
                    severity=AVERTISSEMENT,
                )
            )

        else:

            statuts = {
                row.skill: row.status
                for row in (
                    db.query(JobSkillMatchDB)
                    .filter(JobSkillMatchDB.job_match_id == job_match.id)
                    .all()
                )
            }

            for competence in cv.skills:

                statut = statuts.get(competence)

                if statut is None:
                    issues.append(
                        ValidationIssue(
                            code="competence_hors_analyse",
                            message=(
                                f"« {competence} » figure au CV sans "
                                "apparaître dans l'analyse de l'offre."
                            ),
                        )
                    )

                elif statut != "proven":
                    issues.append(
                        ValidationIssue(
                            code="competence_non_prouvee",
                            message=(
                                f"« {competence} » est affichée alors "
                                f"qu'elle est au statut « {statut} » : "
                                "seule une compétence prouvée peut "
                                "figurer au CV."
                            ),
                        )
                    )

        # ----------------------------------------------------
        # DATES
        # ----------------------------------------------------

        for experience in cv.experiences:

            source = db.get(ExperienceDB, experience.experience_id)

            if source is None:
                issues.append(
                    ValidationIssue(
                        code="experience_introuvable",
                        message=(
                            "Expérience absente du Master CV : "
                            f"{experience.job_title} — {experience.company}"
                        ),
                    )
                )
                continue

            if (
                experience.start_date != source.start_date
                or experience.end_date != source.end_date
            ):
                issues.append(
                    ValidationIssue(
                        code="dates_divergentes",
                        message=(
                            "Dates différentes de celles du Master CV "
                            f"pour {experience.job_title} — "
                            f"{experience.company}."
                        ),
                    )
                )

            if (
                experience.end_date is not None
                and experience.end_date < experience.start_date
            ):
                issues.append(
                    ValidationIssue(
                        code="dates_incoherentes",
                        message=(
                            "Date de fin antérieure à la date de début "
                            f"pour {experience.job_title} — "
                            f"{experience.company}."
                        ),
                    )
                )

            if experience.start_date > today:
                issues.append(
                    ValidationIssue(
                        code="date_future",
                        message=(
                            "Date de début dans le futur pour "
                            f"{experience.job_title} — "
                            f"{experience.company}."
                        ),
                    )
                )

        return ValidationReport(issues=issues)

    finally:

        db.close()
