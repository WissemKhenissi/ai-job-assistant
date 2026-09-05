"""les composantes du Product Management passent dans le referentiel

L'inference composite deduisait « Product Management » d'un faisceau
de neuf competences produit, ecrites en dur dans le moteur. En les
generalisant — une competence d'ensemble se deduit des competences
que le referentiel lui associe — cinq d'entre elles se sont perdues :
le referentiel n'en associait que quatre.

Ce n'est pas une regle a retablir dans le code, c'est une donnee a
completer la ou elle appartient. Les cinq manquantes sont ajoutees
aux competences associees de Product Management ; elles y sont a leur
place independamment de l'inference, un referentiel qui ignore le
lien entre Product Management et la priorisation est incomplet.

Revision ID: d1e5a9c73b20
Revises: c8b3f1a27d54
Create Date: 2026-09-05

"""

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d1e5a9c73b20"
down_revision: Union[str, None] = "c8b3f1a27d54"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COMPOSANTES_AJOUTEES = (
    "Priorisation",
    "Backlog Management",
    "Experimentation",
    "Stakeholder Management",
    "Agile / Scrum",
)


def upgrade() -> None:

    connexion = op.get_bind()

    ligne = connexion.execute(
        sa.text(
            "SELECT id, related_skills FROM skill_catalog "
            "WHERE canonical_name = 'Product Management'"
        )
    ).fetchone()

    if ligne is None:
        # Referentiel sans cette entree (base neuve, autre profil) :
        # rien a completer.
        return

    try:
        associees = json.loads(ligne[1] or "[]")
    except (TypeError, ValueError):
        associees = []

    if not isinstance(associees, list):
        associees = []

    for nom in COMPOSANTES_AJOUTEES:
        if nom not in associees:
            associees.append(nom)

    connexion.execute(
        sa.text(
            "UPDATE skill_catalog SET related_skills = :valeur "
            "WHERE id = :identifiant"
        ),
        {
            "valeur": json.dumps(associees, ensure_ascii=False),
            "identifiant": ligne[0],
        },
    )


def downgrade() -> None:

    connexion = op.get_bind()

    ligne = connexion.execute(
        sa.text(
            "SELECT id, related_skills FROM skill_catalog "
            "WHERE canonical_name = 'Product Management'"
        )
    ).fetchone()

    if ligne is None:
        return

    try:
        associees = json.loads(ligne[1] or "[]")
    except (TypeError, ValueError):
        return

    restantes = [
        nom
        for nom in associees
        if nom not in COMPOSANTES_AJOUTEES
    ]

    connexion.execute(
        sa.text(
            "UPDATE skill_catalog SET related_skills = :valeur "
            "WHERE id = :identifiant"
        ),
        {
            "valeur": json.dumps(restantes, ensure_ascii=False),
            "identifiant": ligne[0],
        },
    )
