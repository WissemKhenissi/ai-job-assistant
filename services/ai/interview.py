"""
Entretien IA d'enrichissement du Master CV.

Le parcours se déroule **expérience par expérience**, en commençant
par la plus récente (structure choisie par l'utilisateur après avoir
comparé plusieurs options) :

1. Le candidat **raconte** librement une expérience, à l'écrit ou à
   l'oral. Aucun appel IA à ce stade : on le laisse parler.
2. `generate_followup_questions` lit ce récit, la fiche de CETTE
   expérience et le poste recherché, puis pose une série de relances
   ciblées — outils, méthodes, résultats, formations, interlocuteurs,
   arbitrages — sans jamais redemander ce qui a déjà été dit.
3. Le candidat y répond, toujours en un seul bloc, à l'écrit ou à
   l'oral (toute réponse orale passe d'abord par `transcribe_audio`,
   pour que le garde-fou de traçabilité ci-dessous s'applique de la
   même façon quelle que soit la modalité de saisie).
4. `propose_evidence_from_answers` ne relit QUE ce que le candidat a
   effectivement dit dans cette session — jamais le reste du profil —
   et propose des lignes d'expérience et compétences prêtes pour le
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
    ExperienceDB,
    SkillDB,
)

from services.ai.gemini_client import (
    GEMINI_AUDIO_TIMEOUT_MS,
    GeminiNotConfiguredError,
    GeminiRequestError,
    generate_multimodal,
    is_configured,
)


# Nombre de questions visé — un éventail large, pas une exploration
# exhaustive qui découragerait de répondre.
MIN_FOLLOWUP_QUESTIONS = 4
MAX_FOLLOWUP_QUESTIONS = 8

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


def _forme_comparable(texte: str) -> str:
    """
    Forme normalisée d'une question, pour repérer un doublon : sans
    accents, minuscules, ponctuation et espaces multiples écrasés.
    """

    import unicodedata

    normalise = unicodedata.normalize("NFKD", texte)

    normalise = "".join(
        caractere
        for caractere in normalise
        if not unicodedata.combining(caractere)
    ).casefold()

    return " ".join(re.sub(r"[^a-z0-9 ]", " ", normalise).split())


def _strip_json_fences(text: str) -> str:

    texte = text.strip()

    if texte.startswith("```"):
        texte = re.sub(r"^```[a-zA-Z]*\n?", "", texte)
        texte = re.sub(r"```$", "", texte.strip())

    return texte.strip()


# ============================================================
# FICHE D'UNE EXPERIENCE
# ============================================================

def _build_experience_sheet(
    candidate_id: str,
    experience_id: str,
) -> tuple[str, str]:
    """
    Sérialise UNE expérience (contexte, réalisations) et retourne
    aussi son libellé lisible.

    L'entretien se déroule expérience par expérience : donner à l'IA
    tout le Master CV la ferait dériver vers d'autres postes, alors
    que l'enjeu est de creuser celui dont le candidat vient de parler.
    """

    db = SessionLocal()

    try:

        experience = db.get(ExperienceDB, experience_id)

        if experience is None or experience.candidate_id != candidate_id:
            return "", ""

        fin = (
            experience.end_date.strftime("%Y")
            if experience.end_date
            else "aujourd'hui"
        )

        libelle = f"{experience.job_title} — {experience.company}"

        lignes_fiche = [
            f"Poste : {experience.job_title}",
            f"Entreprise : {experience.company}",
            f"Période : {experience.start_date.strftime('%Y')}–{fin}",
        ]

        if experience.description:
            lignes_fiche.append(f"Description : {experience.description}")

        if experience.business_context:
            lignes_fiche.append(f"Contexte : {experience.business_context}")

        achievements = (
            db.query(AchievementDB)
            .filter(AchievementDB.experience_id == experience_id)
            .all()
        )

        for achievement in achievements:
            lignes_fiche.append(
                f"Réalisation déjà documentée : {achievement.title}"
                + (f" — {achievement.result}" if achievement.result else "")
            )

        skills = (
            db.query(SkillDB)
            .filter(SkillDB.candidate_id == candidate_id)
            .all()
        )

        if skills:
            lignes_fiche.append(
                "Compétences déjà déclarées (ne pas les redemander) : "
                + ", ".join(sorted({skill.name for skill in skills}))
            )

        return "\n".join(lignes_fiche), libelle

    finally:

        db.close()


# ============================================================
# RELANCE SUR UNE EXPERIENCE
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


FOLLOWUP_RULES = """Tu aides un candidat à documenter UNE expérience professionnelle pour son Master CV (le référentiel unique de son parcours, qui servira ensuite à générer des CV ciblés et des lettres de motivation honnêtes).

Le candidat vient de raconter cette expérience avec ses propres mots. Ta mission : poser entre {min_q} et {max_q} questions de relance pour faire émerger ce qu'il n'a PAS dit et qui a de la valeur sur un CV.

CREUSE EN PRIORITÉ :
- les outils, logiciels et technologies réellement utilisés ;
- les méthodes de travail et rituels (cadrage, priorisation, suivi, tests) ;
- les résultats concrets et, quand ils existent, les chiffres ;
- les formations, certifications ou montées en compétence liées à ce poste ;
- les interlocuteurs et parties prenantes, et la nature de la collaboration ;
- les décisions ou arbitrages dont il a été responsable.

RÈGLES :
- Ne repose JAMAIS une question dont la réponse figure déjà dans son récit ou dans la fiche ci-dessous.
- Reste sur CETTE expérience : ne demande rien sur d'autres postes.
- Des questions concrètes et vérifiables, jamais sur la personnalité ("êtes-vous rigoureux ?" est interdit).
- Si un poste recherché est indiqué, priorise ce qui compte pour ce type de poste.
- N'affirme rien sur le candidat : tu poses des questions, tu n'y réponds pas à sa place.
- Réponds UNIQUEMENT avec un tableau JSON de chaînes, sans texte autour, sans balisage markdown : ["Question 1", "Question 2"].
"""


def generate_followup_questions(
    candidate_id: str,
    experience_id: str,
    narration: str,
    target_role: str = "",
    uploaded_files: list | None = None,
    already_asked: list[str] | None = None,
) -> tuple[list[InterviewQuestion], str]:
    """
    Questions de relance sur une expérience, à partir du récit que le
    candidat vient d'en faire.

    Ne lève jamais d'exception : retourne une liste vide et un
    avertissement en cas d'échec.
    """

    if not is_configured():
        return [], (
            "Clé GEMINI_API_KEY non configurée : entretien IA "
            "indisponible."
        )

    if not narration.strip():
        return [], "Racontez d'abord cette expérience."

    fiche, libelle = _build_experience_sheet(candidate_id, experience_id)

    if not fiche:
        return [], "Expérience introuvable."

    image_parts, textes_documents = _build_image_parts(uploaded_files)

    prompt = FOLLOWUP_RULES.format(
        min_q=MIN_FOLLOWUP_QUESTIONS, max_q=MAX_FOLLOWUP_QUESTIONS
    )

    if target_role.strip():
        prompt += (
            f"\nPoste recherché par le candidat : {target_role.strip()}\n"
        )

    if already_asked:
        prompt += (
            "\nQUESTIONS DÉJÀ POSÉES — n'en repose AUCUNE, ni sous "
            "une formulation différente :\n"
            + "\n".join(f"- {question}" for question in already_asked)
            + "\n"
        )

    prompt += f"\nFICHE DE L'EXPÉRIENCE\n{fiche}"
    prompt += f"\n\nRÉCIT DU CANDIDAT\n{narration.strip()}"

    if textes_documents:
        prompt += f"\n\nDOCUMENTS FOURNIS EN COMPLÉMENT\n{textes_documents}"

    from google.genai import types

    parts = [types.Part.from_text(text=prompt)] + image_parts

    try:
        reponse = generate_multimodal(parts, temperature=0.5)

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return [], f"Génération des relances impossible ({error})."

    try:
        donnees = json.loads(_strip_json_fences(reponse))

    except json.JSONDecodeError:
        return [], "Réponse de l'IA illisible : réessayez."

    if not isinstance(donnees, list):
        return [], "Format de réponse inattendu : réessayez."

    # Le prompt seul ne suffit pas : l'IA repose volontiers la même
    # question sous une autre formulation.
    deja_vues = {
        _forme_comparable(question)
        for question in (already_asked or [])
    }

    questions: list[InterviewQuestion] = []

    for element in donnees[:MAX_FOLLOWUP_QUESTIONS]:

        if not isinstance(element, str):
            continue

        texte_question = element.strip()

        if not texte_question:
            continue

        forme = _forme_comparable(texte_question)

        if forme in deja_vues:
            continue

        deja_vues.add(forme)

        questions.append(
            InterviewQuestion(
                question=texte_question,
                experience_id=experience_id,
                experience_label=libelle,
            )
        )

    if not questions:
        return [], "Aucune relance exploitable n'a été générée."

    return questions, ""



# ============================================================
# TRANSCRIPTION AUDIO
# ============================================================

# Types MIME audio produits par st.audio_input (enregistrement
# navigateur) — la valeur exacte varie selon le navigateur, on garde
# une liste large plutôt que d'imposer un seul format.


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
        # Délai allongé : un enregistrement de plusieurs minutes met
        # bien plus de 30 s à être téléversé et traité.
        texte = generate_multimodal(
            parts,
            temperature=0.0,
            timeout_ms=GEMINI_AUDIO_TIMEOUT_MS,
        )

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
- En revanche, juge chaque réponse SUR SON CONTENU, même si elle ne répond pas à la question posée : le candidat peut raconter tout autre chose que ce qui lui était demandé, et ce qu'il raconte reste exploitable. La question n'est qu'un contexte, jamais un filtre.
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
        # Température basse : extraire des faits d'une réponse est une
        # tâche de lecture, pas de création. À 0.3, la même réponse
        # donnait tantôt une proposition, tantôt aucune — variabilité
        # inacceptable pour l'utilisateur, qui croit alors que rien
        # n'a été pris en compte.
        reponse = generate_multimodal([prompt], temperature=0.1)

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
