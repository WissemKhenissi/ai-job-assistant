"""le referentiel dit quelles competences sont des ensembles

L'inference composite deduisait une competence transverse d'un
faisceau de competences constitutives. Generalisee a toute entree
possedant des competences associees, elle a produit son premier
resultat aberrant : « Jira » deduit parce que le candidat pratique
Agile, la gestion de backlog et la gestion de projet. Jira est
associe a ces trois competences, il n'en est pas fait.

`related_skills` dit « associe a », jamais « fait de ». Cette colonne
dit lesquelles de ces associations valent composition.

Valeur initiale : seul « Product Management » l'obtient. C'est la
seule composition que quiconque ait jamais affirmee — elle vivait
dans le moteur, sous la forme d'une liste de neuf noms. La consigner
ici ne l'etend a personne d'autre, mais elle devient une donnee que
le referentiel peut porter pour n'importe quel metier, au lieu d'une
regle qu'un seul metier pouvait declencher.

Revision ID: e94d2f8a1c07
Revises: d1e5a9c73b20
Create Date: 2026-09-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e94d2f8a1c07"
down_revision: Union[str, None] = "d1e5a9c73b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    with op.batch_alter_table("skill_catalog") as batch:

        batch.add_column(
            sa.Column(
                "is_composite",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )

    op.execute(
        """
        UPDATE skill_catalog
           SET is_composite = 1
         WHERE canonical_name = 'Product Management'
        """
    )


def downgrade() -> None:

    with op.batch_alter_table("skill_catalog") as batch:

        batch.drop_column("is_composite")
