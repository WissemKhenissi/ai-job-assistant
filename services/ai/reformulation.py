"""
Reformulation IA du CV et de la lettre, avec garde-fous anti-invention.

Principe non négociable du projet, appliqué ici : l'IA reformule un
texte déjà entièrement déterminé par le Master CV. Elle ne peut ni
ajouter une compétence, ni un chiffre, ni un fait absent du texte
source — seulement le rendre plus fluide et plus adapté au vocabulaire
de l'offre.

Quatre lignes de défense :

1. Le prompt l'interdit explicitement — les règles viennent de
   services.cv.prompt_rules, qui répartit le cahier des charges de
   rédaction entre les étapes capables de l'appliquer.
2. Un garde-fou vérifie qu'aucun nombre nouveau (donc potentiellement
   un chiffre ou un pourcentage inventé) n'apparaît dans le résultat.
3. Un garde-fou vérifie qu'aucun terme désignant une compétence non
   prouvée n'apparaît : sans lui, « adapte-toi au vocabulaire de
   l'offre » suffirait à faire écrire au modèle une compétence que le
   candidat ne possède pas.
4. Un garde-fou vérifie qu'aucun mot de séniorité n'a été ajouté :
   « expert » n'est ni un chiffre ni un nom de compétence, et
   traversait donc les deux contrôles précédents.

Si la reformulation échoue pour n'importe quelle raison — clé absente,
erreur API, garde-fou déclenché — le texte déterministe d'origine est
utilisé sans que rien ne casse. La reformulation est un plus, jamais
une dépendance : le CV et la lettre restent générables sans elle.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from services.ai.gemini_client import (
    GeminiNotConfiguredError,
    GeminiRequestError,
    generate_text,
    is_configured,
)
from services.cv.prompt_rules import (
    ANTI_INVENTION,
    FORMULATION,
    RESUME,
    build_summary_focus,
    build_vocabulary_rules,
)
from services.cv.results import CVEvidenceLine, TargetedCV
from services.cv.vocabulary import (
    OfferVocabulary,
    build_offer_vocabulary,
    forbidden_terms_used,
    seniority_terms_added,
)
from services.text_numbers import numbers_in


# Longueur d'extrait d'offre transmise au prompt : assez pour donner
# le vocabulaire et le ton, sans faire exploser le coût du prompt sur
# une annonce de plusieurs milliers de caractères.
MAX_JOB_EXCERPT = 2000


# Reformuler, c'est redire la même chose autrement : la créativité n'y
# a aucune valeur, elle n'apporte que de l'enjolivement. Un essai à la
# température par défaut (0.4) a fait apparaître dans un résumé une
# « approche Data / KPI » que le texte source ne mentionnait pas —
# terme autorisé, donc invisible pour les garde-fous, mais ajouté.
REFORMULATION_TEMPERATURE = 0.2


@dataclass(frozen=True)
class ReformulationResult:
    text: str
    was_reformulated: bool
    warning: str = ""


def _motif_de_rejet(
    reformule: str,
    source_text: str,
    forbidden_terms: tuple[str, ...] | list[str],
) -> str:
    """
    Raison pour laquelle une reformulation ne peut pas être retenue.

    Chaîne vide si elle est acceptable. Le motif est rédigé pour
    servir deux fois : expliqué à l'utilisateur, et renvoyé au modèle
    pour qu'il retente sans l'erreur.
    """

    # Un chiffre absent du texte source (marge, pourcentage, durée)
    # serait la forme la plus grave d'invention : un fait chiffré
    # fabriqué. On ne tente pas de tout vérifier — seuls les nombres
    # sont assez concrets pour être contrôlés de façon fiable.
    nombres_inventes = numbers_in(reformule) - numbers_in(source_text)

    if nombres_inventes:
        return (
            "elle introduisait des chiffres absents du texte source "
            f"({', '.join(sorted(nombres_inventes))})."
        )

    # Pendant du précédent : les chiffres protègent des faits
    # inventés, les termes protègent des compétences inventées. La
    # liste vient du référentiel, pas du jugement du modèle.
    termes_interdits = forbidden_terms_used(
        reformule,
        forbidden_terms,
        source_text,
    )

    if termes_interdits:
        return (
            "elle affirmait des compétences que le Master CV ne "
            f"prouve pas ({', '.join(sorted(termes_interdits))})."
        )

    # Ni un chiffre, ni un nom de compétence : « expert » traversait
    # les deux contrôles précédents alors qu'il transforme une
    # expérience en expertise, ce que le cahier des charges interdit.
    seniorite = seniority_terms_added(reformule, source_text)

    if seniorite:
        return (
            "elle rehaussait le niveau annoncé "
            f"({', '.join(seniorite)}) sans que le texte source le "
            "dise."
        )

    return ""


def _safe_reformulate(
    source_text: str,
    instructions: str,
    forbidden_terms: tuple[str, ...] | list[str] = (),
) -> ReformulationResult:
    """
    Reformule un texte via Gemini, avec repli automatique sur le texte
    source en cas d'échec ou de garde-fou déclenché.
    """

    if not source_text.strip():
        return ReformulationResult(
            text=source_text,
            was_reformulated=False,
        )

    if not is_configured():
        return ReformulationResult(
            text=source_text,
            was_reformulated=False,
            warning=(
                "Clé GEMINI_API_KEY non configurée : texte "
                "déterministe utilisé."
            ),
        )

    prompt = (
        "Tu reformules un extrait de candidature déjà entièrement "
        "exact.\n\n"
        f"{ANTI_INVENTION}\n\n"
        f"{instructions}\n\n"
        "FORMAT DE RÉPONSE\n"
        "Réponds uniquement avec le texte reformulé : pas de "
        "commentaire, pas de guillemets, pas d'introduction.\n\n"
        f"Texte source :\n{source_text}"
    )

    try:
        reformule = generate_text(
            prompt,
            temperature=REFORMULATION_TEMPERATURE,
        )

        motif = _motif_de_rejet(
            reformule,
            source_text,
            forbidden_terms,
        )

        # --------------------------------------------------------
        # SECONDE CHANCE
        # --------------------------------------------------------
        #
        # Un garde-fou qui explique son refus vaut mieux qu'un
        # garde-fou qui abandonne : sans cette reprise, un seul mot
        # de trop faisait retomber la phrase entière sur sa version
        # déterministe, et la section n'était plus adaptée du tout.

        if motif:

            reformule = generate_text(
                f"{prompt}\n\n"
                "TA PRÉCÉDENTE RÉPONSE A ÉTÉ REFUSÉE\n"
                f"{motif}\n"
                "Recommence sans cela. Si tu ne peux pas, renvoie le "
                "texte source tel quel.",
                temperature=REFORMULATION_TEMPERATURE,
            )

            motif = _motif_de_rejet(
                reformule,
                source_text,
                forbidden_terms,
            )

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return ReformulationResult(
            text=source_text,
            was_reformulated=False,
            warning=(
                f"Reformulation IA indisponible ({error}) : texte "
                "déterministe utilisé."
            ),
        )

    if motif:
        return ReformulationResult(
            text=source_text,
            was_reformulated=False,
            warning=f"Reformulation rejetée : {motif} Texte "
            "déterministe utilisé.",
        )

    return ReformulationResult(text=reformule, was_reformulated=True)


# ============================================================
# CV CIBLE
# ============================================================

def _bloc_vocabulaire(vocabulary: OfferVocabulary | None) -> str:
    """Règle de vocabulaire, ou rien si l'offre n'a pas été analysée."""

    if vocabulary is None or vocabulary.is_empty:
        return ""

    return "\n\n" + build_vocabulary_rules(
        vocabulary.authorized,
        vocabulary.forbidden,
    )


def _ouverture(texte: str) -> str:
    """Premier mot significatif d'une ligne, pour éviter les répétitions."""

    mots = texte.strip().split()

    if not mots:
        return ""

    mot = mots[0].strip(" ,;:.«»\"'").casefold()

    return mot if len(mot) > 3 else ""


def _bloc_repetitions(ouvertures: tuple[str, ...] | list[str]) -> str:

    if not ouvertures:
        return ""

    return (
        "\n\nRÉPÉTITIONS À ÉVITER\n"
        "D'autres lignes de ce CV commencent déjà par : "
        f"{', '.join(sorted(set(ouvertures)))}. N'ouvre pas "
        "celle-ci de la même façon et varie la tournure."
    )


def reformulate_cv_line(
    text: str,
    job_text: str,
    vocabulary: OfferVocabulary | None = None,
    already_opened_with: tuple[str, ...] | list[str] = (),
) -> ReformulationResult:

    instructions = (
        "Cette ligne fait partie des compétences démontrées sur un "
        "CV ciblé pour l'offre ci-dessous. Reformule-la pour "
        "qu'elle soit plus percutante, sans changer le fond.\n\n"
        f"{FORMULATION}"
        + _bloc_vocabulaire(vocabulary)
        + _bloc_repetitions(already_opened_with)
        + f"\n\nExtrait de l'offre :\n{job_text[:MAX_JOB_EXCERPT]}"
    )

    return _safe_reformulate(
        text,
        instructions,
        vocabulary.forbidden if vocabulary else (),
    )


def reformulate_cv_summary(
    summary: str,
    headline: str,
    job_text: str,
    vocabulary: OfferVocabulary | None = None,
    poste: str = "",
    priorites: tuple[str, ...] | list[str] = (),
) -> ReformulationResult:
    """
    Reformule le résumé de profil (section "Profil" du CV) pour le
    rapprocher du vocabulaire et des enjeux de l'offre — un résumé
    plus "adapté au storytelling de l'offre" reste un résumé du même
    parcours, jamais un résumé différent.
    """

    instructions = (
        "Ce texte est le résumé de profil affiché en tête d'un CV "
        "ciblé pour l'offre ci-dessous"
        + (f' (accroche : "{headline}")' if headline.strip() else "")
        + ". Reformule-le pour qu'il mette en avant, avec le "
        "vocabulaire de l'offre, ce qui est déjà écrit.\n\n"
        f"{RESUME}\n\n"
        + build_summary_focus(poste, priorites)
        + _bloc_vocabulaire(vocabulary)
        + f"\n\nExtrait de l'offre :\n{job_text[:MAX_JOB_EXCERPT]}"
    )

    return _safe_reformulate(
        summary,
        instructions,
        vocabulary.forbidden if vocabulary else (),
    )


def reformulate_targeted_cv(
    cv: TargetedCV,
    job_text: str,
) -> tuple[TargetedCV, list[str]]:
    """
    Reformule le résumé de profil et les lignes de preuve de chaque
    expérience retenue.

    Le reste du CV (compétences, formation, certifications, en-tête)
    n'est volontairement pas passé à l'IA : ce sont des données
    factuelles courtes, sans valeur à en attendre d'une reformulation.
    """

    avertissements: list[str] = []

    # ------------------------------------------------------------
    # CADRE DE VOCABULAIRE
    # ------------------------------------------------------------
    #
    # Son absence n'empêche pas de reformuler — les autres garde-fous
    # tiennent — mais elle retire une protection, donc elle se dit.

    vocabulaire: OfferVocabulary | None = None

    try:
        vocabulaire = build_offer_vocabulary(
            cv.candidate_id,
            cv.job_offer_id,
            cv.skill_levels,
        )

    except Exception as error:
        avertissements.append(
            "Vocabulaire de l'offre indisponible "
            f"({error}) : reformulation sans contrôle des termes."
        )

    resultat_resume = reformulate_cv_summary(
        cv.summary,
        cv.headline,
        job_text,
        vocabulaire,
        poste=cv.cv_title or cv.job_offer_title,
        priorites=tuple(cv.skills),
    )

    if resultat_resume.warning:
        avertissements.append(resultat_resume.warning)

    nouvelles_experiences = []

    ouvertures: list[str] = []

    for experience in cv.experiences:

        nouvelles_lignes: list[CVEvidenceLine] = []

        for ligne in experience.lines:

            resultat = reformulate_cv_line(
                ligne.text,
                job_text,
                vocabulaire,
                tuple(ouvertures),
            )

            if resultat.warning:
                avertissements.append(resultat.warning)

            ouverture = _ouverture(resultat.text)

            if ouverture:
                ouvertures.append(ouverture)

            nouvelles_lignes.append(
                CVEvidenceLine(
                    text=resultat.text,
                    skill=ligne.skill,
                    evidence_id=ligne.evidence_id,
                )
            )

        nouvelles_experiences.append(
            replace(experience, lines=nouvelles_lignes)
        )

    cv_reformule = replace(
        cv,
        summary=resultat_resume.text,
        experiences=nouvelles_experiences,
    )

    return cv_reformule, avertissements
