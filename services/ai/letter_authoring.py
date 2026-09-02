"""
Rédaction de la lettre de motivation par l'IA (Gemini).

Différence avec les deux autres approches du projet :

- `services.letter.generation` assemble une lettre déterministe à
  partir de formules fixes — aucune IA.
- `services.ai.reformulation` reformule, phrase par phrase, un texte
  déjà écrit par le générateur déterministe — l'IA ne fait que
  polir.
- Ce module fait composer à l'IA l'argumentaire complet de la lettre
  (accroche, arguments, conclusion) à partir d'une **fiche de faits**
  structurée — jamais un texte à copier. C'est la seule façon de
  produire une vraie argumentation plutôt qu'un empilement de
  formules ou une reformulation de phrases pauvres au départ.

Le principe non négociable reste identique : rien n'est affirmé qui
ne soit dans le Master CV, dans les motivations explicitement
fournies par le candidat, ou dans le texte de l'offre. Deux lignes de
défense :

1. Un prompt de règles détaillé qui interdit explicitement toute
   invention (repris du cahier des charges de l'utilisateur).
2. Un contrôle automatique : aucun nombre absent de la fiche de faits
   (et donc du Master CV / des motivations / de l'offre) ne doit
   apparaître dans la lettre générée.

Si l'IA n'est pas configurée, échoue, ou que le garde-fou se
déclenche, la lettre déterministe (services.letter.generation) est
utilisée à la place, avec un avertissement — la lettre reste toujours
générable sans IA, comme le reste du projet.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

from database.db import SessionLocal
from database.models import CandidateDB
from models.matching import JobMatchDB
from models.skill_match import JobSkillMatchDB

from services.ai.gemini_client import (
    GeminiNotConfiguredError,
    GeminiRequestError,
    generate_text,
    is_configured,
)
from services.cv import build_targeted_cv
from services.cv.results import TargetedCV
from services.job_service import get_job_offer_text
from services.letter.generation import build_cover_letter
from services.letter.results import CoverLetter, LetterParagraph


# Longueur maximale du texte de l'offre transmise au prompt : l'offre
# est ici l'entrée principale (pas un simple réglage de vocabulaire
# comme dans reformulation.py), d'où une limite plus généreuse.
MAX_JOB_EXCERPT = 4000


LETTER_RULES = """Tu es un expert en recrutement, en communication professionnelle et en rédaction de lettres de motivation.

Ta mission est de rédiger le corps d'une lettre de motivation personnalisée, crédible, naturelle et convaincante, à partir de la fiche de faits ci-dessous et de l'offre d'emploi. La lettre doit donner envie au recruteur de rencontrer le candidat. Elle ne doit jamais être une simple reformulation du CV, ni une lettre générique où seuls le nom de l'entreprise et l'intitulé du poste changeraient.

SOURCE DE VÉRITÉ
La fiche de faits ci-dessous est la seule source autorisée, avec le texte de l'offre. Interdiction absolue d'inventer une expérience, une responsabilité, une compétence, un diplôme, une certification, un résultat, un chiffre, une mission, un outil, une connaissance de l'entreprise, une motivation personnelle non fournie, une réussite, ou toute autre information sur le candidat. Si une information n'est pas dans la fiche de faits, ne l'invente pas — n'en parle pas.

OBJECTIF
La lettre doit répondre implicitement à trois questions : pourquoi ce candidat est pertinent pour ce poste, pourquoi ce poste et cette entreprise peuvent être pertinents pour lui, pourquoi il serait intéressant de le rencontrer.

PERSONNALISATION
Analyse l'offre (responsabilités, compétences prioritaires, enjeux, séniorité, secteur) et le candidat (expériences et réalisations les plus pertinentes, compétences prouvées vs. transférables, écarts éventuels). Ne sélectionne pas automatiquement toutes les compétences du candidat : choisis uniquement celles qui renforcent réellement cette candidature précise.

LOGIQUE VOUS / MOI / NOUS
Quand c'est pertinent, construis implicitement la lettre autour de : ce que l'entreprise recherche (VOUS), ce que le candidat apporte concrètement (MOI), pourquoi la rencontre est pertinente (NOUS) — jamais sous forme de titres visibles, intégré naturellement dans le texte.

PREUVE PLUTÔT QU'AFFIRMATION
Préfère toujours une preuve concrète issue de la fiche de faits à une affirmation générique ("dynamique, motivé, organisé"). Relie une compétence importante à une expérience ou une réalisation réelle quand la fiche le permet.

NE PAS RÉPÉTER LE CV
Le CV répond à "qu'avez-vous fait ?". La lettre doit répondre à "pourquoi ce parcours est-il pertinent pour ce poste ?" — utilise les expériences pour construire une argumentation, pas pour les énumérer.

HIÉRARCHISATION
Ne cherche pas à tout mentionner. Identifie 2 à 4 arguments les plus pertinents pour cette candidature précise. Une lettre courte et ciblée vaut mieux qu'une lettre exhaustive.

ÉCARTS
Si une compétence demandée manque à la fiche de faits, ne mens pas et ne la masque pas artificiellement. Valorise plutôt les compétences transférables, les expériences proches, la capacité d'apprentissage si elle est démontrée par la fiche.

TON
Professionnel, humain, naturel, précis, confiant, sobre, crédible. Évite les formulations excessivement enthousiastes, les superlatifs, les phrases artificiellement flatteuses, le langage corporate, les clichés, les tournures scolaires, les phrases trop longues, les répétitions. Ne cherche pas à impressionner par le vocabulaire — cherche à convaincre par la pertinence.

CLICHÉS À ÉVITER (sauf si le contexte les justifie réellement)
"Je vous adresse ma candidature avec beaucoup d'enthousiasme", "Votre entreprise est un leader dans son domaine", "Je suis dynamique, motivé et rigoureux", "Je serais ravi de mettre mes compétences au service de votre entreprise", "Cette opportunité représente une véritable chance", "Fort de plusieurs années d'expérience...".

STRUCTURE
Accroche courte et contextualisée (poste visé, pourquoi le candidat est pertinent) puis 2 ou 3 arguments démontrés par le parcours (compétence ou expérience + contexte + action + résultat quand connu + lien avec le poste), puis pourquoi cette opportunité est cohérente avec le projet du candidat (uniquement si la fiche donne des motivations), puis une conclusion ouvrant naturellement vers un entretien. Ne force jamais un résultat si la fiche n'en fournit pas.

MOTIVATION
Ne prétends jamais connaître une motivation personnelle non fournie dans la fiche. Si la fiche contient des motivations explicites (reconversion, intérêt pour le secteur ou l'entreprise), utilise-les. Sinon, appuie-toi uniquement sur les éléments objectifs du profil et de l'offre — ne fabrique aucune passion.

ENTREPRISE
N'utilise des informations sur l'entreprise que si elles figurent dans l'offre. Ne prétends jamais connaître sa culture, ses valeurs, sa stratégie ou son actualité si ce n'est pas écrit dans l'offre. N'invente aucun lien personnel avec l'entreprise.

LONGUEUR ET STYLE
Vise 300 à 450 mots ; la lettre doit idéalement tenir sur une page. Phrases de longueur variée, formulations simples, mots-clés de l'offre repris seulement quand ils sont naturellement pertinents et véridiques — ne surcharge pas le texte de mots-clés.

FORMAT DE RÉPONSE
Réponds uniquement avec le corps de la lettre : pas d'objet, pas de formule d'appel ("Madame, Monsieur"), pas de formule de politesse finale, pas de signature — ces éléments sont ajoutés séparément par l'application. Sépare les paragraphes par une ligne vide. Pas de titre, pas de commentaire, pas d'explication de ta démarche : seulement le texte final.

CONTRÔLE FINAL AVANT DE RÉPONDRE
Vérifie mentalement : chaque affirmation est-elle retrouvable dans la fiche de faits ou dans l'offre ? Aucun chiffre, résultat, compétence ou motivation n'a été inventé ? La lettre est spécifique à ce candidat et à cette offre, elle ne répète pas simplement le CV, les lacunes éventuelles ne sont pas dissimulées par une fausse affirmation, le ton est naturel et sans cliché, la conclusion donne envie d'échanger."""


def _digits(text: str) -> set[str]:
    """Tous les nombres (suites de chiffres) présents dans un texte."""

    return set(re.findall(r"\d+", text))


def _get_motivations(candidate_id: str) -> str:

    db = SessionLocal()

    try:
        candidate = db.get(CandidateDB, candidate_id)

        return (candidate.motivations or "").strip() if candidate else ""

    finally:
        db.close()


def _gather_matching_detail(
    candidate_id: str,
    job_offer_id: str,
) -> tuple[list[str], list[str], list[tuple[str, str, str]]]:
    """
    Détail de matching déjà persisté (forces, points de vigilance,
    explication par compétence) — plus riche que ce que le CV ciblé
    expose, utile comme contexte pour l'IA. Renvoie des listes vides
    si l'offre n'a pas été analysée (ne devrait pas arriver ici, le
    CV ciblé l'exige déjà, mais on reste défensif).
    """

    db = SessionLocal()

    try:
        job_match = (
            db.query(JobMatchDB)
            .filter(
                JobMatchDB.candidate_id == candidate_id,
                JobMatchDB.job_offer_id == job_offer_id,
            )
            .one_or_none()
        )

        if job_match is None:
            return [], [], []

        skill_matches = (
            db.query(JobSkillMatchDB)
            .filter(JobSkillMatchDB.job_match_id == job_match.id)
            .all()
        )

        explications = [
            (row.skill, row.status, row.explanation.strip())
            for row in skill_matches
            if row.explanation and row.explanation.strip()
        ]

        return (
            list(job_match.strengths or []),
            list(job_match.weaknesses or []),
            explications,
        )

    finally:
        db.close()


def _build_fact_sheet(
    cv: TargetedCV,
    motivations: str,
    strengths: list[str],
    weaknesses: list[str],
    explications: list[tuple[str, str, str]],
    job_text: str,
) -> str:
    """
    Sérialise tout ce que l'IA a le droit d'utiliser, en sections
    étiquetées. Ce n'est jamais un texte à recopier tel quel — c'est
    la matière première à partir de laquelle composer.
    """

    sections: list[str] = []

    # --------------------------------------------------------
    # CANDIDAT
    # --------------------------------------------------------

    identite = [f"Nom : {cv.full_name}"]

    if cv.headline:
        identite.append(f"Accroche : {cv.headline}")

    if cv.summary:
        identite.append(f"Résumé existant : {cv.summary}")

    if cv.availability:
        identite.append(f"Disponibilité : {cv.availability}")

    if cv.languages:
        identite.append(f"Langues : {cv.languages}")

    sections.append("CANDIDAT\n" + "\n".join(identite))

    # --------------------------------------------------------
    # MOTIVATIONS
    # --------------------------------------------------------

    if motivations:
        sections.append(
            "MOTIVATIONS ET PROJET PROFESSIONNEL (fournies "
            "explicitement par le candidat)\n" + motivations
        )
    else:
        sections.append(
            "MOTIVATIONS ET PROJET PROFESSIONNEL : aucune information "
            "fournie par le candidat — n'invente aucune motivation "
            "personnelle."
        )

    # --------------------------------------------------------
    # COMPETENCES PROUVEES
    # --------------------------------------------------------

    if cv.skill_groups:

        lignes = [
            f"- {groupe.category} : {', '.join(groupe.skills)}"
            for groupe in cv.skill_groups
        ]

        sections.append(
            "COMPÉTENCES PROUVÉES (déclarées et démontrées par une "
            "preuve concrète)\n" + "\n".join(lignes)
        )

    # --------------------------------------------------------
    # COMPETENCES A NE PAS AFFIRMER
    # --------------------------------------------------------

    non_affirmables = list(cv.declared_skills) + list(cv.inferred_skills)

    if non_affirmables:
        sections.append(
            "COMPÉTENCES À NE PAS PRÉSENTER COMME ACQUISES (déclarées "
            "sans preuve, ou seulement déduites du parcours — n'en "
            "fais jamais des compétences prouvées) : "
            + ", ".join(non_affirmables)
        )

    # --------------------------------------------------------
    # EXPERIENCES
    # --------------------------------------------------------

    if cv.experiences:

        blocs = []

        for experience in cv.experiences:

            fin = (
                experience.end_date.strftime("%Y")
                if experience.end_date
                else "aujourd'hui"
            )

            entete = (
                f"- {experience.job_title} — {experience.company} "
                f"({experience.start_date.strftime('%Y')}–{fin}"
            )

            if experience.location:
                entete += f", {experience.location}"

            entete += ")"

            bloc = [entete]

            if experience.business_context:
                bloc.append(f"  Contexte : {experience.business_context}")

            for ligne in experience.lines:
                bloc.append(f"  · {ligne.text}")

            blocs.append("\n".join(bloc))

        sections.append(
            "EXPÉRIENCES RETENUES POUR CETTE CANDIDATURE\n"
            + "\n".join(blocs)
        )

    # --------------------------------------------------------
    # REALISATIONS
    # --------------------------------------------------------

    if cv.achievements:

        blocs = []

        for achievement in cv.achievements:

            bloc = [f"- {achievement.title}"]

            if achievement.situation:
                bloc.append(f"  Situation : {achievement.situation}")

            if achievement.action:
                bloc.append(f"  Action : {achievement.action}")

            if achievement.result:
                bloc.append(f"  Résultat : {achievement.result}")

            if achievement.metrics:
                bloc.append(f"  Indicateurs : {achievement.metrics}")

            blocs.append("\n".join(bloc))

        sections.append("RÉALISATIONS\n" + "\n".join(blocs))

    # --------------------------------------------------------
    # FORMATION ET CERTIFICATIONS
    # --------------------------------------------------------

    if cv.educations:

        lignes = [
            f"- {education.degree} — {education.institution}"
            + (
                f" ({education.end_year})"
                if education.end_year
                else ""
            )
            for education in cv.educations
        ]

        sections.append("FORMATION\n" + "\n".join(lignes))

    if cv.certifications:

        lignes = [
            f"- {certification.name}"
            + (
                f" — {certification.organization}"
                if certification.organization
                else ""
            )
            + (
                f" ({certification.obtained_year})"
                if certification.obtained_year
                else ""
            )
            for certification in cv.certifications
        ]

        sections.append("CERTIFICATIONS\n" + "\n".join(lignes))

    # --------------------------------------------------------
    # ANALYSE D'ADEQUATION DEJA REALISEE
    # --------------------------------------------------------

    if strengths or weaknesses or explications:

        bloc = [
            "ANALYSE DE L'ADÉQUATION AVEC L'OFFRE (déjà réalisée par "
            "le moteur de matching)"
        ]

        if strengths:
            bloc.append("Points forts : " + " ; ".join(strengths))

        if weaknesses:
            bloc.append(
                "Points de vigilance (écarts réels, ne pas masquer) : "
                + " ; ".join(weaknesses)
            )

        if explications:

            bloc.append("Détail par compétence :")

            for skill, status, explanation in explications:
                bloc.append(f"  - {skill} ({status}) : {explanation}")

        sections.append("\n".join(bloc))

    # --------------------------------------------------------
    # OFFRE
    # --------------------------------------------------------

    sections.append(
        "OFFRE D'EMPLOI\n"
        f"Poste : {cv.job_offer_title or 'non précisé'}\n"
        f"Entreprise : {cv.job_offer_company or 'non précisée'}\n"
        f"Texte de l'offre :\n{job_text[:MAX_JOB_EXCERPT]}"
    )

    return "\n\n".join(sections)


def _split_paragraphs(texte: str) -> list[str]:
    """Découpe le corps généré en paragraphes, sur les lignes vides."""

    morceaux = re.split(r"\n\s*\n", texte.strip())

    return [bloc.strip() for bloc in morceaux if bloc.strip()]


def build_ai_letter(
    candidate_id: str,
    job_offer_id: str,
    redaction_date: date | None = None,
) -> tuple[CoverLetter, list[str]]:
    """
    Fait rédiger le corps de la lettre par Gemini à partir d'une fiche
    de faits, avec repli automatique sur la lettre déterministe en
    cas d'échec ou de garde-fou déclenché.

    Retourne toujours une CoverLetter utilisable (IA ou repli) et la
    liste des avertissements rencontrés — jamais vide en cas de repli,
    toujours vide en cas de succès complet.
    """

    lettre_deterministe = build_cover_letter(
        candidate_id=candidate_id,
        job_offer_id=job_offer_id,
        redaction_date=redaction_date,
    )

    if not is_configured():
        return lettre_deterministe, [
            "Clé GEMINI_API_KEY non configurée : lettre déterministe "
            "utilisée."
        ]

    cv = build_targeted_cv(
        candidate_id=candidate_id,
        job_offer_id=job_offer_id,
    )

    motivations = _get_motivations(candidate_id)

    strengths, weaknesses, explications = _gather_matching_detail(
        candidate_id,
        job_offer_id,
    )

    job_text = get_job_offer_text(job_offer_id)

    fiche = _build_fact_sheet(
        cv,
        motivations,
        strengths,
        weaknesses,
        explications,
        job_text,
    )

    prompt = f"{LETTER_RULES}\n\n{fiche}"

    try:
        corps_genere = generate_text(prompt, temperature=0.6)

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return lettre_deterministe, [
            f"Rédaction IA indisponible ({error}) : lettre "
            "déterministe utilisée."
        ]

    # ------------------------------------------------------------
    # GARDE-FOU : aucun nombre nouveau ne doit apparaître.
    # ------------------------------------------------------------
    #
    # Comparé à la fiche de faits entière (Master CV + motivations +
    # offre), pas seulement à un paragraphe isolé comme dans
    # reformulation.py — c'est tout ce que la lettre a le droit
    # d'affirmer.

    chiffres_inventes = _digits(corps_genere) - _digits(fiche)

    if chiffres_inventes:
        return lettre_deterministe, [
            "Lettre IA rejetée : elle introduisait des chiffres "
            f"absents de la fiche de faits ({', '.join(sorted(chiffres_inventes))})"
            ". Lettre déterministe utilisée."
        ]

    paragraphes_texte = _split_paragraphs(corps_genere)

    if not paragraphes_texte:
        return lettre_deterministe, [
            "Lettre IA rejetée : réponse vide. Lettre déterministe "
            "utilisée."
        ]

    # La traçabilité fine (quelle preuve justifie quelle phrase)
    # n'est plus possible sur un texte librement composé — limite
    # assumée, compensée par le panneau des faits affiché à côté de
    # la lettre dans l'interface, pour que la relecture humaine ait
    # quelque chose de concret à vérifier.
    paragraphs = [
        LetterParagraph(text=texte, sources=())
        for texte in paragraphes_texte
    ]

    lettre_ia = replace(
        lettre_deterministe,
        paragraphs=paragraphs,
        validated_by_user=False,
    )

    return lettre_ia, []
