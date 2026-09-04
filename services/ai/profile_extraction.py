"""
Lecture d'un CV pour amorcer un Master CV.

Sans cette étape, un nouvel utilisateur arrive devant un profil vide
et doit tout ressaisir — expérience par expérience, preuve par preuve.
Personne ne le fait, et tout le reste de l'outil reste inutilisable.

Le principe du projet s'applique intégralement ici : l'IA **transcrit**,
elle n'interprète pas. Chaque élément extrait doit se retrouver dans le
texte du CV, et le code le vérifie au lieu de faire confiance :

- une puce d'expérience doit être présente **mot pour mot** dans le CV
  (aux espaces près) — c'est la même exigence que pour l'entretien ;
- une compétence doit apparaître dans le texte, sinon elle serait
  déduite, et une déduction n'est pas une déclaration du candidat ;
- aucun nombre absent du CV ne peut apparaître dans un texte libre ;
- les dates doivent être cohérentes entre elles et non futures.

Ce qui échoue à ces contrôles est écarté, avec la raison. Rien n'est
écrit en base : cette fonction retourne une proposition que
l'utilisateur relit, corrige et valide.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from services.ai.gemini_client import (
    GeminiNotConfiguredError,
    GeminiRequestError,
    generate_text,
    is_configured,
)
from services.text_numbers import numbers_in


# Un CV tient largement dedans ; au-delà, c'est un dossier complet et
# le coût du prompt s'envole sans rien apporter.
MAX_CV_LENGTH = 20_000

# Un CV réaliste ne dépasse pas ces bornes ; au-delà, c'est le signe
# d'une extraction qui part en roue libre.
MAX_EXPERIENCES = 20
MAX_LINES_PER_EXPERIENCE = 15
MAX_SKILLS = 60


@dataclass(frozen=True)
class ExtractedLine:
    """Une puce du CV, et la compétence qu'elle démontre."""

    text: str
    skill: str = ""


@dataclass(frozen=True)
class ExtractedExperience:
    company: str
    job_title: str
    location: str = ""
    start_date: date | None = None
    end_date: date | None = None
    business_context: str = ""
    lines: tuple[ExtractedLine, ...] = ()

    @property
    def label(self) -> str:
        return f"{self.job_title} — {self.company}"


@dataclass(frozen=True)
class ExtractedEducation:
    institution: str
    degree: str
    field_of_study: str = ""
    start_year: int | None = None
    end_year: int | None = None


@dataclass(frozen=True)
class ExtractedCertification:
    name: str
    organization: str = ""
    obtained_year: int | None = None


@dataclass(frozen=True)
class ExtractedProfile:
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin_url: str = ""
    headline: str = ""
    summary: str = ""
    languages: str = ""
    experiences: tuple[ExtractedExperience, ...] = ()
    skills: tuple[str, ...] = ()
    educations: tuple[ExtractedEducation, ...] = ()
    certifications: tuple[ExtractedCertification, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return not (
            self.experiences
            or self.skills
            or self.educations
            or self.certifications
            or self.first_name
        )


# ============================================================
# COMPARAISON AU TEXTE SOURCE
# ============================================================

def _aplatir(texte: str) -> str:
    """Minuscules, sans accents, espaces normalisés."""

    normalise = unicodedata.normalize("NFKD", texte or "")

    normalise = "".join(
        caractere
        for caractere in normalise
        if not unicodedata.combining(caractere)
    )

    return " ".join(normalise.casefold().split())


def _present(fragment: str, source_aplatie: str) -> bool:
    """Ce fragment figure-t-il tel quel dans le CV ?"""

    aplati = _aplatir(fragment)

    return bool(aplati) and aplati in source_aplatie


def _chiffres_inventes(texte: str, source: str) -> set[str]:
    return numbers_in(texte) - numbers_in(source)


# ============================================================
# LECTURE DES VALEURS
# ============================================================

def _texte(valeur) -> str:
    return valeur.strip() if isinstance(valeur, str) else ""


def _entier(valeur) -> int | None:

    if isinstance(valeur, int):
        return valeur

    if isinstance(valeur, str) and valeur.strip().isdigit():
        return int(valeur.strip())

    return None


def _date(valeur) -> date | None:
    """Lit une date ISO, complète au premier jour du mois si besoin."""

    texte = _texte(valeur)

    if not texte:
        return None

    correspondance = re.match(
        r"^(\d{4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$", texte
    )

    if correspondance is None:
        return None

    annee, mois, jour = correspondance.groups()

    try:
        return date(
            int(annee),
            int(mois) if mois else 1,
            int(jour) if jour else 1,
        )

    except ValueError:
        return None


# ============================================================
# PROMPT
# ============================================================

PROMPT_RULES = """Tu transcris un CV en données structurées. Tu ne l'interprètes pas.

RÈGLE ABSOLUE
N'invente rien. N'ajoute aucune compétence, réalisation, date, entreprise, diplôme ou chiffre qui ne figure pas dans le texte du CV. Si une information est absente, laisse le champ vide plutôt que de le combler.

PUCES D'EXPÉRIENCE
Recopie chaque puce **mot pour mot** telle qu'elle figure dans le CV. Ne la reformule pas, ne la raccourcis pas, ne la complète pas. Une puce reformulée sera rejetée automatiquement.

COMPÉTENCES
Ne liste que des compétences dont le nom apparaît réellement dans le texte du CV — dans une rubrique compétences, dans un intitulé de poste ou dans une puce. N'en déduis aucune du contexte.

Pour chaque puce, indique dans "skill" la compétence qu'elle démontre, choisie parmi celles que tu as listées. Laisse vide si aucune ne correspond.

DATES
Format ISO : "2019-03" pour mars 2019, "2019" si seule l'année est connue. Laisse "end_date" vide pour un poste en cours.

FORMAT DE RÉPONSE
Réponds uniquement avec un objet JSON, sans texte autour, sans balisage markdown :

{
  "first_name": "", "last_name": "", "email": "", "phone": "",
  "location": "", "linkedin_url": "", "headline": "", "summary": "",
  "languages": "",
  "skills": [],
  "experiences": [
    {"company": "", "job_title": "", "location": "",
     "start_date": "", "end_date": "", "business_context": "",
     "lines": [{"text": "", "skill": ""}]}
  ],
  "educations": [
    {"institution": "", "degree": "", "field_of_study": "",
     "start_year": null, "end_year": null}
  ],
  "certifications": [
    {"name": "", "organization": "", "obtained_year": null}
  ]
}"""


def _lire_objet_json(reponse: str) -> dict | None:

    texte = reponse.strip()

    if texte.startswith("```"):
        texte = re.sub(r"^```[a-zA-Z]*\n?", "", texte)
        texte = re.sub(r"```$", "", texte.strip()).strip()

    try:
        donnees = json.loads(texte)

    except json.JSONDecodeError:

        debut, fin = texte.find("{"), texte.rfind("}")

        if debut < 0 or fin <= debut:
            return None

        try:
            donnees = json.loads(texte[debut : fin + 1])

        except json.JSONDecodeError:
            return None

    return donnees if isinstance(donnees, dict) else None


# ============================================================
# EXTRACTION
# ============================================================

def extract_profile_from_cv(
    cv_text: str,
    today: date | None = None,
) -> ExtractedProfile:
    """
    Propose un Master CV à partir du texte d'un CV.

    N'écrit rien : le résultat est une proposition à relire. Ne lève
    jamais d'exception — un échec retourne un profil vide portant un
    avertissement.
    """

    if not (cv_text or "").strip():
        return ExtractedProfile(
            warnings=("Aucun texte à analyser.",)
        )

    if not is_configured():
        return ExtractedProfile(
            warnings=(
                "Clé GEMINI_API_KEY non configurée : lecture "
                "automatique indisponible.",
            )
        )

    source = cv_text[:MAX_CV_LENGTH]

    try:
        reponse = generate_text(
            f"{PROMPT_RULES}\n\nTEXTE DU CV\n{source}",
            temperature=0.1,
        )

    except (GeminiNotConfiguredError, GeminiRequestError) as error:
        return ExtractedProfile(
            warnings=(f"Lecture indisponible ({error}).",)
        )

    donnees = _lire_objet_json(reponse)

    if donnees is None:
        return ExtractedProfile(
            warnings=("Réponse de l'IA illisible : réessayez.",)
        )

    return _valider(donnees, source, today or date.today())


def _valider(
    donnees: dict,
    source: str,
    aujourd_hui: date,
) -> ExtractedProfile:
    """Confronte chaque élément extrait au texte du CV."""

    aplatie = _aplatir(source)

    avertissements: list[str] = []

    # ----------------------------------------------------------
    # IDENTITE
    # ----------------------------------------------------------
    #
    # Une adresse ou un téléphone inventés seraient la pire erreur
    # possible : le recruteur ne pourrait pas rappeler.

    def _si_present(cle: str) -> str:

        valeur = _texte(donnees.get(cle))

        if valeur and not _present(valeur, aplatie):
            avertissements.append(
                f"« {valeur} » ne figure pas dans le CV : champ "
                f"{cle} laissé vide."
            )
            return ""

        return valeur

    email = _si_present("email")
    telephone = _si_present("phone")
    lien = _si_present("linkedin_url")

    # ----------------------------------------------------------
    # TEXTES LIBRES
    # ----------------------------------------------------------

    def _sans_chiffre_invente(cle: str) -> str:

        valeur = _texte(donnees.get(cle))

        inventes = _chiffres_inventes(valeur, source)

        if inventes:
            avertissements.append(
                f"Chiffre absent du CV ({', '.join(sorted(inventes))}) "
                f"dans {cle} : champ laissé vide."
            )
            return ""

        return valeur

    resume = _sans_chiffre_invente("summary")

    # ----------------------------------------------------------
    # COMPETENCES
    # ----------------------------------------------------------

    competences: list[str] = []
    vues: set[str] = set()
    deduites: list[str] = []

    brutes = donnees.get("skills")

    for element in brutes if isinstance(brutes, list) else []:

        nom = _texte(element)

        if not nom or _aplatir(nom) in vues:
            continue

        if not _present(nom, aplatie):
            deduites.append(nom)
            continue

        vues.add(_aplatir(nom))
        competences.append(nom)

        if len(competences) >= MAX_SKILLS:
            break

    if deduites:
        avertissements.append(
            "Compétences écartées, absentes du texte du CV : "
            + ", ".join(deduites[:8])
            + ("…" if len(deduites) > 8 else "")
        )

    # ----------------------------------------------------------
    # EXPERIENCES
    # ----------------------------------------------------------

    experiences, alertes = _valider_experiences(
        donnees.get("experiences"),
        source,
        aplatie,
        aujourd_hui,
        set(vues),
    )

    avertissements.extend(alertes)

    return ExtractedProfile(
        first_name=_texte(donnees.get("first_name")),
        last_name=_texte(donnees.get("last_name")),
        email=email,
        phone=telephone,
        location=_texte(donnees.get("location")),
        linkedin_url=lien,
        headline=_texte(donnees.get("headline")),
        summary=resume,
        languages=_texte(donnees.get("languages")),
        experiences=tuple(experiences),
        skills=tuple(competences),
        educations=tuple(_valider_formations(donnees.get("educations"))),
        certifications=tuple(
            _valider_certifications(donnees.get("certifications"))
        ),
        warnings=tuple(avertissements),
    )


def _valider_experiences(
    brutes,
    source: str,
    aplatie: str,
    aujourd_hui: date,
    competences_connues: set[str],
) -> tuple[list[ExtractedExperience], list[str]]:

    experiences: list[ExtractedExperience] = []
    avertissements: list[str] = []

    reformulees = 0

    for element in (brutes if isinstance(brutes, list) else [])[
        :MAX_EXPERIENCES
    ]:

        if not isinstance(element, dict):
            continue

        entreprise = _texte(element.get("company"))
        poste = _texte(element.get("job_title"))

        if not entreprise and not poste:
            continue

        debut = _date(element.get("start_date"))
        fin = _date(element.get("end_date"))

        if debut and debut > aujourd_hui:
            avertissements.append(
                f"« {poste} — {entreprise} » : date de début dans le "
                "futur, à corriger."
            )
            debut = None

        if debut and fin and fin < debut:
            avertissements.append(
                f"« {poste} — {entreprise} » : la fin précède le "
                "début, date de fin ignorée."
            )
            fin = None

        # --------------------------------------------------
        # PUCES : PRESENCE MOT POUR MOT
        # --------------------------------------------------

        lignes: list[ExtractedLine] = []

        brutes_lignes = element.get("lines")

        for ligne in (
            brutes_lignes if isinstance(brutes_lignes, list) else []
        )[:MAX_LINES_PER_EXPERIENCE]:

            texte = (
                _texte(ligne.get("text"))
                if isinstance(ligne, dict)
                else _texte(ligne)
            )

            if not texte:
                continue

            if not _present(texte, aplatie):
                reformulees += 1
                continue

            if _chiffres_inventes(texte, source):
                reformulees += 1
                continue

            competence = (
                _texte(ligne.get("skill"))
                if isinstance(ligne, dict)
                else ""
            )

            if competence and _aplatir(competence) not in (
                competences_connues
            ):
                competence = ""

            lignes.append(
                ExtractedLine(text=texte, skill=competence)
            )

        contexte = _texte(element.get("business_context"))

        if contexte and _chiffres_inventes(contexte, source):
            contexte = ""

        experiences.append(
            ExtractedExperience(
                company=entreprise,
                job_title=poste,
                location=_texte(element.get("location")),
                start_date=debut,
                end_date=fin,
                business_context=contexte,
                lines=tuple(lignes),
            )
        )

    if reformulees:
        avertissements.append(
            f"{reformulees} ligne(s) écartée(s) : reformulées par "
            "l'IA au lieu d'être recopiées du CV."
        )

    return experiences, avertissements


def _valider_formations(brutes) -> list[ExtractedEducation]:

    formations: list[ExtractedEducation] = []

    for element in brutes if isinstance(brutes, list) else []:

        if not isinstance(element, dict):
            continue

        etablissement = _texte(element.get("institution"))
        diplome = _texte(element.get("degree"))

        if not etablissement and not diplome:
            continue

        formations.append(
            ExtractedEducation(
                institution=etablissement,
                degree=diplome,
                field_of_study=_texte(element.get("field_of_study")),
                start_year=_entier(element.get("start_year")),
                end_year=_entier(element.get("end_year")),
            )
        )

    return formations


def _valider_certifications(brutes) -> list[ExtractedCertification]:

    certifications: list[ExtractedCertification] = []

    for element in brutes if isinstance(brutes, list) else []:

        if not isinstance(element, dict):
            continue

        nom = _texte(element.get("name"))

        if not nom:
            continue

        certifications.append(
            ExtractedCertification(
                name=nom,
                organization=_texte(element.get("organization")),
                obtained_year=_entier(element.get("obtained_year")),
            )
        )

    return certifications
