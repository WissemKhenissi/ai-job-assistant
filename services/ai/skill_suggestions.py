"""
Suggestions de compétences attendues pour un poste donné.

Sert à alimenter le choix du candidat dans l'onglet Compétences : on
lui propose ce qu'un poste demande habituellement, il coche ce qu'il
possède réellement.

Point d'honnêteté : ce module ne fait que **proposer une liste de
noms**. Une compétence retenue est ensuite ajoutée sans preuve, donc
au statut "declared" — le moteur de matching continuera de la
distinguer d'une compétence "proven". C'est le candidat qui atteste,
jamais le système qui affirme à sa place.
"""

from __future__ import annotations

import json
import re

from services.ai.gemini_client import (
    GeminiNotConfiguredError,
    GeminiRequestError,
    generate_text,
    is_configured,
)


MAX_SUGGESTIONS = 40


def _strip_json_fences(text: str) -> str:

    texte = text.strip()

    if texte.startswith("```"):
        texte = re.sub(r"^```[a-zA-Z]*\n?", "", texte)
        texte = re.sub(r"```$", "", texte.strip())

    return texte.strip()


def suggest_skills_for_role(
    role: str,
    count: int = 15,
    existing: list[str] | None = None,
) -> tuple[list[str], str]:
    """
    Propose les `count` compétences les plus attendues pour `role`,
    en excluant celles que le candidat déclare déjà.

    Ne lève jamais d'exception : retourne une liste vide et un
    avertissement en cas d'échec.
    """

    if not role.strip():
        return [], "Indiquez un poste pour obtenir des suggestions."

    if not is_configured():
        return [], (
            "Clé GEMINI_API_KEY non configurée : suggestions "
            "indisponibles."
        )

    deja = [nom.strip() for nom in (existing or []) if nom.strip()]

    prompt = (
        f"Liste les {count} compétences les plus attendues pour un "
        f"poste de « {role.strip()} », classées de la plus "
        "importante à la moins importante.\n\n"
        "RÈGLES :\n"
        "- Des noms de compétences courts et concrets (2 à 4 mots), "
        "tels qu'on les écrirait sur un CV.\n"
        "- Des compétences métier, méthodologiques ou techniques — "
        "pas des traits de personnalité.\n"
        "- Réponds UNIQUEMENT avec un tableau JSON de chaînes, sans "
        "texte autour, sans balisage markdown : "
        '["Compétence 1", "Compétence 2"].'
    )

    if deja:
        prompt += (
            "\n- N'inclus AUCUNE des compétences suivantes, déjà "
            "déclarées par le candidat : " + ", ".join(deja)
        )

    try:
        reponse = generate_text(prompt, temperature=0.2)

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return [], f"Suggestions indisponibles ({error})."

    try:
        donnees = json.loads(_strip_json_fences(reponse))

    except json.JSONDecodeError:
        return [], "Réponse de l'IA illisible : réessayez."

    if not isinstance(donnees, list):
        return [], "Format de réponse inattendu : réessayez."

    # Filtrage final côté code : le prompt demande d'exclure les
    # compétences déjà déclarées, mais rien ne garantit qu'il soit
    # suivi — un doublon proposé ferait perdre du temps au candidat.
    deja_normalisees = {nom.casefold() for nom in deja}

    suggestions = []

    for element in donnees[:MAX_SUGGESTIONS]:

        if not isinstance(element, str):
            continue

        nom = element.strip()

        if not nom or nom.casefold() in deja_normalisees:
            continue

        deja_normalisees.add(nom.casefold())
        suggestions.append(nom)

    if not suggestions:
        return [], "Aucune suggestion nouvelle pour ce poste."

    return suggestions, ""
