"""
Découpage du cahier des charges de rédaction de CV, étape par étape.

Le cahier des charges fourni compte 48 sections. Le donner en entier à
chaque appel serait contre-productif : un modèle à qui l'on demande
simultanément de sélectionner, rédiger, mettre en page et vérifier
fait mal les quatre. Chaque règle est donc rattachée à l'étape qui
peut réellement l'appliquer.

RÈGLES APPLIQUÉES PAR LE CODE, PAS PAR LE MODÈLE
    §3, 5, 6, 7, 8, 15, 17, 23, 24, 30, 34, 48 (sélection) sont déjà
    l'oeuvre de services.cv.selection : le contenu du CV est choisi
    de façon déterministe à partir de l'analyse de l'offre, ce qui
    garantit qu'une compétence non prouvée ne peut pas entrer dans le
    document, même si le modèle le souhaitait.
    §28 et 38 (une page) sont appliquées par services.cv.fitting, qui
    mesure un vrai PDF au lieu de demander une estimation.
    §31, 32, 36 (traçabilité, contrôle final) sont appliquées par
    services.cv.validation et services.generated_cv_service.
    §26 (cohérence du niveau de séniorité) est appliquée par
    services.cv.vocabulary.seniority_terms_added : comparer deux
    textes est un contrôle plus sûr qu'une consigne que le modèle
    peut oublier.
    §12 et 44 (ATS, terme canonique) sont structurellement acquises :
    une compétence n'est « prouvée » que si le référentiel relie le
    terme de l'annonce à une compétence du Master CV. Le CV affiche
    donc le mot de l'annonce, qui est aussi celui que l'ATS cherche.

RÈGLES ÉCARTÉES VOLONTAIREMENT
    §27, 39, 40, 45 décrivent l'ordre des sections, le format des
    expériences et l'adaptation du style à la culture de l'entreprise.
    C'est le travail du gabarit d'export (services.cv.export), pas
    celui du modèle : lui demander de produire une mise en page
    revient à lui laisser réécrire la structure du document à chaque
    appel, sans aucun gain de véracité.
    §46 (rédiger dans la langue de l'offre) est reportée : les
    garde-fous du projet — comparaison des chiffres, extraits
    verbatim — perdent leur force à travers une traduction, et
    livrer la traduction sans son garde-fou reviendrait à supprimer
    le contrôle en même temps.

RÈGLES CONFIÉES AU MODÈLE, ICI
    ANTI_INVENTION (§1, 2, 33, 37) : préambule commun à tous les
    appels de rédaction.
    FORMULATION (§9, 10, 41, 42, 43) : rédaction d'une ligne
    d'expérience.
    RESUME (§14) : rédaction du résumé de profil.
    build_vocabulary_rules (§11) : adaptation du vocabulaire, bornée
    par le référentiel plutôt que laissée au jugement du modèle.
"""

from __future__ import annotations


# ============================================================
# PREAMBULE COMMUN (§1, 2, 33, 37)
# ============================================================

ANTI_INVENTION = """SOURCE DE VÉRITÉ
Le texte source est la seule information autorisée. Tu peux le raccourcir, le reformuler, le réorganiser, le rendre plus direct et adapter son vocabulaire au poste visé. Tu ne peux jamais inventer une expérience, une compétence, une responsabilité, un résultat, un chiffre, une technologie, un outil, un diplôme, une certification, un niveau de langue, un secteur, un projet, une réalisation ni une responsabilité managériale. Si une information ne figure pas dans le texte source, elle ne doit pas apparaître.

FAITS ET DÉDUCTIONS
Ne transforme jamais une hypothèse en fait, ni une responsabilité en résultat, ni une compétence seulement déduite en compétence explicitement maîtrisée. N'ajoute aucune action ou étape supplémentaire, même plausible ou habituelle pour ce type de mission : le texte reformulé doit décrire exactement les mêmes actions que le texte source, ni plus, ni moins. Exemple interdit : transformer « identification d'opportunités » en « analyse de marché et identification d'opportunités » — « analyse de marché » n'était pas dans le texte source, même si c'en est un préalable plausible.

NIVEAU ANNONCÉ
Ne rehausse jamais un niveau : une expérience ne devient pas une expertise, une participation ne devient pas une responsabilité, et le candidat ne devient ni senior, ni lead, ni expert parce que l'offre emploie ces mots.

EN CAS DE DOUTE
Si tu hésites entre une formulation moins impressionnante mais certaine et une formulation plus impressionnante mais incertaine, choisis toujours la première. La crédibilité du candidat passe avant l'optimisation du CV.

VÉRIFICATION AVANT DE RÉPONDRE
Pour chaque élément que tu écris, demande-toi : « puis-je identifier sa source dans le texte fourni ? » Si non, supprime-le. Ne complète jamais avec tes connaissances générales. Si tu ne peux pas reformuler sans ajouter d'information, renvoie le texte source tel quel."""


# ============================================================
# LIGNE D'EXPERIENCE (§9, 10, 41, 42, 43)
# ============================================================

FORMULATION = """FORMULATION
Évite les descriptions génériques du type « gestion de différents projets et collaboration avec les équipes ». Préfère la forme : action menée, sur quel contexte, avec quelles équipes, dans quel but — en n'utilisant que ce que le texte source contient réellement.

IMPACT
Quand le texte source fournit un résultat, écris action + contexte + impact. Quand il n'en fournit pas, arrête-toi au contexte : ne fabrique jamais un résultat, ne présente jamais une responsabilité comme une réussite.

VERBES D'ACTION
Ouvre la ligne par un verbe d'action précis — piloté, conçu, déployé, structuré, optimisé, analysé, coordonné, automatisé, lancé, négocié, accompagné, mis en place — uniquement lorsque ce verbe correspond réellement à l'action décrite dans le texte source.

NE PAS COPIER L'ANNONCE
Ne reprends pas les phrases de l'annonce. Le CV doit démontrer la correspondance par le parcours réel du candidat, pas recopier l'offre."""


# ============================================================
# RESUME DE PROFIL (§14)
# ============================================================

RESUME = """RÉSUMÉ DE PROFIL
Le résumé doit rester court — 40 à 70 mots — factuel et ciblé : identité professionnelle, niveau d'expérience, domaine principal, deux ou trois forces réellement pertinentes pour cette offre. Pas de succession de qualités génériques du type « professionnel dynamique, motivé et rigoureux »."""


# ============================================================
# VOCABULAIRE (§11), BORNE PAR LE REFERENTIEL
# ============================================================

def build_vocabulary_rules(
    authorized: tuple[str, ...] | list[str],
    forbidden: tuple[str, ...] | list[str],
) -> str:
    """
    Règle de vocabulaire construite à partir du référentiel.

    Le cahier des charges dit « utilise le vocabulaire de l'offre
    lorsqu'il correspond réellement au parcours ». Laisser le modèle
    juger de cette correspondance, c'est lui laisser décider qu'une
    compétence est acquise — exactement ce que le projet lui refuse.
    On lui donne donc deux listes closes, calculées par le code :
    les termes que le référentiel relie à une compétence prouvée, et
    ceux que l'annonce demande sans que le candidat les ait prouvés.
    """

    blocs: list[str] = []

    if authorized:

        termes = "\n".join(f"- {terme}" for terme in authorized)

        blocs.append(
            "VOCABULAIRE AUTORISÉ\n"
            "Pour désigner une compétence, tu peux employer les "
            "termes suivants, et uniquement ceux-là : le référentiel "
            "les relie à une compétence que le candidat a réellement "
            "prouvée. Cette liste est une permission de renommer, "
            "pas une consigne d'ajouter : un terme ne se justifie "
            "que s'il désigne autrement quelque chose que le texte "
            "source décrit déjà. N'en place aucun s'il n'a rien à "
            f"traduire.\n{termes}"
        )

    if forbidden:

        termes = "\n".join(f"- {terme}" for terme in forbidden)

        blocs.append(
            "TERMES INTERDITS\n"
            "L'annonce emploie aussi les termes suivants, que le "
            "candidat n'a pas prouvés. Ne les écris jamais, même "
            "s'ils rapprocheraient la ligne de l'offre, et même sous "
            f"une forme voisine.\n{termes}"
        )

    blocs.append(
        "N'emploie aucun autre mot-clé de l'annonce pour qualifier "
        "une compétence, et ne force jamais un mot-clé dans le seul "
        "but d'améliorer un score ATS."
    )

    return "\n\n".join(blocs)
