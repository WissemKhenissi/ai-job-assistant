"""
Mesure de la qualité du moteur de matching.

Deux couches sont évaluées séparément, car elles échouent
différemment :

1. EXTRACTION — à partir du texte d'une annonce, quelles compétences
   le moteur considère-t-il comme demandées ? On mesure precision,
   recall et faux positifs face aux compétences réellement attendues.

   Deux fois : sans l'IA, puis avec. L'application intercale une
   extraction par l'IA entre le catalogue et le nettoyage ; ne
   mesurer que la moitié déterministe laissait l'autre sans aucun
   garde-fou — c'est ainsi que le doublon « méthode Agile » est passé
   au travers, et que sa correction n'a bougé aucun chiffre.

   La réponse de l'IA est rejouée depuis reponse_ia.json, figée par
   evaluation/enregistrer_reponses_ia.py. La redemander à chaque
   mesure rendrait celle-ci variable, et une mesure qui bouge toute
   seule ne mesure rien.

2. STATUTS — pour chaque compétence demandée, le moteur répond
   proven / declared / inferred / missing. On compare au statut
   attendu.

Toutes les erreurs ne se valent pas. Sur ce projet, la pire est la
SURÉVALUATION : le moteur affirme une compétence mieux établie
qu'elle ne l'est. C'est elle qui produirait un CV malhonnête. Elle est
donc comptée et affichée à part, jamais noyée dans un taux global.

Le référentiel en base doit par ailleurs correspondre à celui du
dépôt : c'est lui qui pilote l'extraction, et une mesure prise sur un
catalogue que personne d'autre ne peut reconstituer ne prouve rien.
Le harnais refuse de mesurer tant qu'ils divergent.

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

from services.catalog_drift import divergences_avec_le_seed
from services.job_requirements_service import extract_required_skills
from services.matching import analyze_candidate_against_skills
from services.matching.normalization import _canonical_skill_name
from services.requirement_cleaning import (
    clean_required_skills,
    merge_ai_requirements,
)


DATASET_DIR = Path(__file__).resolve().parent / "dataset"


def resoudre_candidat(demande: str | None) -> str | None:
    """
    Le profil sur lequel mesurer, ou None si le choix est ambigu.

    L'identifiant était auparavant codé en dur dans ce module — un
    reliquat de l'époque où l'application ne connaissait qu'un
    candidat. Il désignait un profil qui pouvait ne pas exister dans
    la base de celui qui lance la mesure, et le harnais mesurait
    alors le vide sans le dire.

    La règle est explicite : un seul profil en base, on le prend ;
    plusieurs, il faut choisir.
    """

    from services.profile_service import list_candidates

    profils = list_candidates()

    if not profils:
        print()
        print("Aucun profil en base — rien à mesurer.")
        print("Créez-en un dans l'application, ou voir database/init_db.py.")
        print()
        return None

    if demande:

        if any(profil["id"] == demande for profil in profils):
            return demande

        print()
        print(f"Profil inconnu : {demande}")
        print("Profils disponibles :")
        for profil in profils:
            print(f"  - {profil['id']} : {profil['full_name']}")
        print()
        return None

    if len(profils) == 1:
        return profils[0]["id"]

    print()
    print(
        f"{len(profils)} profils en base : précisez lequel mesurer "
        "avec --candidat."
    )
    for profil in profils:
        print(f"  - {profil['id']} : {profil['full_name']}")
    print()
    return None


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

    # Ce que l'IA avait répondu le jour de l'enregistrement, ou None
    # si aucune réponse n'a été figée pour ce cas.
    reponse_ia: dict | None = None


def _lire_reponse_ia(case_dir: Path) -> dict | None:
    """
    La réponse de l'IA figée pour ce cas, si elle existe.

    Son absence n'est pas une erreur : la mesure sans IA reste
    valable, et le rapport dit alors sur combien de cas la couche IA
    a pu être évaluée.
    """

    chemin = case_dir / "reponse_ia.json"

    if not chemin.exists():
        return None

    return json.loads(chemin.read_text(encoding="utf-8"))


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
                reponse_ia=_lire_reponse_ia(case_dir),
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

    # Le circuit complet de l'application : catalogue, IA, nettoyage.
    extraction: ExtractionResult

    # Le même, sans l'étape IA. L'écart entre les deux est la seule
    # réponse honnête à « l'IA apporte-t-elle quelque chose ? ».
    extraction_sans_ia: ExtractionResult

    statuts_corrects: int = 0
    erreurs_statut: list[StatusError] = field(default_factory=list)


# ============================================================
# EVALUATION D'UN CAS
# ============================================================

def evaluate_case(
    case: EvaluationCase,
    candidate_id: str,
) -> CaseResult:

    # --------------------------------------------------------
    # COUCHE 1 : EXTRACTION
    # --------------------------------------------------------
    #
    # La comparaison se fait sur la forme canonique : "Project
    # Management" et "Gestion de projet" désignent la même
    # compétence et ne doivent pas compter comme un écart.

    # Le harnais mesurait l'extraction brute, alors que l'application
    # ne s'en sert jamais telle quelle : elle enchaîne toujours sur
    # clean_required_skills. La precision affichée était donc celle
    # d'un enchaînement qui n'existe nulle part — « paris », « ski »
    # et « communication » comptaient comme des faux positifs que
    # l'utilisateur n'aurait jamais vus.
    #
    # Une mesure doit porter sur le circuit réel, sinon elle mesure
    # une autre application que la sienne.

    du_catalogue = extract_required_skills(case.texte)

    detectees_sans_ia, _ = clean_required_skills(
        list(du_catalogue),
        job_title=case.titre,
        job_description=case.texte,
    )

    if case.reponse_ia is not None:

        avec_ia = merge_ai_requirements(
            list(du_catalogue),
            case.reponse_ia.get("required_skills", []),
        )

    else:
        avec_ia = list(du_catalogue)

    detectees, _ = clean_required_skills(
        avec_ia,
        job_title=case.titre,
        job_description=case.texte,
    )

    canon_attendues = {
        _canonical_skill_name(skill): skill
        for skill in case.competences_attendues
    }

    def confronter(sorties) -> ExtractionResult:
        """Ce qu'un circuit a trouvé, face à ce qui est attendu."""

        canon = {
            _canonical_skill_name(skill): skill for skill in sorties
        }

        return ExtractionResult(
            trouvees_et_attendues=sorted(
                canon_attendues[cle]
                for cle in canon.keys() & canon_attendues.keys()
            ),
            faux_positifs=sorted(
                canon[cle]
                for cle in canon.keys() - canon_attendues.keys()
            ),
            oubliees=sorted(
                canon_attendues[cle]
                for cle in canon_attendues.keys() - canon.keys()
            ),
        )

    result = CaseResult(
        case=case,
        extraction=confronter(detectees),
        extraction_sans_ia=confronter(detectees_sans_ia),
    )

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
        candidate_id=candidate_id,
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

    def agreger(extractions) -> tuple:

        tp = sum(len(e.trouvees_et_attendues) for e in extractions)
        fp = sum(len(e.faux_positifs) for e in extractions)
        fn = sum(len(e.oubliees) for e in extractions)

        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None

        f1 = (
            2 * precision * recall / (precision + recall)
            if precision and recall
            else None
        )

        return tp, fp, fn, precision, recall, f1

    complet = agreger([r.extraction for r in results])
    sans_ia = agreger([r.extraction_sans_ia for r in results])

    avec_reponse = [
        r for r in results if r.case.reponse_ia is not None
    ]

    print()
    print(f"Cas évalués : {len(results)}")
    print()
    print("EXTRACTION DES COMPÉTENCES DEMANDÉES")
    print(
        "  %-14s %-12s %-12s %s"
        % ("", "catalogue", "+ IA", "apport de l'IA")
    )

    for libelle, i in (
        ("détectées", 0),
        ("faux positifs", 1),
        ("oubliées", 2),
    ):
        print(
            "  %-14s %-12d %-12d %+d"
            % (libelle, sans_ia[i], complet[i], complet[i] - sans_ia[i])
        )

    for libelle, i in (
        ("precision", 3),
        ("recall", 4),
        ("F1", 5),
    ):
        ecart = (
            "%+.1f pts" % ((complet[i] - sans_ia[i]) * 100)
            if complet[i] is not None and sans_ia[i] is not None
            else "—"
        )
        print(
            "  %-14s %-12s %-12s %s"
            % (
                libelle,
                _pourcent(sans_ia[i]),
                _pourcent(complet[i]),
                ecart,
            )
        )

    print()

    if not avec_reponse:
        print(
            "  Aucune réponse d'IA figée : les deux colonnes sont "
            "identiques. Voir enregistrer_reponses_ia.py."
        )
    else:
        print(
            "  Réponse de l'IA rejouée sur %d cas sur %d, figée le %s."
            % (
                len(avec_reponse),
                len(results),
                avec_reponse[0].case.reponse_ia.get(
                    "enregistre_le", "?"
                ),
            )
        )

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
# LE REFERENTIEL MESURE EST-IL CELUI DU DEPOT ?
# ============================================================

def refuser_si_la_base_derive(ignorer: bool) -> bool:
    """
    Vrai s'il faut renoncer à mesurer.

    Le référentiel pilote entièrement l'extraction. S'il ne
    correspond plus à database/seed_skill_catalog.py, les chiffres
    obtenus décrivent un moteur qui n'existe que sur cette machine :
    personne ne peut les retrouver depuis le dépôt, et une prochaine
    exécution du seed les changera sans prévenir.

    C'est arrivé. Quatorze alias ajoutés depuis l'écran Référentiel
    n'avaient jamais été remontés dans le fichier ; la mesure publiée
    portait sur un moteur plus riche que celui du dépôt, et un seed
    l'a fait tomber de 83,0 % à 75,5 % de recall d'un coup.

    Même esprit que --inclure-non-revises : on peut passer outre,
    mais il faut le demander, et savoir ce qu'on mesure alors.
    """

    derive = divergences_avec_le_seed()

    if not derive:
        return False

    print()
    print(
        "LE RÉFÉRENTIEL EN BASE NE CORRESPOND PAS AU DÉPÔT."
    )
    print()

    if derive.modifiees:

        print(
            f"{len(derive.modifiees)} entrée(s) modifiée(s) — un "
            f"seed détruirait {derive.alias_en_peril} alias :"
        )

        for entree in derive.modifiees:

            print(f"  - {entree.canonical_name}")

            if entree.alias_perdus:
                print(
                    "      en base seulement : "
                    + ", ".join(entree.alias_perdus)
                )

            if entree.alias_a_recuperer:
                print(
                    "      au dépôt seulement : "
                    + ", ".join(entree.alias_a_recuperer)
                )

            if entree.autres_champs:
                print(
                    "      champs divergents : "
                    + ", ".join(entree.autres_champs)
                )

    if derive.hors_depot:

        print()
        print(
            f"{len(derive.hors_depot)} compétence(s) créée(s) "
            "depuis l'écran et absente(s) du dépôt :"
        )

        for entree in derive.hors_depot:
            print(f"  - {entree.canonical_name}")

    if derive.absentes_de_la_base:

        print()
        print(
            f"{len(derive.absentes_de_la_base)} entrée(s) du dépôt "
            "manquante(s) en base — la base est en retard d'un "
            "seed :"
        )

        for nom in derive.absentes_de_la_base:
            print(f"  - {nom}")

    print()
    print(
        "Une mesure prise sur cette base ne serait reproductible "
        "par personne d'autre."
    )
    print()
    print("Deux sorties :")
    print(
        "  - remonter ces décisions dans "
        "database/seed_skill_catalog.py (l'écran Référentiel "
        "affiche le texte à coller), puis rejouer le seed ;"
    )
    print(
        "  - ou relancer avec --ignorer-la-derive, en sachant que "
        "les chiffres ne vaudront que pour cette machine."
    )
    print()

    return not ignorer


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
        "--candidat",
        metavar="ID",
        help=(
            "identifiant du profil à mesurer ; facultatif si la base "
            "n'en contient qu'un"
        ),
    )

    parser.add_argument(
        "--detail",
        action="store_true",
        help="affiche le détail annonce par annonce",
    )

    parser.add_argument(
        "--ignorer-la-derive",
        action="store_true",
        help=(
            "mesure même si le référentiel en base ne correspond "
            "plus au dépôt — les chiffres ne valent alors que pour "
            "cette machine"
        ),
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

    if refuser_si_la_base_derive(args.ignorer_la_derive):
        return 1

    candidate_id = resoudre_candidat(args.candidat)

    if candidate_id is None:
        return 1

    results = [
        evaluate_case(case, candidate_id) for case in cases
    ]

    print_report(results, detail=args.detail)

    return 0


if __name__ == "__main__":
    sys.exit(main())
