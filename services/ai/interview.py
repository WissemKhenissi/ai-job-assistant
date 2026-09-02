"""
Entretien IA d'enrichissement du Master CV.

Un seul round, volontairement large plutôt que profond (préférence
explicite de l'utilisateur, retenue après discussion) :

1. `generate_interview_questions` lit tout le profil du candidat (et,
   en option, un CV externe ou des captures d'écran fournis) et
   propose un éventail large de questions couvrant plusieurs
   expériences passées — jamais une seule ligne de questions en
   profondeur sur une expérience isolée.
2. Le candidat répond à ce qu'il veut, dans l'interface (aucune
   question n'est obligatoire) — à l'écrit, ou à l'oral (chaque
   réponse orale est transcrite par `transcribe_audio` avant d'être
   traitée comme n'importe quelle réponse texte, pour que le garde-fou
   de traçabilité ci-dessous s'applique de la même façon quelle que
   soit la modalité de saisie).
3. `propose_evidence_from_answers` ne relit QUE les réponses
   effectivement données dans cette session — jamais le reste du
   profil — et propose des formulations courtes prêtes pour le
   Master CV, chacune reliée à l'extrait de réponse qui la justifie.

Rien n'est jamais écrit automatiquement : chaque proposition est
affichée à l'utilisateur, éditable, et n'entre dans les tables
SkillDB/EvidenceDB qu'après validation explicite (voir
ui/master_cv/interview_section.py) — cette validation, avec relecture
et correction possible du texte, est une protection plus forte que le
contrôle automatique de chiffres inventés utilisé ailleurs dans le
projet.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from uuid import uuid4

from database.db import SessionLocal
from database.models import (
    AchievementDB,
    CandidateDB,
    CertificationDB,
    EducationDB,
    EvidenceDB,
    ExperienceDB,
    SkillDB,
)

from services.ai.gemini_client import (
    GeminiNotConfiguredError,
    GeminiRequestError,
    generate_multimodal,
    is_configured,
)


# Nombre de questions visé — un éventail large, pas une exploration
# exhaustive qui découragerait de répondre.
MIN_QUESTIONS = 8
MAX_QUESTIONS = 15

# Types MIME image acceptés pour les captures d'écran, transmises à
# Gemini telles quelles (pas d'extraction locale).
IMAGE_MIME_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


@dataclass(frozen=True)
class InterviewQuestion:
    question: str
    experience_id: str | None = None
    experience_label: str = ""


@dataclass(frozen=True)
class InterviewAnswer:
    question: str
    answer: str
    experience_id: str | None = None
    experience_label: str = ""


@dataclass(frozen=True)
class EvidenceProposal:
    """
    `id` est généré côté serveur (jamais par l'IA) — l'interface s'en
    sert comme clé stable de widget : les propositions sont validées
    ou rejetées une par une, et leur position dans la liste change à
    chaque suppression, donc une clé basée sur l'index mélangerait le
    texte affiché entre deux propositions différentes.
    """

    text: str
    skill_name: str
    experience_id: str | None = None
    experience_label: str = ""
    source_excerpt: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)


def _strip_json_fences(text: str) -> str:

    texte = text.strip()

    if texte.startswith("```"):
        texte = re.sub(r"^```[a-zA-Z]*\n?", "", texte)
        texte = re.sub(r"```$", "", texte.strip())

    return texte.strip()


# ============================================================
# FICHE DU PROFIL COMPLET
# ============================================================

def _build_full_profile_sheet(
    candidate_id: str,
) -> tuple[str, dict[str, str]]:
    """
    Sérialise tout le Master CV (sans filtrage par statut ni par
    offre, contrairement à letter_authoring qui cible une
    candidature précise) et renvoie, en plus, le dictionnaire
    experience_id -> libellé lisible ("Poste — Entreprise") utilisé
    pour attribuer les questions et, plus tard, les preuves validées.
    """

    db = SessionLocal()

    try:

        candidate = db.get(CandidateDB, candidate_id)

        if candidate is None:
            return "", {}

        experiences = (
            db.query(ExperienceDB)
            .filter(ExperienceDB.candidate_id == candidate_id)
            .order_by(ExperienceDB.start_date.desc())
            .all()
        )

        experience_ids = [experience.id for experience in experiences]

        achievements = (
            db.query(AchievementDB)
            .filter(AchievementDB.experience_id.in_(experience_ids))
            .all()
            if experience_ids
            else []
        )

        achievements_par_experience: dict[str, list] = {}

        for achievement in achievements:
            achievements_par_experience.setdefault(
                achievement.experience_id, []
            ).append(achievement)

        skills = (
            db.query(SkillDB)
            .filter(SkillDB.candidate_id == candidate_id)
            .all()
        )

        educations = (
            db.query(EducationDB)
            .filter(EducationDB.candidate_id == candidate_id)
            .all()
        )

        certifications = (
            db.query(CertificationDB)
            .filter(CertificationDB.candidate_id == candidate_id)
            .all()
        )

        # ----------------------------------------------------
        # LIBELLES
        # ----------------------------------------------------

        libelles = {
            experience.id: (
                f"{experience.job_title} — {experience.company}"
            )
            for experience in experiences
        }

        # ----------------------------------------------------
        # SERIALISATION
        # ----------------------------------------------------

        sections = []

        identite = [f"Nom : {candidate.first_name} {candidate.last_name}"]

        if candidate.headline:
            identite.append(f"Accroche actuelle : {candidate.headline}")

        if candidate.summary:
            identite.append(f"Résumé actuel : {candidate.summary}")

        sections.append("CANDIDAT\n" + "\n".join(identite))

        if experiences:

            blocs = []

            for experience in experiences:

                fin = (
                    experience.end_date.strftime("%Y")
                    if experience.end_date
                    else "aujourd'hui"
                )

                entete = (
                    f"- [id={experience.id}] "
                    f"{experience.job_title} — {experience.company} "
                    f"({experience.start_date.strftime('%Y')}–{fin})"
                )

                bloc = [entete]

                if experience.description:
                    bloc.append(f"  Description : {experience.description}")

                if experience.business_context:
                    bloc.append(
                        f"  Contexte : {experience.business_context}"
                    )

                for achievement in achievements_par_experience.get(
                    experience.id, []
                ):
                    bloc.append(
                        f"  Réalisation : {achievement.title}"
                        + (
                            f" — {achievement.result}"
                            if achievement.result
                            else ""
                        )
                    )

                blocs.append("\n".join(bloc))

            sections.append(
                "EXPÉRIENCES (chacune avec son identifiant [id=...], à "
                "reprendre tel quel si une question s'y rapporte)\n"
                + "\n".join(blocs)
            )

        if skills:
            sections.append(
                "COMPÉTENCES DÉJÀ DÉCLARÉES\n"
                + ", ".join(sorted({skill.name for skill in skills}))
            )

        if educations:
            sections.append(
                "FORMATION\n"
                + "\n".join(
                    f"- {education.degree} — {education.institution}"
                    for education in educations
                )
            )

        if certifications:
            sections.append(
                "CERTIFICATIONS\n"
                + "\n".join(
                    f"- {certification.name}"
                    for certification in certifications
                )
            )

        return "\n\n".join(sections), libelles

    finally:

        db.close()


# ============================================================
# GENERATION DES QUESTIONS
# ============================================================

def _build_image_parts(uploaded_files: list) -> tuple[list, str]:
    """
    Transforme les fichiers image téléversés en parties multimodales
    Gemini. Retourne aussi le texte extrait des fichiers .docx/.pdf
    (traités séparément, voir services/document_extraction.py).
    """

    from google.genai import types

    from services.document_extraction import extract_text_from_upload

    image_parts = []
    textes_documents = []

    for fichier in uploaded_files or []:

        nom = (getattr(fichier, "name", "") or "").lower()
        extension = nom.rsplit(".", 1)[-1] if "." in nom else ""

        if extension in IMAGE_MIME_TYPES:

            try:
                donnees = fichier.read()
            except Exception:
                continue

            image_parts.append(
                types.Part.from_bytes(
                    data=donnees,
                    mime_type=IMAGE_MIME_TYPES[extension],
                )
            )

        elif extension in ("docx", "pdf"):

            texte = extract_text_from_upload(fichier)

            if texte.strip():
                textes_documents.append(
                    f"--- Document fourni ({fichier.name}) ---\n{texte}"
                )

    return image_parts, "\n\n".join(textes_documents)


QUESTION_RULES = """Tu aides un candidat à enrichir son Master CV (le référentiel unique de son parcours, utilisé ensuite pour générer des CV ciblés et des lettres de motivation honnêtes).

Ta mission : proposer un ÉVENTAIL LARGE de questions de relance, entre {min_q} et {max_q}, qui couvrent PLUSIEURS expériences passées différentes — jamais une exploration en profondeur d'une seule expérience isolée. L'objectif est de faire émerger des compétences ou des détails d'expérience réels mais non encore écrits dans le Master CV.

RÈGLES :
- Base-toi sur les expériences listées ci-dessous et, si un poste recherché est indiqué, priorise les questions qui aideraient à documenter ce qui compte pour CE type de poste — sans jamais te limiter à une seule expérience.
- Si des documents ou captures d'écran sont fournis en plus, utilise-les comme contexte supplémentaire (ils peuvent mentionner des expériences ou compétences absentes du Master CV actuel) — pose des questions dessus aussi si pertinent.
- Chaque question doit être concrète et vérifiable (pas "Êtes-vous rigoureux ?" mais "Avez-vous eu à arbitrer entre plusieurs priorités concurrentes sur tel projet, et comment ?").
- N'affirme jamais rien sur le candidat : tu poses des questions, tu n'apportes aucune réponse toi-même.
- Réponds UNIQUEMENT avec un tableau JSON valide, sans texte autour, sans balisage markdown, où chaque élément est : {{"question": "...", "experience_id": "l'un des identifiants [id=...] ci-dessus, ou null si la question est transversale"}}.
"""


def generate_interview_questions(
    candidate_id: str,
    target_role: str = "",
    uploaded_files: list | None = None,
) -> tuple[list[InterviewQuestion], str]:
    """
    Génère un éventail large de questions de relance.

    Ne lève jamais d'exception : retourne une liste vide avec un
    avertissement en cas d'échec (clé absente, erreur API, réponse
    illisible).
    """

    if not is_configured():
        return [], (
            "Clé GEMINI_API_KEY non configurée : entretien IA "
            "indisponible."
        )

    fiche, libelles = _build_full_profile_sheet(candidate_id)

    if not fiche:
        return [], "Candidat introuvable."

    image_parts, textes_documents = _build_image_parts(uploaded_files)

    prompt = QUESTION_RULES.format(min_q=MIN_QUESTIONS, max_q=MAX_QUESTIONS)

    if target_role.strip():
        prompt += f"\nPoste recherché indiqué par le candidat : {target_role.strip()}\n"
    else:
        prompt += "\nAucun poste recherché indiqué — reste généraliste.\n"

    prompt += f"\n{fiche}"

    if textes_documents:
        prompt += f"\n\nDOCUMENTS FOURNIS EN COMPLÉMENT\n{textes_documents}"

    from google.genai import types

    parts = [types.Part.from_text(text=prompt)] + image_parts

    try:
        reponse = generate_multimodal(parts, temperature=0.6)

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return [], f"Génération des questions impossible ({error})."

    try:
        donnees = json.loads(_strip_json_fences(reponse))

    except json.JSONDecodeError:
        return [], "Réponse de l'IA illisible : réessayez."

    if not isinstance(donnees, list):
        return [], "Format de réponse inattendu : réessayez."

    questions: list[InterviewQuestion] = []

    for item in donnees[:MAX_QUESTIONS]:

        if not isinstance(item, dict):
            continue

        texte_question = str(item.get("question") or "").strip()

        if not texte_question:
            continue

        experience_id = item.get("experience_id")

        if experience_id not in libelles:
            experience_id = None

        questions.append(
            InterviewQuestion(
                question=texte_question,
                experience_id=experience_id,
                experience_label=(
                    libelles.get(experience_id, "") if experience_id else ""
                ),
            )
        )

    if not questions:
        return [], "Aucune question exploitable n'a été générée."

    return questions, ""


# ============================================================
# TRANSCRIPTION AUDIO
# ============================================================

# Types MIME audio produits par st.audio_input (enregistrement
# navigateur) — la valeur exacte varie selon le navigateur, on garde
# une liste large plutôt que d'imposer un seul format.
AUDIO_MIME_TYPES = {"audio/wav", "audio/webm", "audio/ogg", "audio/mp4"}


def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> tuple[str, str]:
    """
    Transcrit un enregistrement audio en texte via Gemini.

    Chaque réponse orale passe par ici avant d'être traitée comme
    n'importe quelle réponse texte : le garde-fou de traçabilité de
    propose_evidence_from_answers (l'extrait cité doit apparaître mot
    pour mot dans la réponse) ne fonctionne que sur du texte — la
    transcription est donc une étape obligatoire, jamais un simple
    confort, pas un raccourci qui contournerait le garde-fou.

    Ne lève jamais d'exception : retourne une chaîne vide avec un
    avertissement en cas d'échec.
    """

    if not audio_bytes:
        return "", ""

    if not is_configured():
        return "", (
            "Clé GEMINI_API_KEY non configurée : transcription audio "
            "indisponible."
        )

    from google.genai import types

    parts = [
        types.Part.from_text(
            text=(
                "Transcris fidèlement cet enregistrement audio en "
                "français. Réponds UNIQUEMENT avec la transcription "
                "du texte parlé, mot pour mot — pas de reformulation, "
                "pas de résumé, pas de commentaire, pas de correction "
                "de ce qui a été dit."
            )
        ),
        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
    ]

    try:
        texte = generate_multimodal(parts, temperature=0.0)

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return "", f"Transcription audio impossible ({error})."

    return texte.strip(), ""


# ============================================================
# PROPOSITION DE PREUVES A PARTIR DES REPONSES
# ============================================================

EVIDENCE_RULES = """Voici des questions posées à un candidat pour enrichir son Master CV, et les réponses qu'il a effectivement données. Ta mission : proposer des formulations courtes, prêtes pour un Master CV, à partir de CE QUI A ÉTÉ RÉELLEMENT RÉPONDU CI-DESSOUS — RIEN D'AUTRE.

RÈGLES ABSOLUES :
- N'utilise QUE le contenu des réponses ci-dessous. N'utilise aucune autre connaissance sur le candidat, aucune supposition.
- Chaque proposition doit être directement retrouvable dans une réponse précise — cite l'extrait qui la justifie.
- N'invente aucun chiffre, aucun résultat, aucune compétence qui ne soit pas clairement énoncée dans la réponse.
- Une réponse vague ou évasive ne doit donner lieu à aucune proposition plutôt qu'à une proposition exagérée.
- Associe si possible chaque proposition à un nom de compétence court (ex. "Gestion de budget", "Négociation fournisseur").
- Réponds UNIQUEMENT avec un tableau JSON valide, sans texte autour, sans balisage markdown : [{"text": "phrase courte prête pour le Master CV", "skill_name": "...", "source_excerpt": "extrait exact de la réponse qui justifie cette phrase"}].
- Si aucune réponse n'apporte de matière exploitable, réponds avec un tableau vide []."""


def propose_evidence_from_answers(
    answers: list[InterviewAnswer],
    inspiration_questions: list[InterviewQuestion] | None = None,
) -> tuple[list[EvidenceProposal], str]:
    """
    Ne lit que les réponses transmises ici — jamais le reste du
    Master CV — et propose des preuves à valider explicitement par
    l'utilisateur avant toute écriture en base.

    `inspiration_questions`, optionnel, sert uniquement de contexte
    (mode "réponse libre" : le candidat répond en un seul bloc à
    l'ensemble des questions plutôt qu'une par une) — l'IA voit quelles
    pistes avaient été proposées, mais le garde-fou de traçabilité
    porte toujours exclusivement sur le texte des réponses, jamais sur
    ces questions elles-mêmes.
    """

    reponses_utiles = [
        answer for answer in answers if answer.answer.strip()
    ]

    if not reponses_utiles:
        return [], "Aucune réponse fournie."

    if not is_configured():
        return [], (
            "Clé GEMINI_API_KEY non configurée : impossible de "
            "générer des propositions."
        )

    blocs = []

    for answer in reponses_utiles:

        bloc = f"Question : {answer.question}\n"

        if answer.experience_label:
            bloc += f"(à propos de : {answer.experience_label})\n"

        bloc += f"Réponse du candidat : {answer.answer.strip()}"

        blocs.append(bloc)

    prompt = EVIDENCE_RULES

    if inspiration_questions:
        prompt += (
            "\n\nPour information, voici les pistes de réflexion "
            "proposées au candidat avant sa réponse libre — ce ne "
            "sont PAS des réponses, seulement le contexte de ce qui "
            "était recherché, à ne jamais utiliser comme source de "
            "preuve :\n"
            + "\n".join(f"- {q.question}" for q in inspiration_questions)
        )

    prompt += "\n\n" + "\n\n".join(blocs)

    try:
        reponse = generate_multimodal([prompt], temperature=0.3)

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return [], f"Génération des propositions impossible ({error})."

    try:
        donnees = json.loads(_strip_json_fences(reponse))

    except json.JSONDecodeError:
        return [], "Réponse de l'IA illisible : réessayez."

    if not isinstance(donnees, list):
        return [], "Format de réponse inattendu : réessayez."

    # Association question -> (experience_id, experience_label), pour
    # relier chaque proposition à la bonne expérience via l'extrait
    # source qu'elle cite.
    par_extrait_source: list[InterviewAnswer] = reponses_utiles

    propositions: list[EvidenceProposal] = []

    for item in donnees:

        if not isinstance(item, dict):
            continue

        texte = str(item.get("text") or "").strip()

        if not texte:
            continue

        source_excerpt = str(item.get("source_excerpt") or "").strip()

        # Garde-fou : l'extrait cité doit réellement provenir d'une
        # réponse donnée — sinon la proposition est écartée plutôt
        # que gardée sans preuve de traçabilité.
        answer_correspondante = next(
            (
                answer
                for answer in par_extrait_source
                if source_excerpt and source_excerpt in answer.answer
            ),
            None,
        )

        if answer_correspondante is None:
            continue

        propositions.append(
            EvidenceProposal(
                text=texte,
                skill_name=str(item.get("skill_name") or "").strip(),
                experience_id=answer_correspondante.experience_id,
                experience_label=answer_correspondante.experience_label,
                source_excerpt=source_excerpt,
            )
        )

    return propositions, ""
