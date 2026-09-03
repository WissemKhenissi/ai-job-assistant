"""
Analyse d'une offre par l'IA (Gemini) : catégorisation (type de
contrat, télétravail) et extraction des compétences attendues, ainsi
qu'une synthèse qualitative de l'adéquation avec le Master CV.

Deux usages distincts, deux niveaux de risque différents :

- `analyze_job_offer_with_ai` lit l'OFFRE, jamais le candidat : le
  risque n'est pas d'affirmer quelque chose de faux sur le candidat,
  mais de mal classer le texte. Garde-fous légers (valeurs limitées à
  un ensemble connu, compétences filtrées à celles réellement
  présentes dans le texte).
- `generate_fit_synthesis` commente le résultat du moteur de matching
  DÉJÀ CALCULÉ (services.matching) — le moteur honnête
  (prouvé/déclaré/déduit/manquant) reste seul responsable du score et
  des statuts ; l'IA ne fait que les mettre en mots, jamais les
  recalculer. C'est un avis indicatif, jamais présenté comme le score
  officiel.

Dans les deux cas : si l'IA n'est pas configurée ou échoue, la
fonctionnalité se dégrade proprement (résultat vide + avertissement)
plutôt que de bloquer l'analyse déterministe, qui reste le cœur du
projet et fonctionne sans IA.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

from database.db import SessionLocal
from models.job import JobOfferDB
from models.matching import JobMatchDB
from models.skill_match import JobSkillMatchDB

from services.text_numbers import numbers_in

from services.ai.gemini_client import (
    GeminiNotConfiguredError,
    GeminiRequestError,
    generate_text,
    is_configured,
)


# Longueur maximale du texte d'offre transmis au prompt.
MAX_JOB_EXCERPT = 6000

ALLOWED_CONTRACT_TYPES = {"CDI", "CDD", "Freelance", "Stage"}
ALLOWED_REMOTE_POLICIES = {"Sur site", "Hybride", "Télétravail complet"}


def _normalize_loose(text: str) -> str:
    """Minuscules, sans accents — suffisant pour un contrôle de présence."""

    normalized = unicodedata.normalize("NFKD", text)

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    return normalized.casefold()


def _strip_json_fences(text: str) -> str:
    """
    Gemini respecte rarement à 100 % la consigne « pas de balisage » :
    il enveloppe parfois sa réponse dans un bloc ```json ... ```.
    """

    texte = text.strip()

    if texte.startswith("```"):

        texte = re.sub(r"^```[a-zA-Z]*\n?", "", texte)
        texte = re.sub(r"```$", "", texte.strip())

    return texte.strip()


# ============================================================
# CATEGORISATION DE L'OFFRE
# ============================================================

@dataclass(frozen=True)
class JobOfferAnalysis:
    contract_type: str = ""
    remote_policy: str = ""
    remote_details: str = ""
    required_skills: list[str] = field(default_factory=list)
    warning: str = ""


def analyze_job_offer_with_ai(job_text: str) -> JobOfferAnalysis:
    """
    Catégorise une offre (type de contrat, télétravail) et en extrait
    les compétences explicitement mentionnées.

    Ne lève jamais d'exception : en cas d'indisponibilité ou d'échec,
    retourne un résultat vide avec un avertissement — l'analyse
    déterministe (catalogue de compétences + sélection manuelle des
    menus déroulants) reste utilisable sans IA.
    """

    if not job_text.strip():
        return JobOfferAnalysis()

    if not is_configured():
        return JobOfferAnalysis(
            warning=(
                "Clé GEMINI_API_KEY non configurée : catégorisation "
                "et extraction automatiques indisponibles."
            )
        )

    prompt = (
        "Tu analyses le texte d'une offre d'emploi. Réponds "
        "UNIQUEMENT avec un objet JSON valide, sans texte autour, "
        "sans balisage markdown, avec exactement ces clés :\n\n"
        "{\n"
        '  "contract_type": une valeur EXACTE parmi "CDI", "CDD", '
        '"Freelance", "Stage", ou "" si non précisé ou autre,\n'
        '  "remote_policy": une valeur EXACTE parmi "Sur site", '
        '"Hybride", "Télétravail complet", ou "" si non précisé,\n'
        '  "remote_details": une courte précision UNIQUEMENT si '
        "elle est explicitement écrite dans le texte (ex. \"2 jours "
        'de télétravail par semaine\"), "" sinon — n\'invente jamais '
        "un nombre de jours qui n'est pas écrit,\n"
        '  "required_skills": une liste de compétences, outils ou '
        "technologies EXPLICITEMENT mentionnés dans le texte, tels "
        "qu'écrits, sans inventer\n"
        "}\n\n"
        "RÈGLES ABSOLUES :\n"
        "- N'invente rien : si une information n'est pas "
        "explicitement dans le texte, laisse le champ vide (chaîne "
        "vide ou liste vide).\n"
        "- contract_type et remote_policy doivent être EXACTEMENT "
        "l'une des valeurs autorisées ci-dessus, ou une chaîne "
        "vide — jamais une autre formulation.\n\n"
        f"Texte de l'offre :\n{job_text[:MAX_JOB_EXCERPT]}"
    )

    try:
        reponse = generate_text(prompt, temperature=0.1)

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return JobOfferAnalysis(
            warning=f"Analyse IA de l'offre indisponible ({error})."
        )

    try:
        donnees = json.loads(_strip_json_fences(reponse))

    except json.JSONDecodeError:
        return JobOfferAnalysis(
            warning=(
                "Analyse IA de l'offre rejetée : réponse illisible."
            )
        )

    if not isinstance(donnees, dict):
        return JobOfferAnalysis(
            warning=(
                "Analyse IA de l'offre rejetée : format inattendu."
            )
        )

    contract_type = donnees.get("contract_type") or ""
    if contract_type not in ALLOWED_CONTRACT_TYPES:
        contract_type = ""

    remote_policy = donnees.get("remote_policy") or ""
    if remote_policy not in ALLOWED_REMOTE_POLICIES:
        remote_policy = ""

    remote_details_brut = str(donnees.get("remote_details") or "").strip()

    # Garde-fou léger : un chiffre de précision (nombre de jours) qui
    # n'apparaît nulle part dans le texte source est probablement
    # inventé — on écarte la précision plutôt que de la garder telle
    # quelle dans ce cas.
    if remote_details_brut and (
        numbers_in(remote_details_brut) - numbers_in(job_text)
    ):
        remote_details_brut = ""

    skills_bruts = donnees.get("required_skills") or []

    if not isinstance(skills_bruts, list):
        skills_bruts = []

    normalized_job_text = _normalize_loose(job_text)

    required_skills = []

    for skill in skills_bruts:

        if not isinstance(skill, str):
            continue

        skill = skill.strip()

        if not skill:
            continue

        # Garde-fou : la compétence doit réellement apparaître dans
        # le texte de l'offre — une extraction n'est pas une
        # invention.
        if _normalize_loose(skill) not in normalized_job_text:
            continue

        required_skills.append(skill)

    return JobOfferAnalysis(
        contract_type=contract_type,
        remote_policy=remote_policy,
        remote_details=remote_details_brut,
        required_skills=required_skills,
    )


# ============================================================
# SYNTHESE QUALITATIVE DE L'ADEQUATION
# ============================================================

@dataclass(frozen=True)
class FitSynthesisResult:
    text: str = ""
    warning: str = ""


def generate_fit_synthesis(
    candidate_id: str,
    job_offer_id: str,
) -> FitSynthesisResult:
    """
    Avis IA court sur l'adéquation candidat/offre, à partir du
    résultat DÉJÀ CALCULÉ par le moteur de matching honnête — l'IA ne
    recalcule rien, elle met en mots un résultat qui existe déjà.

    Jamais présenté comme le score officiel : c'est à l'appelant de
    l'afficher clairement comme un avis indicatif.
    """

    if not is_configured():
        return FitSynthesisResult(
            warning=(
                "Clé GEMINI_API_KEY non configurée : avis IA "
                "indisponible."
            )
        )

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
            return FitSynthesisResult(
                warning=(
                    "Analysez d'abord l'annonce pour obtenir un avis "
                    "IA sur l'adéquation."
                )
            )

        skill_matches = (
            db.query(JobSkillMatchDB)
            .filter(JobSkillMatchDB.job_match_id == job_match.id)
            .all()
        )

        score_global = job_match.score_global
        strengths = list(job_match.strengths or [])
        weaknesses = list(job_match.weaknesses or [])

        lignes_detail = [
            f"- {row.skill} : statut={row.status}"
            + (f" ({row.explanation})" if row.explanation else "")
            for row in skill_matches
        ]

    finally:

        db.close()

    contexte = (
        f"Score global déjà calculé : {score_global:.0f}/100\n\n"
        "Détail par compétence (statut déjà déterminé, ne pas le "
        "recalculer) :\n" + "\n".join(lignes_detail) + "\n\n"
        "Points forts déjà identifiés : "
        + (", ".join(strengths) if strengths else "aucun")
        + "\n"
        "Points de vigilance déjà identifiés : "
        + (", ".join(weaknesses) if weaknesses else "aucun")
    )

    prompt = (
        "Tu es un conseiller carrière. Voici le résultat DÉJÀ "
        "CALCULÉ d'une analyse de correspondance entre le profil "
        "d'un candidat et une offre d'emploi. Rédige un avis court "
        "(3 à 5 phrases), en langage naturel, professionnel et "
        "honnête, sur l'adéquation entre ce profil et cette offre.\n"
        "\n"
        "RÈGLES ABSOLUES :\n"
        "- N'affirme JAMAIS qu'une compétence est acquise si son "
        "statut ci-dessous n'est pas 'proven' ou 'declared'.\n"
        "- Une compétence 'inferred' est une hypothèse déduite du "
        "parcours, jamais une certitude — dis-le explicitement si tu "
        "la mentionnes.\n"
        "- Une compétence 'missing' est un écart réel : ne le "
        "minimise pas, ne le dissimule pas.\n"
        "- N'invente aucun chiffre, aucune compétence, aucun fait "
        "absent de ce qui suit.\n"
        "- Reste synthétique : 3 à 5 phrases, pas de liste à puces, "
        "pas de titre, pas de formule d'introduction.\n\n"
        f"{contexte}"
    )

    try:
        reponse = generate_text(prompt, temperature=0.5)

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return FitSynthesisResult(
            warning=f"Avis IA indisponible ({error})."
        )

    if not reponse.strip():
        return FitSynthesisResult(
            warning="Avis IA rejeté : réponse vide."
        )

    # Garde-fou numérique : tout ce que le contexte fourni contient
    # est autorisé, le reste ne doit pas apparaître dans l'avis.
    chiffres_inventes = numbers_in(reponse) - numbers_in(contexte)

    if chiffres_inventes:
        return FitSynthesisResult(
            warning=(
                "Avis IA rejeté : il introduisait des chiffres non "
                f"justifiés ({', '.join(sorted(chiffres_inventes))})."
            )
        )

    return FitSynthesisResult(text=reponse.strip())
