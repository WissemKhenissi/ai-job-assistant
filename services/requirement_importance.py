"""
Ce que l'annonce dit d'une exigence : condition, souhait, ou décor.

Le moteur traitait toutes les exigences à égalité. Une annonce qui
écrit « la maîtrise de la gestion de projet est indispensable » puis
« environnement : Jira, Miro, GitLab, BaseCamp, Planner, TFS, Clarity,
MS Project » produisait neuf exigences dont huit outils — et le score
s'effondrait sur une énumération que l'annonce elle-même ne présente
pas comme une condition d'entrée.

La pondération par rang d'apparition atténuait le symptôme sans
toucher la cause : elle suppose que l'ordre porte l'importance, ce qui
vaut pour les sections d'une annonce mais pas à l'intérieur d'une
liste. Ici on lit ce que l'annonce **dit** du terme.

Trois niveaux :

- ``ESSENTIELLE`` — l'annonce en fait une condition ;
- ``SOUHAITEE``   — l'annonce l'apprécierait sans l'exiger ;
- ``MENTION``     — l'annonce la cite, en exemple ou en décor.

Le classement est entièrement déterministe : il repose sur des
marqueurs de langage explicites, cherchés dans une fenêtre étroite
autour de la première occurrence du terme. Le même texte donne
toujours le même niveau.

L'IA en a été écartée, en deux temps et sur mesure.

D'abord elle décidait, et le texte ne comblait que ses silences. Sur
treize annonces réelles, les deux divergeaient sur 29 exigences,
**toujours dans le même sens** : l'IA promeut en condition d'entrée
ce que l'annonce se contente de citer (14 fois) ou de souhaiter
(13 fois), jamais l'inverse. La priorité a donc été inversée.

Cela n'a pas suffi. Une annonce ne qualifie pas ce qu'elle demande :
137 exigences sur 202 tombaient dans le silence, et l'IA y décidait
encore. Deux captures d'une même offre, dont les seules différences
sont des bandeaux de navigation, obtenaient 34,6 et 44,5 — sur deux
termes, dont l'un n'apparaît que dans le titre de la page.

Un score qui bouge de dix points sur le même texte n'aide à décider
de rien. Le classement par l'IA n'a jamais démontré qu'il apportait
de la justesse — seulement de la sévérité et de la variance. En cas
de silence, le niveau médian : il n'exagère ni ne minimise l'écart,
et il ne change pas d'avis.

En cas de doute, ``SOUHAITEE`` : ni écarter une vraie condition, ni
transformer un décor en exigence.
"""

from __future__ import annotations

import re

from services.text_normalization import (
    forme_comparable,
    minuscules_sans_accents,
)


# ============================================================
# NIVEAUX
# ============================================================

ESSENTIELLE = "essentielle"
SOUHAITEE = "souhaitee"
MENTION = "mention"

# Ce que l'on retient quand rien dans l'annonce ne tranche.
IMPORTANCE_PAR_DEFAUT = SOUHAITEE

LIBELLES = {
    ESSENTIELLE: "exigée",
    SOUHAITEE: "souhaitée",
    MENTION: "citée",
}


# ============================================================
# MARQUEURS
# ============================================================
#
# Écrits sans accents : le texte est désaccentué avant la recherche.

MARQUEURS_ESSENTIELLE = (
    "indispensable",
    "imperatif",
    "imperativement",
    "obligatoire",
    "exige",
    "requis",
    "prerequis",
    "pre requis",
    "must have",
    "must-have",
    "incontournable",
    "maitrise",
    "maitrisez",
    "solide experience",
    "forte experience",
    "experience confirmee",
    "experience significative",
    "vous justifiez",
    "profil recherche",
    "competences requises",
    "competences attendues",
    "ce que nous attendons",
    "necessairement",
)

MARQUEURS_SOUHAITEE = (
    "un plus",
    "un atout",
    "un vrai plus",
    "apprecie",
    "idealement",
    "de preference",
    "nice to have",
    "nice-to-have",
    "bonus",
    "souhaite",
    "optionnel",
    "facultatif",
    "la connaissance de",
    "des notions de",
    "si possible",
    "eventuellement",
    "serait un",
)

# Ce qui annonce une liste d'exemples ou d'alternatives plutot
# qu'une liste de conditions. Observe sur des annonces reelles :
#
#   « vous maitrisez un ou plusieurs outils de gestion de projet :
#     Jira, Confluence, Trello, Miro, GitLab, BaseCamp, Planner... »
#   « maitrise des principaux outils digitaux (Google Ads, Google
#     Analytics, Meta Ads, WordPress, Pack Adobe) »
#
# Le verbe dit « maitrise », mais l'annonce n'exige aucun de ces dix
# outils en particulier : elle en demande un. Compter dix conditions
# la ou l'annonce en pose une fausse le score dans le mauvais sens —
# et c'est exactement ce que faisait la moyenne simple.
MARQUEURS_ILLUSTRATION = (
    "un ou plusieurs",
    "une ou plusieurs",
    "au moins un",
    "au moins une",
    "l un de",
    "l un ou l autre",
    "outil",
    "outils",
    "logiciel",
    "logiciels",
    "solution",
    "solutions",
    "technologie",
    "technologies",
    "plateforme",
    "plateformes",
    "suite",
    "environnement",
    "stack",
    "ecosysteme",
    "tel que",
    "tels que",
    "telles que",
    "comme",
    "par exemple",
    "notamment",
    "entre autres",
    "de type",
    "type de",
)


MARQUEURS_MENTION = (
    "environnement",
    "notre stack",
    "stack technique",
    "outils utilises",
    "logiciels utilises",
    "nous utilisons",
    "vous utiliserez",
    "parmi lesquels",
    "tels que",
    "telles que",
    "par exemple",
    "notamment",
    "entre autres",
    "ecosysteme",
)


# ============================================================
# NORMALISATION
# ============================================================

# La clé sous laquelle une exigence est retrouvée d'un module à
# l'autre. Réexportée sous ce nom : le moteur de matching et le tri
# des exigences l'emploient tous les deux, et ils doivent employer
# exactement la même — voir services.text_normalization.
normalise_terme = forme_comparable


# Fins de phrase et séparateurs de puce : la fenêtre de lecture s'y
# arrête, sans quoi un marqueur situé trois phrases plus loin
# déciderait du niveau.
_DELIMITEURS = re.compile(r"[\n\r.;!?•]")


def _fenetre_phrase(texte: str, position: int) -> tuple[str, int]:
    """
    Le fragment de phrase qui contient la position donnée, et son
    décalage — la position du terme à l'intérieur du fragment sert
    ensuite à savoir s'il est avant ou après l'ouverture d'une liste.
    """

    debut = 0

    for delimiteur in _DELIMITEURS.finditer(texte, 0, position):
        debut = delimiteur.end()

    suite = _DELIMITEURS.search(texte, position)

    fin = suite.start() if suite else len(texte)

    return texte[debut:fin], debut


def _fenetre_ligne(texte: str, position: int) -> str:
    """La ligne entière qui contient la position donnée."""

    debut = texte.rfind("\n", 0, position) + 1

    fin = texte.find("\n", position)

    return texte[debut : fin if fin != -1 else len(texte)]


def _entete(texte: str, position: int, lignes: int = 2) -> str:
    """
    Les lignes non vides qui précèdent — souvent un titre de section
    (« Environnement technique : », « Compétences requises : ») qui
    qualifie tout ce qui suit.
    """

    debut_ligne = texte.rfind("\n", 0, position) + 1

    precedentes = [
        ligne.strip()
        for ligne in texte[:debut_ligne].split("\n")
        if ligne.strip()
    ]

    return " ".join(precedentes[-lignes:])


# ============================================================
# LECTURE DES MARQUEURS
# ============================================================

def _niveau_dans(fenetre: str) -> str:
    """
    Le niveau annoncé par cette fenêtre, ou "" si elle ne dit rien.

    L'ordre n'est pas neutre : « la maîtrise de X serait un plus »
    contient les deux marqueurs, et c'est « un plus » qui décrit
    l'exigence réelle. Un souhait explicite l'emporte donc toujours
    sur une formule d'exigence.
    """

    if any(marqueur in fenetre for marqueur in MARQUEURS_SOUHAITEE):
        return SOUHAITEE

    if any(marqueur in fenetre for marqueur in MARQUEURS_ESSENTIELLE):
        return ESSENTIELLE

    if any(marqueur in fenetre for marqueur in MARQUEURS_MENTION):
        return MENTION

    return ""


# Une énumération se reconnaît à sa forme : beaucoup d'éléments, tous
# courts. « Jira, Miro, GitLab, BaseCamp, Planner, TFS » liste un
# outillage possible ; une phrase de quinze mots séparée par des
# virgules n'est pas une liste d'outils.
_MINIMUM_ELEMENTS = 4
_MOTS_MAX_PAR_ELEMENT = 4


def _est_une_enumeration(fenetre: str) -> bool:

    elements = [
        element.strip()
        for element in re.split(r"[,/|]", fenetre)
        if element.strip()
    ]

    if len(elements) < _MINIMUM_ELEMENTS:
        return False

    return all(
        len(element.split()) <= _MOTS_MAX_PAR_ELEMENT
        for element in elements
    )


def _enumeration_illustrative(phrase: str, position: int) -> bool:
    """
    Le terme figure-t-il dans une liste d'exemples ou d'alternatives ?

    On regarde ce qui **introduit** la liste — le fragment qui précède
    le « : » ou la parenthèse ouvrante. « Compétences requises : » ne
    ressemble pas à « un ou plusieurs outils de gestion de projet : »,
    et pourtant les deux sont suivis d'une énumération.

    Cette lecture passe avant les marqueurs d'exigence, sinon le
    « vous maîtrisez » qui ouvre la phrase ferait de chacun des dix
    outils cités une condition d'entrée.
    """

    ouverture = max(
        phrase.rfind(":", 0, position),
        phrase.rfind("(", 0, position),
    )

    if ouverture == -1:
        return False

    if not _est_une_enumeration(phrase[ouverture + 1 :]):
        return False

    introduction = phrase[:ouverture]

    return any(
        marqueur in introduction
        for marqueur in MARQUEURS_ILLUSTRATION
    )


# ============================================================
# CLASSEMENT
# ============================================================

def _lire_niveau(terme: str, job_text: str) -> str | None:
    """
    Ce que l'annonce dit de ce terme, ou ``None`` si elle n'en dit
    rien.

    Le vide est une réponse à part entière, et il ne se confond pas
    avec « souhaitée ». Une annonce qui écrit « serait un plus » se
    prononce ; une annonce qui mentionne un terme sans le qualifier
    ne se prononce pas. Les deux aboutissent au même niveau, mais pas
    au même degré de certitude — et c'est ce degré qui décide si la
    proposition de l'IA a droit de cité.
    """

    cle = normalise_terme(terme)

    if not cle or not (job_text or "").strip():
        return None

    texte = minuscules_sans_accents(job_text)

    # Le terme normalisé perd sa ponctuation, le texte non : on
    # cherche donc le terme mot à mot, en tolérant n'importe quel
    # séparateur entre ses mots.
    motif = re.compile(
        r"(?<![a-z0-9])"
        + r"[^a-z0-9]+".join(
            re.escape(mot) for mot in cle.split(" ")
        )
        + r"(?![a-z0-9])"
    )

    occurrence = motif.search(texte)

    if occurrence is None:
        return None

    position = occurrence.start()

    phrase, debut_phrase = _fenetre_phrase(texte, position)

    # Une liste d'exemples ou d'alternatives l'emporte sur la formule
    # qui l'introduit : « vous maîtrisez un ou plusieurs outils de
    # gestion de projet : Jira, Miro, GitLab... » demande un outil,
    # pas les dix.
    if _enumeration_illustrative(phrase, position - debut_phrase):
        return MENTION

    for fenetre in (
        phrase,
        _fenetre_ligne(texte, position),
        _entete(texte, position),
    ):

        niveau = _niveau_dans(fenetre)

        if niveau:
            return niveau

    # Dernier recours : une énumération que rien n'introduit se
    # reconnaît encore à sa forme.
    if _est_une_enumeration(phrase):
        return MENTION

    return None


def classify_requirement(terme: str, job_text: str) -> str:
    """
    Ce que l'annonce dit de ce terme : essentielle, souhaitée, ou
    simple mention.

    Retourne toujours l'un des trois niveaux — jamais de vide : une
    exigence sans niveau ne pourrait pas être pondérée. Quand
    l'annonce ne se prononce pas, c'est le niveau médian, qui
    n'exagère ni ne minimise l'écart.
    """

    return _lire_niveau(terme, job_text) or IMPORTANCE_PAR_DEFAUT


def classify_requirements(
    termes: list[str] | tuple[str, ...],
    job_text: str,
) -> dict[str, str]:
    """
    Niveau de chaque exigence, indexé par forme normalisée.

    Deux fois le même texte donnent deux fois le même résultat :
    c'est la propriété qu'on attend d'un score dont on se sert pour
    comparer des annonces entre elles.
    """

    niveaux: dict[str, str] = {}

    for terme in termes:

        cle = normalise_terme(terme)

        if not cle or cle in niveaux:
            continue

        niveaux[cle] = (
            _lire_niveau(terme, job_text) or IMPORTANCE_PAR_DEFAUT
        )

    return niveaux
