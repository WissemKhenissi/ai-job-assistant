"""
Mesure de la qualité du moteur de matching.

Deux couches sont évaluées séparément, car elles échouent
différemment :

1. EXTRACTION — à partir du texte d'une annonce, quelles compétences
   le moteur considère-t-il comme demandées ? On mesure precision,
   recall et faux positifs face aux compétences réellement attendues.

2. STATUTS — pour chaque compétence demandée, le moteur répond
   proven / declared / inferred / missing. On compare au statut
   attendu.

Toutes les erreurs ne se valent pas. Sur ce projet, la pire est la
SURÉVALUATION : le moteur affirme une compétence mieux établie
qu'elle ne l'est. C'est elle qui produirait un CV malhonnête. Elle est
donc comptée et affichée à part, jamais noyée dans un taux global.

Usage :

    .venv/Scripts/python.exe -m evaluation.evaluate
    .venv/Scripts/python.exe -m evaluation.evaluate --detail
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from services.job_requirements_service import extract_required_skills
from services.matching import analyze_candidate_against_skills
from services.matching.normalization import _canonical_skill_name


DATASET_DIR = Path(__file__).resolve().parent / "dataset"

CANDIDATE_ID = "candidate-demo"


# Du plus faible au plus fort niveau d'affirmation.
# Sert à décider si une erreur est une surévaluation ou une
# sous-évaluation.
STATUS_STRENGTH = {
    "missing": 0,
    "inferred": 1,
    "declared": 2,
    "proven": 3,
}


# ============================================================
# CHARGEMENT DU DATASET
# ============================================================

@dataclass
class EvaluationCase:
    slug: str
    titre: str
    texte: str
    competences_attendues: list[str]
    statuts_attendus: dict[str, str]
    revise_par_humain: bool
    commentaire: str = ""


def load_cases() -> list[EvaluationCase]:
    """Charge tous les cas du dataset."""

    cases: list[EvaluationCase] = []

    if not DATASET_DIR.exists():
        return cases

    for case_dir in sorted(DATASET_DIR.iterdir()):

        if not case_dir.is_dir():
            continue

        annonce_path = case_dir / "annonce.txt"
        attendu_path = case_dir / "attendu.json"

        if not annonce_path.exists() or not attendu_path.exists():
            print(
                f"  ! {case_dir.name} ignoré : "
                "annonce.txt ou attendu.json manquant"
            )
            continue

        attendu = json.loads(
            attendu_path.read_text(encoding="utf-8")
        )

        cases.append(
            EvaluationCase(
                slug=case_dir.name,
                titre=attendu.get("titre", case_dir.name),
                texte=annonce_path.read_text(encoding="utf-8"),
                competences_attendues=attendu.get(
                    "competences_attendues",
                    [],
                ),
                statuts_attendus=attendu.get(
                    "statuts_attendus",
                    {},
                ),
                revise_par_humain=attendu.get(
                    "revise_par_humain",
                    False,
                ),
                commentaire=attendu.get("commentaire", ""),
            )
        )

    return cases


# ============================================================
# RESULTATS
# ============================================================

@dataclass
class ExtractionResult:
    trouvees_et_attendues: list[str] = field(default_factory=list)
    faux_positifs: list[str] = field(default_factory=list)
    oubliees: list[str] = field(default_factory=list)

    @property
    def precision(self) -> float | None:
        detectees = (
            len(self.trouvees_et_attendues)
            + len(self.faux_positifs)
        )

        if detectees == 0:
            return None

        return len(self.trouvees_et_attendues) / detectees

    @property
    def recall(self) -> float | None:
        attendues = (
            len(self.trouvees_et_attendues)
            + len(self.oubliees)
        )

        if attendues == 0:
            return None

        return len(self.trouvees_et_attendues) / attendues


@dataclass
class StatusError:
    competence: str
    attendu: str
    obtenu: str

    @property
    def est_surevaluation(self) -> bool:
        return (
            STATUS_STRENGTH.get(self.obtenu, 0)
            > STATUS_STRENGTH.get(self.attendu, 0)
        )


@dataclass
class CaseResult:
    case: EvaluationCase
    extraction: ExtractionResult
    statuts_corrects: int = 0
    erreurs_statut: list[StatusError] = field(default_factory=list)


# ============================================================
# EVALUATION D'UN CAS
# ============================================================

def evaluate_case(case: EvaluationCase) -> CaseResult:

    # --------------------------------------------------------
    # COUCHE 1 : EXTRACTION
    # --------------------------------------------------------
    #
    # La comparaison se fait sur la forme canonique : "Project
    # Management" et "Gestion de projet" désignent la même
    # compétence et ne doivent pas compter comme un écart.

    detectees = extract_required_skills(case.texte)

    canon_detectees = {
        _canonical_skill_name(skill): skill
        for skill in detectees
    }

    canon_attendues = {
        _canonical_skill_name(skill): skill
        for skill in case.competences_attendues
    }

    extraction = ExtractionResult(
        trouvees_et_attendues=sorted(
            canon_attendues[canon]
            for canon in canon_detectees.keys()
            & canon_attendues.keys()
        ),
        faux_positifs=sorted(
            canon_detectees[canon]
            for canon in canon_detectees.keys()
            - canon_attendues.keys()
        ),
        oubliees=sorted(
            canon_attendues[canon]
            for canon in canon_attendues.keys()
            - canon_detectees.keys()
        ),
    )

    result = CaseResult(case=case, extraction=extraction)

    # --------------------------------------------------------
    # COUCHE 2 : STATUTS
    # --------------------------------------------------------
    #
    # On analyse sur les compétences ATTENDUES et non sur celles
    # détectées : sinon une erreur d'extraction masquerait la
    # qualité du matching lui-même.

    if not case.statuts_attendus:
        return result

    skills_a_analyser = (
        case.competences_attendues
        or list(case.statuts_attendus.keys())
    )

    if not skills_a_analyser:
        return result

    matching = analyze_candidate_against_skills(
        candidate_id=CANDIDATE_ID,
        required_skills=skills_a_analyser,
        job_text=case.texte,
    )

    statut_obtenu = {
        _canonical_skill_name(match.skill): match.status
        for match in matching.matches
    }

    for competence, attendu in case.statuts_attendus.items():

        canon = _canonical_skill_name(competence)
        obtenu = statut_obtenu.get(canon)

        if obtenu is None:
            # La compétence attendue n'a pas été analysée du tout.
            result.erreurs_statut.append(
                StatusError(
                    competence=competence,
                    attendu=attendu,
                    obtenu="(non analysée)",
                )
            )
            continue

        if obtenu == attendu:
            result.statuts_corrects += 1
        else:
            result.erreurs_statut.append(
                StatusError(
                    competence=competence,
                    attendu=attendu,
                    obtenu=obtenu,
                )
            )

    return result


# ============================================================
# AFFICHAGE
# ============================================================

def _pourcent(value: float | None) -> str:
    if value is None:
        return "  n/a"
    return f"{value * 100:5.1f} %"


def print_case_detail(result: CaseResult) -> None:

    case = result.case
    extraction = result.extraction

    print()
    print(f"--- {case.titre} ({case.slug})")

    print(
        f"    extraction : "
        f"precision {_pourcent(extraction.precision)} | "
        f"recall {_pourcent(extraction.recall)}"
    )

    if extraction.faux_positifs:
        print(
            "      faux positifs  : "
            + ", ".join(extraction.faux_positifs)
        )

    if extraction.oubliees:
        print(
            "      oubliées       : "
            + ", ".join(extraction.oubliees)
        )

    if case.statuts_attendus:

        total = (
            result.statuts_corrects
            + len(result.erreurs_statut)
        )

        print(
            f"    statuts    : "
            f"{result.statuts_corrects}/{total} corrects"
        )

        for erreur in result.erreurs_statut:

            marqueur = (
                "SURÉVALUATION"
                if erreur.est_surevaluation
                else "écart"
            )

            print(
                f"      {marqueur:13} {erreur.competence} : "
                f"attendu {erreur.attendu}, "
                f"obtenu {erreur.obtenu}"
            )


def print_report(
    results: list[CaseResult],
    detail: bool,
) -> None:

    print()
    print("=" * 62)
    print("EVALUATION DU MOTEUR DE MATCHING")
    print("=" * 62)

    if detail:
        for result in results:
            print_case_detail(result)

    # --------------------------------------------------------
    # AGREGATION
    # --------------------------------------------------------

    tp = sum(
        len(r.extraction.trouvees_et_attendues) for r in results
    )
    fp = sum(len(r.extraction.faux_positifs) for r in results)
    fn = sum(len(r.extraction.oubliees) for r in results)

    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall
        else None
    )

    print()
    print(f"Cas évalués : {len(results)}")
    print()
    print("EXTRACTION DES COMPÉTENCES DEMANDÉES")
    print(f"  compétences correctement détectées : {tp}")
    print(f"  faux positifs (détectées à tort)   : {fp}")
    print(f"  oubliées (attendues, non trouvées) : {fn}")
    print(f"  precision : {_pourcent(precision)}")
    print(f"  recall    : {_pourcent(recall)}")
    print(f"  F1        : {_pourcent(f1)}")

    # --------------------------------------------------------
    # STATUTS
    # --------------------------------------------------------

    corrects = sum(r.statuts_corrects for r in results)

    erreurs = [
        erreur
        for r in results
        for erreur in r.erreurs_statut
    ]

    total_statuts = corrects + len(erreurs)

    print()
    print("STATUTS ATTRIBUÉS")

    if total_statuts == 0:
        print("  aucun statut annoté dans le dataset")
    else:
        exactitude = corrects / total_statuts

        print(f"  statuts annotés : {total_statuts}")
        print(f"  corrects        : {corrects}")
        print(f"  exactitude      : {_pourcent(exactitude)}")

    # --------------------------------------------------------
    # SURÉVALUATIONS
    # --------------------------------------------------------

    surevaluations = [
        erreur for erreur in erreurs if erreur.est_surevaluation
    ]

    print()
    print("SURÉVALUATIONS — le moteur en affirme plus que la réalité")
    print("(l'erreur qui produirait un CV malhonnête)")

    if not surevaluations:
        print("  aucune")
    else:
        print(f"  {len(surevaluations)} sur {total_statuts} statuts")

        for erreur in surevaluations:
            print(
                f"    {erreur.competence} : "
                f"attendu {erreur.attendu}, "
                f"obtenu {erreur.obtenu}"
            )

    print()


# ============================================================
# POINT D'ENTREE
# ============================================================

def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Mesure precision / recall / surévaluations du moteur "
            "de matching sur le dataset annoté."
        )
    )

    parser.add_argument(
        "--detail",
        action="store_true",
        help="affiche le détail annonce par annonce",
    )

    parser.add_argument(
        "--inclure-non-revises",
        action="store_true",
        help=(
            "inclut les cas non relus par un humain — les chiffres "
            "obtenus ne mesurent alors plus rien"
        ),
    )

    args = parser.parse_args()

    cases = load_cases()

    if not cases:
        print()
        print(f"Aucun cas trouvé dans {DATASET_DIR}")
        print("Voir evaluation/README.md pour en ajouter un.")
        print()
        return 1

    non_revises = [
        case for case in cases if not case.revise_par_humain
    ]

    if non_revises and not args.inclure_non_revises:

        print()
        print(
            f"{len(non_revises)} cas sur {len(cases)} ne sont pas "
            "encore relus et sont EXCLUS de la mesure :"
        )

        for case in non_revises:
            print(f"  - {case.slug} : {case.titre}")

        print()
        print(
            "Ces annotations ont été pré-remplies avec la sortie du "
            "moteur lui-même. Les compter reviendrait à comparer le "
            "moteur à lui-même : le score serait de 100 % et ne "
            "mesurerait rien."
        )
        print()
        print(
            "Relis chaque attendu.json, corrige les compétences et "
            "les statuts, puis passe revise_par_humain à true."
        )

        cases = [case for case in cases if case.revise_par_humain]

        if not cases:
            print()
            print("Aucun cas relu : rien à mesurer pour l'instant.")
            print()
            return 1

    results = [evaluate_case(case) for case in cases]

    print_report(results, detail=args.detail)

    return 0


if __name__ == "__main__":
    sys.exit(main())
