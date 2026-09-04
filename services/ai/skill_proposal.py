"""
Proposition d'entrée de référentiel à partir d'un terme d'annonce.

Le référentiel livré ne couvre que les métiers prévus par son auteur.
Le faire grandir à la main suppose que quelqu'un sache, pour chaque
terme rencontré, s'il désigne une compétence nouvelle ou une autre
façon de nommer une compétence connue — et sache lui trouver un nom,
une catégorie et des synonymes. C'est précisément le travail que
l'IA fait bien et que l'utilisateur fait lentement.

Ce module ne décide rien : il **pré-remplit un formulaire**. Créer une
compétence reste un clic de l'utilisateur, comme tout ce qui engage
son CV. La proposition peut être corrigée dans tous ses champs avant
d'être appliquée, ou ignorée.

Garde-fous appliqués au résultat, avant même de l'afficher :

- un rattachement proposé vers une compétence inexistante est écarté ;
- un alias déjà revendiqué par une autre compétence est retiré, avec
  un avertissement — un alias appartient à une seule entrée, sinon une
  compétence du Master CV se rattacherait à la mauvaise ;
- le terme d'origine est toujours conservé parmi les alias, faute de
  quoi l'annonce qui l'emploie ne serait toujours pas reconnue.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from services.ai.gemini_client import (
    GeminiNotConfiguredError,
    GeminiRequestError,
    generate_text,
    is_configured,
)
from services.skill_catalog_service import (
    get_active_skills,
    normalize_skill_text,
)


# Un extrait suffit à lever l'ambiguïté d'un sigle : « CDP » n'a pas
# le même sens dans une annonce marketing et dans une annonce
# industrielle.
MAX_CONTEXT = 1200

MAX_ALIASES = 8


@dataclass(frozen=True)
class SkillProposal:
    """
    Ce que l'IA propose de faire d'un terme inconnu.

    `attach_to_id` non vide signifie « ce n'est pas une compétence
    nouvelle, c'est un autre nom pour celle-ci ».
    """

    canonical_name: str = ""
    category: str = ""
    description: str = ""
    aliases: tuple[str, ...] = ()
    attach_to_id: str = ""
    attach_to_name: str = ""
    reasoning: str = ""
    warning: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.canonical_name and not self.attach_to_id


def _strip_json_fences(text: str) -> str:

    texte = text.strip()

    if texte.startswith("```"):
        texte = re.sub(r"^```[a-zA-Z]*\n?", "", texte)
        texte = re.sub(r"```$", "", texte.strip())

    return texte.strip()


def _lire_objet_json(reponse: str) -> dict | None:
    """
    Lit l'objet JSON d'une réponse, même entourée de texte.

    Le modèle respecte la consigne « uniquement du JSON » la plupart
    du temps, mais pas toujours : observé une fois sur quinze en usage
    réel. Repêcher l'objet coûte deux lignes et évite de renvoyer
    l'utilisateur à un « réessayez » sans raison visible.
    """

    texte = _strip_json_fences(reponse)

    try:
        donnees = json.loads(texte)

    except json.JSONDecodeError:

        debut = texte.find("{")
        fin = texte.rfind("}")

        if debut < 0 or fin <= debut:
            return None

        try:
            donnees = json.loads(texte[debut : fin + 1])

        except json.JSONDecodeError:
            return None

    return donnees if isinstance(donnees, dict) else None


def _index_du_referentiel() -> tuple[dict, dict]:
    """
    Retourne (nom canonique normalisé -> compétence, alias normalisé
    -> nom canonique) pour valider la proposition.
    """

    par_nom: dict[str, object] = {}
    proprietaire: dict[str, str] = {}

    for competence in get_active_skills():

        par_nom[normalize_skill_text(competence.canonical_name)] = (
            competence
        )

        for alias in (
            competence.canonical_name,
            *competence.aliases,
        ):
            proprietaire[normalize_skill_text(alias)] = (
                competence.canonical_name
            )

    return par_nom, proprietaire


def _construire_prompt(
    term: str,
    context: str,
    noms_existants: list[str],
) -> str:

    prompt = (
        "Tu tiens un référentiel de compétences professionnelles, "
        "tous métiers confondus.\n\n"
        f"Un terme est apparu dans une offre d'emploi : « {term} ».\n"
        "Le référentiel ne le reconnaît pas. Décide ce qu'il faut en "
        "faire.\n\n"
        "DEUX RÉPONSES POSSIBLES\n"
        "1. Le terme désigne une compétence DÉJÀ présente dans la "
        "liste ci-dessous, sous un autre nom : réponds avec "
        '"attach_to" contenant EXACTEMENT le nom de cette '
        "compétence.\n"
        "2. Le terme désigne une compétence ABSENTE de la liste : "
        'réponds avec "canonical_name", "category", "description" '
        'et "aliases".\n\n'
        "RÈGLES\n"
        "- Ne rattache que si les deux termes désignent réellement la "
        "même compétence. Deux compétences proches mais distinctes "
        "(par exemple « cycle en V » et « gestion de projet ») "
        "doivent rester séparées : un rattachement abusif ferait "
        "passer un candidat pour compétent dans un domaine qu'il ne "
        "maîtrise pas.\n"
        "- Le nom canonique doit être la façon la plus courante "
        "d'écrire cette compétence sur un CV, dans la langue de "
        "l'annonce.\n"
        "- Les alias sont les autres écritures du MÊME concept : "
        "traductions, sigles, variantes. Jamais des compétences "
        "voisines, jamais des sous-compétences.\n"
        "- La catégorie est un mot ou deux, cohérent avec le métier "
        "concerné.\n"
        "- Si le terme n'est pas une compétence (un mot générique "
        "d'annonce, un nom d'entreprise, un intitulé de poste), "
        'réponds {"not_a_skill": true} avec une brève raison.\n\n'
        "FORMAT\n"
        "Réponds uniquement avec un objet JSON, sans texte autour, "
        "sans balisage markdown :\n"
        '{"attach_to": "", "canonical_name": "", "category": "", '
        '"description": "", "aliases": [], "reasoning": ""}\n\n'
    )

    if context.strip():
        prompt += (
            "EXTRAIT DE L'ANNONCE OÙ LE TERME APPARAÎT\n"
            f"{context.strip()[:MAX_CONTEXT]}\n\n"
        )

    prompt += (
        "COMPÉTENCES DÉJÀ AU RÉFÉRENTIEL\n"
        + "\n".join(f"- {nom}" for nom in noms_existants)
    )

    return prompt


def propose_catalog_entry(
    term: str,
    context: str = "",
) -> SkillProposal:
    """
    Propose une entrée de référentiel pour un terme inconnu.

    Ne lève jamais d'exception : en cas d'échec, retourne une
    proposition vide portant un avertissement. Le formulaire manuel
    reste utilisable dans tous les cas.
    """

    if not term.strip():
        return SkillProposal(warning="Aucun terme à analyser.")

    if not is_configured():
        return SkillProposal(
            warning=(
                "Clé GEMINI_API_KEY non configurée : proposition "
                "indisponible, remplissez le formulaire à la main."
            )
        )

    par_nom, proprietaire = _index_du_referentiel()

    prompt = _construire_prompt(
        term,
        context,
        sorted(
            competence.canonical_name
            for competence in par_nom.values()
        ),
    )

    try:
        reponse = generate_text(prompt, temperature=0.2)

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return SkillProposal(
            warning=f"Proposition indisponible ({error})."
        )

    donnees = _lire_objet_json(reponse)

    if donnees is None:
        return SkillProposal(
            warning="Réponse de l'IA illisible : réessayez."
        )

    return _valider(term, donnees, par_nom, proprietaire)


def _valider(
    term: str,
    donnees: dict,
    par_nom: dict,
    proprietaire: dict,
) -> SkillProposal:
    """Confronte la proposition au référentiel réel."""

    raison = str(donnees.get("reasoning") or "").strip()

    # ----------------------------------------------------------
    # PAS UNE COMPETENCE
    # ----------------------------------------------------------

    if donnees.get("not_a_skill"):
        return SkillProposal(
            reasoning=raison,
            warning=(
                "L'IA estime que ce terme ne désigne pas une "
                "compétence."
            ),
        )

    # ----------------------------------------------------------
    # RATTACHEMENT A UNE COMPETENCE EXISTANTE
    # ----------------------------------------------------------

    vise = str(donnees.get("attach_to") or "").strip()

    if vise:

        competence = par_nom.get(normalize_skill_text(vise))

        if competence is None:
            return SkillProposal(
                reasoning=raison,
                warning=(
                    f"L'IA proposait de rattacher à « {vise} », qui "
                    "ne figure pas au référentiel : proposition "
                    "écartée."
                ),
            )

        return SkillProposal(
            attach_to_id=competence.id,
            attach_to_name=competence.canonical_name,
            reasoning=raison,
        )

    # ----------------------------------------------------------
    # NOUVELLE COMPETENCE
    # ----------------------------------------------------------

    nom = str(donnees.get("canonical_name") or "").strip()

    if not nom:
        return SkillProposal(
            reasoning=raison,
            warning="L'IA n'a proposé aucun nom : réessayez.",
        )

    conflit = proprietaire.get(normalize_skill_text(nom))

    if conflit is not None:
        return SkillProposal(
            reasoning=raison,
            warning=(
                f"« {nom} » est déjà connu du référentiel sous "
                f"« {conflit} » : rattachez le terme plutôt que de "
                "créer un doublon."
            ),
        )

    # Alias : on retire ceux qui appartiennent déjà à une autre
    # compétence, et on garantit la présence du terme d'origine.
    alias: list[str] = []
    ecartes: list[str] = []

    vus = {normalize_skill_text(nom)}

    propositions = donnees.get("aliases")

    for element in (
        propositions if isinstance(propositions, list) else []
    ):

        if not isinstance(element, str):
            continue

        candidat = element.strip()

        if not candidat:
            continue

        cle = normalize_skill_text(candidat)

        if not cle or cle in vus:
            continue

        if cle in proprietaire:
            ecartes.append(candidat)
            continue

        vus.add(cle)
        alias.append(candidat)

    if normalize_skill_text(term) not in vus:
        alias.append(term.strip())

    avertissement = ""

    if ecartes:
        avertissement = (
            "Alias écarté(s), déjà rattaché(s) à une autre "
            f"compétence : {', '.join(ecartes)}."
        )

    return SkillProposal(
        canonical_name=nom,
        category=str(donnees.get("category") or "").strip(),
        description=str(donnees.get("description") or "").strip(),
        aliases=tuple([nom, *alias][:MAX_ALIASES]),
        reasoning=raison,
        warning=avertissement,
    )
