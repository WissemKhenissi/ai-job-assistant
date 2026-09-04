"""
Nettoyage des exigences extraites d'une annonce.

Le catalogue ne détecte que des compétences qu'il connaît : sa sortie
est propre par construction. L'extraction par l'IA, elle, est libre —
et sur une annonce marketing elle rapporte « Data », « mobile »,
« acquisition », « influence » : des mots de l'annonce découpés en
morceaux, pas des compétences.

Ces fragments coûtent cher, trois fois :

1. ils comptent comme des compétences **manquantes**, ce qui abaisse
   le score d'adéquation sans raison ;
2. ils entrent dans la liste des termes **interdits** transmise à la
   rédaction, qui se voit alors refuser des mots français ordinaires ;
3. cas observé : « Data » interdit alors que « Data / KPI » est une
   compétence prouvée du candidat.

Le tri est déterministe et se résume à une règle : un mot isolé que le
référentiel ne connaît pas et qui figure parmi les termes génériques
d'annonce n'est pas une compétence. Tout le reste passe — un terme
composé, un acronyme, un outil, ou n'importe quoi que le référentiel
reconnaît.

En cas de doute, on garde : écarter à tort une vraie exigence
fausserait l'analyse dans l'autre sens.
"""

from __future__ import annotations

from services.skill_catalog_service import find_skill_by_name

# La même forme que celle sous laquelle le niveau d'exigence est
# indexé (services.requirement_importance). Deux définitions
# séparées auraient suffi à ce qu'une exigence retenue ici cesse
# silencieusement de retrouver son niveau.
from services.text_normalization import forme_comparable as _normalize


# Mots qui décrivent un domaine, un objectif ou un support — jamais
# une compétence à eux seuls. Ils ne sont écartés que **isolés** :
# « marketing automation », « acquisition client » ou « Data / KPI »
# restent des exigences valables.
GENERIC_TERMS = frozenset(
    {
        # Domaines et supports
        "data",
        "digital",
        "digitale",
        "mobile",
        "web",
        "online",
        "internet",
        "media",
        "medias",
        "site",
        "plateforme",
        "produit",
        "produits",
        "projet",
        "projets",
        "service",
        "services",
        "outil",
        "outils",
        "logiciel",
        "logiciels",
        # Objectifs et résultats
        "acquisition",
        "fidelisation",
        "conversion",
        "influence",
        "notoriete",
        "visibilite",
        "croissance",
        "performance",
        "qualite",
        "innovation",
        "satisfaction",
        "rentabilite",
        "productivite",
        # Fonctions génériques
        "marketing",
        "commercial",
        "commerciale",
        "communication",
        "management",
        "gestion",
        "pilotage",
        "coordination",
        "organisation",
        "strategie",
        "analyse",
        "suivi",
        "conception",
        "developpement",
        "production",
        "technique",
        "techniques",
        "business",
        # Interlocuteurs
        "client",
        "clients",
        # Observés en faux positifs après l'import d'ESCO, qui
        # possède une entrée portant chacun de ces noms.
        "paris",
        "anglais",
        "francais",
        "mecanique",
        "administration",
        "informatique",
        "utilisateur",
        "utilisateurs",
        "equipe",
        "equipes",
        "partenaire",
        "partenaires",
        "prestataire",
        "prestataires",
    }
)


def is_plausible_requirement(skill: str) -> bool:
    """
    Ce terme peut-il désigner une compétence ?

    Le référentiel tranche en premier — mais seulement pour ses
    entrées **curées**. Une taxonomie importée en masse contient des
    concepts qui portent le nom d'un mot courant : ESCO connaît
    « communication », « acquisition » et « paris ». Leur accorder un
    blanc-seing revenait à compter une exigence dès qu'une annonce
    prononçait ces mots — et à faire chuter le score d'autant.

    Une entrée importée doit donc passer la même épreuve que
    l'inconnu : un mot isolé et générique reste écarté.
    """

    normalise = _normalize(skill)

    if not normalise:
        return False

    if len(normalise) < 2:
        return False

    connue = find_skill_by_name(skill)

    if connue is not None and not _vient_d_un_import(connue):
        return True

    if " " in normalise:
        return True

    return normalise not in GENERIC_TERMS


def _vient_d_un_import(competence) -> bool:
    """
    Cette entrée du référentiel a-t-elle été importée en masse ?

    Les entrées écrites à la main ont été choisies pour ce candidat :
    elles méritent la confiance. Celles d'une taxonomie générale
    n'ont été choisies par personne.
    """

    return str(getattr(competence, "id", "")).startswith("esco-")


def clean_required_skills(
    skills: list[str] | tuple[str, ...],
) -> tuple[list[str], list[str]]:
    """
    Trie les exigences extraites d'une annonce.

    Retourne (retenues, écartées).

    Les doublons sont supprimés par forme canonique du référentiel :
    « Product backlog » et « Gestion du backlog » désignent la même
    exigence, elle ne doit compter qu'une fois. C'est le **premier
    libellé rencontré** qui est conservé, jamais le nom canonique —
    le CV affiche le mot de l'annonce, qui est aussi celui que l'ATS
    cherche.

    Les écartées sont retournées plutôt que jetées : l'utilisateur
    doit pouvoir voir ce que le système a refusé de compter, et le
    rattraper à la main si le tri s'est trompé.
    """

    retenues: list[str] = []
    ecartees: list[str] = []

    vues: set[str] = set()

    for brut in skills:

        terme = (brut or "").strip()

        if not terme:
            continue

        if not is_plausible_requirement(terme):

            if _normalize(terme) not in {
                _normalize(item) for item in ecartees
            }:
                ecartees.append(terme)

            continue

        catalogue = find_skill_by_name(terme)

        # La clé de déduplication passe par le référentiel, le
        # libellé conservé reste celui de l'annonce.
        cle = _normalize(
            catalogue.canonical_name
            if catalogue is not None
            else terme
        )

        if cle in vues:
            continue

        vues.add(cle)
        retenues.append(terme)

    return retenues, ecartees
