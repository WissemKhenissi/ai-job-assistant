"""
Fige la réponse de l'IA pour chaque annonce du jeu d'évaluation.

Le harnais ne mesurait que la moitié déterministe du moteur :
extraction par le catalogue, puis nettoyage. L'application, elle,
intercale une extraction par l'IA, dont les propositions sont fusionnées
au catalogue. Cette moitié-là n'était mesurée par rien — c'est ainsi
que le doublon « méthode Agile » est passé au travers, et que sa
correction n'a bougé aucun chiffre.

On ne peut pas simplement appeler Gemini depuis le harnais : la
réponse varie d'un appel à l'autre, et une mesure qui bouge toute
seule ne mesure rien. C'est le même reproche qui a fait sortir l'IA du
classement du niveau d'exigence.

La réponse est donc enregistrée une fois, datée, versionnée à côté de
l'annonce, et rejouée à l'identique. Le harnais redevient
reproductible et gratuit, et ce qu'il mesure devient le vrai circuit
de l'application.

Ce que ça n'est pas : une mesure de la qualité de l'IA dans le temps.
Une réponse figée dit ce que le modèle a répondu ce jour-là. La
réenregistrer après une mise à jour du modèle est une décision à
prendre, pas un automatisme — sans quoi la vérité terrain suivrait
silencieusement le modèle qu'elle est censée juger.

Usage :

    .venv/Scripts/python.exe -m evaluation.enregistrer_reponses_ia
    .venv/Scripts/python.exe -m evaluation.enregistrer_reponses_ia --forcer
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from services.ai.gemini_client import GEMINI_MODEL, is_configured
from services.ai.job_analysis import analyze_job_offer_with_ai


DATASET_DIR = Path(__file__).resolve().parent / "dataset"

NOM_FICHIER = "reponse_ia.json"


def cas_du_dataset() -> list[Path]:

    if not DATASET_DIR.exists():
        return []

    return [
        dossier
        for dossier in sorted(DATASET_DIR.iterdir())
        if dossier.is_dir() and (dossier / "annonce.txt").exists()
    ]


def enregistrer(dossier: Path, forcer: bool) -> str:
    """Retourne ce qui a été fait, en une ligne."""

    destination = dossier / NOM_FICHIER

    if destination.exists() and not forcer:
        return "déjà enregistrée"

    texte = (dossier / "annonce.txt").read_text(encoding="utf-8")

    titre = ""

    attendu = dossier / "attendu.json"

    if attendu.exists():
        titre = json.loads(
            attendu.read_text(encoding="utf-8")
        ).get("titre", "")

    analyse = analyze_job_offer_with_ai(f"{titre}\n{texte}".strip())

    if analyse.warning:
        return f"échec : {analyse.warning}"

    destination.write_text(
        json.dumps(
            {
                "enregistre_le": date.today().isoformat(),
                "modele": GEMINI_MODEL,
                "contract_type": analyse.contract_type,
                "remote_policy": analyse.remote_policy,
                "remote_details": analyse.remote_details,
                "required_skills": analyse.required_skills,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return "%d compétence(s) proposée(s)" % len(analyse.required_skills)


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Enregistre la réponse de l'IA pour chaque annonce du jeu "
            "d'évaluation, afin que le harnais la rejoue au lieu de "
            "la redemander."
        )
    )

    parser.add_argument(
        "--forcer",
        action="store_true",
        help=(
            "réenregistre même les réponses déjà figées — à ne faire "
            "que délibérément, une réponse figée est une référence"
        ),
    )

    args = parser.parse_args()

    if not is_configured():
        print()
        print("GEMINI_API_KEY absente : rien à enregistrer.")
        print()
        return 1

    cas = cas_du_dataset()

    if not cas:
        print()
        print(f"Aucun cas dans {DATASET_DIR}")
        print()
        return 1

    print()
    print(f"modèle : {GEMINI_MODEL}")
    print()

    for dossier in cas:
        print("  %-42s %s" % (dossier.name[:42], enregistrer(dossier, args.forcer)))

    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
