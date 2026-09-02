"""
Assemblage déterministe d'une lettre de motivation.

Aucune IA n'intervient : la lettre est assemblée à partir du Master CV
et de l'offre, avec des formulations fixes. C'est un choix de cadrage
— un modèle de langage pourrait produire une phrase plus fluide, mais
aussi affirmer une compétence que le candidat ne peut pas prouver.

La lettre s'appuie sur la même sélection que le CV ciblé : les deux
documents affirment donc exactement les mêmes choses.
"""

from __future__ import annotations

from datetime import date

from services.cv import TargetedCV, build_targeted_cv
from services.letter.results import CoverLetter, LetterParagraph


# Nombre de réalisations détaillées dans le corps de la lettre.
# Au-delà, la lettre cesse d'être une lettre.
MAX_ACHIEVEMENTS = 2


def _formuler_liste(elements: list[str]) -> str:
    """Transforme une liste en énumération française lisible."""

    if not elements:
        return ""

    if len(elements) == 1:
        return elements[0]

    return (
        ", ".join(elements[:-1])
        + " et "
        + elements[-1]
    )


def _destinataire(company: str) -> str:
    if company.strip():
        return f"l'équipe de {company.strip()}"

    return "votre équipe"


def _paragraphe_accroche(
    cv: TargetedCV,
    company: str,
) -> LetterParagraph:
    """
    Phrase d'ouverture, courte par construction.

    Le résumé complet du profil (cv.summary) n'est volontairement pas
    repris ici : il vit déjà dans la section PROFIL du CV joint, et
    le dupliquer intégralement noierait l'ouverture de la lettre sous
    un paragraphe dense. Seule l'accroche courte (cv.headline) est
    éventuellement reprise, comme un sous-titre de positionnement.
    """

    poste = cv.job_offer_title or "le poste proposé"

    phrase = (
        f"Votre annonce pour le poste de {poste} a retenu mon "
        f"attention, et je souhaite y postuler."
    )

    if cv.headline.strip():
        phrase += f" Mon positionnement : {cv.headline.strip()}."

    return LetterParagraph(text=phrase)


def _paragraphe_competences(
    cv: TargetedCV,
) -> LetterParagraph | None:
    """
    Paragraphe des compétences.

    Seules les compétences prouvées sont affirmées, et chacune est
    adossée aux éléments de parcours qui la démontrent.
    """

    if not cv.skills:
        return None

    lignes = [
        ligne
        for experience in cv.experiences
        for ligne in experience.lines
    ]

    phrase = (
        "Parmi les compétences que vous recherchez, je peux "
        "documenter concrètement "
        f"{_formuler_liste(cv.skills)}."
    )

    if lignes:

        # Les éléments du Master CV sont des groupes nominaux
        # ("Mise en place d'une logique MVP") : on les présente en
        # énumération après deux-points plutôt que de les enchâsser
        # dans une phrase, et on ne touche pas à leur casse — sans
        # quoi les acronymes seraient abîmés.
        exemples = [
            ligne.text.rstrip(".").strip()
            for ligne in lignes[:3]
        ]

        phrase += (
            " Mon parcours couvre notamment : "
            + " ; ".join(exemples)
            + "."
        )

    return LetterParagraph(
        text=phrase,
        sources=tuple(ligne.evidence_id for ligne in lignes[:3]),
    )


def _paragraphe_realisation(achievement) -> LetterParagraph:
    """
    Une réalisation, résumée pour une lettre.

    On retient le titre et le résultat — la partie qui porte les
    chiffres — plutôt que le détail Situation / Action / Résultat
    complet : celui-ci a sa place sur le CV, pas dans une lettre où
    il noierait le propos.
    """

    morceaux = [achievement.title.strip().rstrip(".") + "."]

    if achievement.result:
        morceaux.append(achievement.result.strip())

    elif achievement.situation:
        morceaux.append(achievement.situation.strip())

    return LetterParagraph(
        text=" ".join(morceaux),
        sources=(achievement.achievement_id,),
    )


def _paragraphe_motivation(company: str) -> LetterParagraph:

    return LetterParagraph(
        text=(
            f"Je serais heureux d'échanger avec {_destinataire(company)} "
            "sur la façon dont cette expérience peut servir vos "
            "enjeux, et de vous exposer ma compréhension du poste."
        )
    )


def build_cover_letter(
    candidate_id: str,
    job_offer_id: str,
    redaction_date: date | None = None,
    max_achievements: int = MAX_ACHIEVEMENTS,
) -> CoverLetter:
    """
    Assemble la lettre de motivation d'un candidat pour une offre
    déjà analysée.

    La lettre produite n'est jamais finale : elle doit être relue et
    validée par l'utilisateur avant tout envoi.
    """

    cv = build_targeted_cv(
        candidate_id=candidate_id,
        job_offer_id=job_offer_id,
    )

    # ========================================================
    # ENTREPRISE
    # ========================================================
    #
    # L'entreprise vient du CV ciblé, qui a déjà chargé l'offre : ce
    # module n'ouvre aucune session, il ne fait que mettre en forme.
    # Elle n'est pas toujours renseignée — la lettre doit rester
    # correcte sans elle, et ne jamais inventer un nom.

    company = cv.job_offer_company

    # ========================================================
    # CORPS
    # ========================================================

    paragraphs: list[LetterParagraph] = [
        _paragraphe_accroche(cv, company),
    ]

    paragraphe_competences = _paragraphe_competences(cv)

    if paragraphe_competences is not None:
        paragraphs.append(paragraphe_competences)

    for achievement in cv.achievements[:max_achievements]:
        paragraphs.append(
            _paragraphe_realisation(achievement)
        )

    paragraphs.append(_paragraphe_motivation(company))

    # ========================================================
    # OBJET ET FORMULES
    # ========================================================

    poste = cv.job_offer_title or "le poste proposé"

    objet = f"Objet : candidature au poste de {poste}"

    closing = (
        "Je vous remercie de l'attention portée à ma candidature "
        "et me tiens à votre disposition pour un entretien."
    )

    return CoverLetter(
        candidate_id=cv.candidate_id,
        full_name=cv.full_name,
        email=cv.email,
        phone=cv.phone,
        location=cv.location,
        job_offer_id=cv.job_offer_id,
        job_offer_title=cv.job_offer_title,
        company=company,
        redaction_date=redaction_date or date.today(),
        objet=objet,
        salutation="Madame, Monsieur,",
        paragraphs=paragraphs,
        closing=closing,
        signature=cv.full_name,
        claimed_skills=list(cv.skills),
        not_claimed_skills=(
            list(cv.declared_skills) + list(cv.inferred_skills)
        ),
        validated_by_user=False,
    )
