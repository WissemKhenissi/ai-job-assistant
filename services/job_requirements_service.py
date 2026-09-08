from __future__ import annotations

import json
import re
import unicodedata

from database.db import SessionLocal
from database.models import SkillCatalogDB


# ============================================================
# NORMALISATION
# ============================================================

def _normalize(value: str) -> str:
    """
    Normalise un texte pour faciliter la détection :

    - suppression des accents
    - minuscules
    - normalisation des tirets
    - conservation de + et #
      pour des technologies comme C++ / C#
    - suppression des caractères parasites
    - espaces multiples supprimés
    """

    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    normalized = normalized.casefold()

    normalized = re.sub(
        r"[-_/]",
        " ",
        normalized,
    )

    normalized = re.sub(
        r"[^a-z0-9+#. ]",
        " ",
        normalized,
    )

    return re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()


# ============================================================
# RECHERCHE DE TERMES
# ============================================================

def _contains_term(
    text: str,
    term: str,
) -> bool:
    """
    Vérifie qu'un terme apparaît réellement dans le texte.

    Important pour les termes courts :

        UI  -> détecte "UI"
        AI  -> détecte "AI"
        R   -> détecte "R"

    mais :

        UI  -> ne détecte pas "fruit"
        R   -> ne détecte pas "marketing"
    """

    normalized_text = _normalize(text)
    normalized_term = _normalize(term)

    if not normalized_term:
        return False

    # Termes courts : frontière stricte.
    if len(normalized_term) <= 2:

        pattern = (
            rf"(?<![a-z0-9])"
            rf"{re.escape(normalized_term)}"
            rf"(?![a-z0-9])"
        )

        return (
            re.search(
                pattern,
                normalized_text,
                flags=re.IGNORECASE,
            )
            is not None
        )

    # Termes normaux : frontière de mot.
    pattern = (
        rf"(?<![a-z0-9])"
        rf"{re.escape(normalized_term)}"
        rf"(?![a-z0-9])"
    )

    return (
        re.search(
            pattern,
            normalized_text,
            flags=re.IGNORECASE,
        )
        is not None
    )


# ============================================================
# CATALOGUE
# ============================================================

def _load_skill_catalog() -> list[SkillCatalogDB]:
    """
    Charge toutes les compétences actives du référentiel.
    """

    db = SessionLocal()

    try:

        skills = (
            db.query(SkillCatalogDB)
            .filter(
                SkillCatalogDB.is_active.is_(True)
            )
            .order_by(
                SkillCatalogDB.canonical_name
            )
            .all()
        )

        return skills

    finally:

        db.close()


def _parse_aliases(
    skill: SkillCatalogDB,
) -> list[str]:
    """
    Transforme le JSON des alias stocké en base
    en liste Python.

    Le système reste robuste si une ancienne ligne
    contient une simple chaîne.
    """

    if not skill.aliases:
        return []

    try:

        aliases = json.loads(
            skill.aliases
        )

        if isinstance(aliases, list):

            return [
                str(alias)
                for alias in aliases
                if alias
            ]

    except (
        json.JSONDecodeError,
        TypeError,
    ):
        pass

    return [
        skill.aliases
    ]


# ============================================================
# DETECTION DES COMPETENCES DANS UNE ANNONCE
# ============================================================
#
# L'ancienne approche lançait une recherche par expression régulière
# dans le texte **pour chaque alias du référentiel** : le coût
# dépendait de la taille du catalogue, pas de celle de l'annonce.
# Mesuré à 46 entrées : 23 ms. Extrapolé à un référentiel de 14 000
# compétences (l'ordre de grandeur d'une taxonomie publique) : près de
# sept secondes par annonce.
#
# On fait désormais l'inverse : découper l'annonce une fois, puis
# chercher chaque groupe de mots dans un index construit une seule
# fois par processus. Le coût suit la longueur de l'annonce et cesse
# de suivre celle du référentiel.
#
# La sémantique est identique : les deux méthodes reconnaissent un
# alias exactement aux frontières de mots, sur le même texte
# normalisé.

# Un mot, au sens de la détection. La normalisation conserve « . »,
# « + » et « # » pour des noms comme node.js, C++ ou C# ; mais un
# point de fin de phrase doit rester une frontière, sans quoi
# « SQL. » cesserait d'être reconnu. Le point sépare donc, et
# « node.js » se retrouve indexé comme les deux mots « node js » —
# des deux côtés de la comparaison, donc sans perte.
_MOT = re.compile(r"[a-z0-9+#]+")


def _mots(texte_normalise: str) -> list[str]:
    return _MOT.findall(texte_normalise)


_index_extraction_cache: tuple[dict, int] | None = None


def _index_extraction() -> tuple[dict, int]:
    """
    Index « forme normalisée -> (compétence, alias) », et longueur du
    plus long alias en nombre de mots.
    """

    global _index_extraction_cache

    if _index_extraction_cache is None:

        index: dict[str, tuple] = {}

        taille_max = 1

        for skill in _load_skill_catalog():

            for alias in (
                skill.canonical_name,
                *_parse_aliases(skill),
            ):

                mots = _mots(_normalize(alias))

                if not mots:
                    continue

                taille_max = max(taille_max, len(mots))

                index.setdefault(" ".join(mots), (skill, alias))

        _index_extraction_cache = (index, taille_max)

    return _index_extraction_cache


# Ponctuation qu'un groupe de mots ne doit jamais franchir.
#
# La normalisation efface la ponctuation : « gestion de projet,
# agile/scrum » devenait la suite de mots « gestion de projet agile
# scrum », et le groupe de quatre mots « gestion de projet agile »
# reconnaissait une compétence ESCO qui n'est nulle part dans
# l'annonce. Deux exigences pour une, dont une fantôme, comptée
# manquante.
#
# Le tiret, l'apostrophe et la barre oblique restent franchissables :
# « agile/scrum » et « e-commerce » sont des compétences uniques, et
# le référentiel les nomme avec un espace.
#
# Le point ne sépare que suivi d'une espace ou d'une fin de texte :
# sans cette précaution, « node.js » deviendrait deux termes que rien
# ne pourrait plus rapprocher de l'entrée « Node.js ».
_SEPARATEUR_DUR = re.compile(
    r"[,;:!?()\[\]{}«»\"\n\r\u2022\u00b7\u2026|]|\.(?=\s|$)"
)


# ============================================================
# SECTIONS QUI N'ENONCENT AUCUNE EXIGENCE
# ============================================================

# Une annonce ne demande rien dans ses paragraphes d'avantages, de
# rémunération ou de déroulé d'entretien. Le moteur les lisait pourtant
# comme le reste. Mesuré sur le jeu d'évaluation : « ski » venait d'un
# week-end au ski, « évènements sportifs » et « Formation des équipes »
# du paragraphe sur la vie d'entreprise, « éthique » d'un soft skill.
#
# Ces sections sont masquées avant la détection — remplacées par des
# espaces plutôt que retirées, pour que les positions restent celles du
# texte d'origine. Elles portent l'ordre d'apparition, dont dépendent la
# pondération par rang et la lecture du niveau d'exigence.
#
# Le masquage est local à la détection : extract_required_years et la
# lecture du type de contrat continuent de voir l'annonce entière,
# puisque c'est justement dans ces sections qu'ils trouvent leur
# réponse.

_TITRES_HORS_EXIGENCE = (
    "avantages",
    "notre petit +",
    "ce que nous offrons",
    "ce que nous proposons",
    "ce que nous t offrons",
    "pourquoi nous rejoindre",
    "pourquoi choisir",
    "pourquoi venir",
    "process de recrutement",
    "processus de recrutement",
    "deroulement du recrutement",
    "etapes du recrutement",
    "notre process",
    "informations supplementaires",
    "infos pratiques",
    "conditions du poste",
    "remuneration",
)

# Un intitulé qui rouvre les exigences referme la section masquée. Sans
# lui, une annonce plaçant ses avantages au milieu perdrait tout ce qui
# suit. Ce sont les titres qui, dans le corpus, introduisent réellement
# des exigences.
_TITRES_EXIGENCE = (
    "votre profil",
    "ton profil",
    "profil recherche",
    "profil souhaite",
    "profil du candidat",
    "qualifications",
    "hard skills",
    "soft skills",
    "competences",
    "vos missions",
    "tes missions",
    "vous maitrisez",
    "tu maitrises",
    "description du poste",
    "ce que vous apportez",
    "ce que tu apportes",
)

# Au-delà, la ligne est une phrase, pas un intitulé de section.
_MOTS_MAX_TITRE_SECTION = 8

_PUCES_SECTION = "-*>+"


def _est_un_intitule(ligne: str) -> bool:
    """
    Une ligne courte et sans puce se lit comme un titre de section.

    C'est la forme de la ligne qui la désigne, pas une liste de titres
    connus — même critère que pour la lecture du niveau d'exigence.
    """

    nue = ligne.strip()

    if not nue:
        return False

    if nue[:1] in _PUCES_SECTION or not nue[:1].isalnum():
        return False

    return len(nue.split()) <= _MOTS_MAX_TITRE_SECTION


def _correspond(ligne: str, titres: tuple[str, ...]) -> bool:

    forme = _normalize(ligne)

    return any(titre in forme for titre in titres)


def masquer_sections_hors_exigence(job_description: str) -> str:
    """
    Remplace par des espaces les sections qui n'énoncent pas
    d'exigence, en conservant la longueur du texte.

    Une section masquée court jusqu'au prochain intitulé qui rouvre les
    exigences, ou jusqu'à la fin — les avantages terminent presque
    toujours une annonce.

    Un intitulé inconnu ne masque rien : l'erreur va vers la lecture
    complète, jamais vers la coupe à l'aveugle.
    """

    if not job_description:
        return job_description

    masquees = []
    dans_section = False

    for ligne in job_description.split("\n"):

        if _est_un_intitule(ligne):

            if _correspond(ligne, _TITRES_HORS_EXIGENCE):
                dans_section = True

            elif dans_section and _correspond(ligne, _TITRES_EXIGENCE):
                dans_section = False

        masquees.append(" " * len(ligne) if dans_section else ligne)

    return "\n".join(masquees)


def _segments(job_description: str) -> list[tuple[str, int]]:
    """
    Les fragments d'annonce à l'intérieur desquels un groupe de mots
    peut être cherché, avec le décalage de chacun dans le texte
    normalisé complet.

    Le décalage sert à restituer l'ordre d'apparition, qui porte une
    information : ce que l'annonce cite en premier compte davantage.
    """

    fragments = []
    decalage = 0

    for brut in _SEPARATEUR_DUR.split(job_description):

        fragments.append((_normalize(brut), decalage))

        # Le fragment brut et sa forme normalisée n'ont pas la même
        # longueur, mais l'ordre relatif suffit : on avance d'autant
        # que le brut, séparateur compris.
        decalage += len(brut) + 1

    return fragments


def _detecter(job_description: str) -> list[tuple]:
    """
    Compétences reconnues dans l'annonce.

    Retourne (position, compétence, alias reconnu) par compétence, à
    sa première occurrence, dans l'ordre d'apparition.
    """

    index, taille_max = _index_extraction()

    if not _normalize(job_description):
        return []

    # Les avantages, la rémunération et le déroulé d'entretien ne
    # demandent rien : ils sont masqués avant toute détection.
    job_description = masquer_sections_hors_exigence(job_description)

    mots: list[str] = []
    positions: list[int] = []

    # Une frontière dure interrompt les groupes de mots : on remplit
    # les listes segment par segment en marquant les coupures.
    coupures: set[int] = set()

    for fragment, decalage in _segments(job_description):

        coupures.add(len(mots))

        for repere in _MOT.finditer(fragment):
            mots.append(repere.group())
            positions.append(decalage + repere.start())

    trouvees: dict[str, tuple] = {}

    for depart in range(len(mots)):

        # Le groupe s'arrête à la prochaine frontière dure.
        fin_du_segment = next(
            (
                coupure
                for coupure in sorted(coupures)
                if coupure > depart
            ),
            len(mots),
        )

        limite = min(taille_max, fin_du_segment - depart)

        for longueur in range(1, limite + 1):

            entree = index.get(
                " ".join(mots[depart : depart + longueur])
            )

            if entree is None:
                continue

            skill, alias = entree

            # Première occurrence seulement : le balayage va de la
            # gauche vers la droite.
            trouvees.setdefault(
                skill.id, (positions[depart], skill, alias)
            )

    return sorted(
        trouvees.values(),
        key=lambda item: (
            item[0],
            item[1].canonical_name.casefold(),
        ),
    )


def extract_required_skills(
    job_description: str,
) -> list[str]:
    """
    Extrait les compétences détectées dans une annonce.

    Le référentiel est entièrement piloté par la table
    `skill_catalog`. Aucune compétence n'est codée en dur ici.

    Retourne les noms canoniques des compétences, dans l'ordre
    d'apparition dans l'annonce.
    """

    if not job_description:
        return []

    return [
        skill.canonical_name
        for _position, skill, _alias in _detecter(job_description)
    ]


# ============================================================
# VERSION DETAILLEE
# ============================================================

def extract_required_skills_detailed(
    job_description: str,
) -> list[dict]:
    """
    Version détaillée de l'extraction.

    Utile pour le moteur de matching et pour l'interface.

    Exemple :

    {
        "canonical_name": "Python",
        "category": "Technology",
        "matched_alias": "Programmation Python",
        "position": 120
    }

    Cette fonction permet de conserver l'information expliquant
    pourquoi une compétence a été détectée.
    """

    if not job_description:
        return []

    return [
        {
            "canonical_name": skill.canonical_name,
            "category": skill.category,
            "subcategory": skill.subcategory,
            "matched_alias": alias,
            "position": position,
            "skill_id": skill.id,
        }
        for position, skill, alias in _detecter(job_description)
    ]


# ============================================================
# ANNEES D'EXPERIENCE DEMANDEES
# ============================================================

# "3 ans", "5 années", "3+ ans", "au moins 4 ans", "3 à 5 ans"...
_MOTIF_ANNEES = re.compile(
    r"(\d{1,2})\s*(?:\+|ans?\b|ann[ée]es?\b)",
    flags=re.IGNORECASE,
)

# Fourchettes : "3 a 5 ans", "entre 3 et 5 ans". Le texte est
# normalise avant, donc "a" y remplace deja "à".
_MOTIF_FOURCHETTE = re.compile(
    r"(\d{1,2})\s*(?:a|et)\s+(\d{1,2})\s*(?:ans?\b|ann[ée]es?\b)",
    flags=re.IGNORECASE,
)

# L'annonce doit parler d'expérience à proximité du chiffre : sans ça,
# "3 ans" dans "contrat de 3 ans" serait pris pour une exigence.
_MOTS_EXPERIENCE = ("experience", "experiences", "anciennete", "seniorite")

# Fenêtre de recherche autour du chiffre, en caractères.
_FENETRE = 60


def extract_required_years(job_description: str) -> int | None:
    """
    Nombre d'années d'expérience demandées par l'annonce, ou None.

    Purement déterministe (aucune IA) : cette information sert à
    comparer avec l'ancienneté réelle du candidat, il vaut donc mieux
    ne rien annoncer que d'annoncer un chiffre inventé.

    En cas de fourchette ("3 à 5 ans"), le minimum est retenu : c'est
    le seuil d'entrée, donc le seul qui permette de dire si le profil
    passe le filtre.
    """

    if not job_description:
        return None

    normalise = _normalize(job_description)

    candidats: list[int] = []

    # Les deux motifs alimentent la meme liste : sur "de 5 a 8 ans",
    # la fourchette apporte 5 et le motif simple 8 — le min() final
    # retient bien le seuil d'entree.
    for correspondance in list(_MOTIF_FOURCHETTE.finditer(normalise)) + list(
        _MOTIF_ANNEES.finditer(normalise)
    ):

        debut = max(0, correspondance.start() - _FENETRE)
        fin = min(len(normalise), correspondance.end() + _FENETRE)

        contexte = normalise[debut:fin]

        if not any(mot in contexte for mot in _MOTS_EXPERIENCE):
            continue

        try:
            annees = int(correspondance.group(1))
        except (TypeError, ValueError):
            continue

        # Au-delà, il ne s'agit plus d'une exigence d'ancienneté
        # (année civile, effectif, montant...).
        if 1 <= annees <= 30:
            candidats.append(annees)

    if not candidats:
        return None

    return min(candidats)
