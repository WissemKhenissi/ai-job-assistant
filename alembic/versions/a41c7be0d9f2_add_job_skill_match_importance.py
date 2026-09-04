"""niveau d'exigence sur le detail du matching

Le detail par competence disait ce que le candidat sait faire, jamais
ce que l'annonce en demandait. Une competence citee en exemple
(« environnement : Jira, Miro, GitLab ») pesait autant qu'une
condition d'entree.

Les lignes existantes prennent "souhaitee" : c'est le niveau neutre
du moteur, celui qu'il retient quand rien dans l'annonce ne tranche.
Une reanalyse recalculera le vrai niveau a partir du texte de
l'annonce, qui est conserve.

Revision ID: a41c7be0d9f2
Revises: eddfd0b1c0f6
Create Date: 2026-09-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a41c7be0d9f2"
down_revision: Union[str, None] = "eddfd0b1c0f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # SQLite ne sait pas ajouter une colonne NOT NULL sans valeur par
    # defaut : batch_alter_table + server_default reconstruit la table
    # proprement et remplit les lignes deja presentes.
    with op.batch_alter_table("job_skill_matches") as batch:

        batch.add_column(
            sa.Column(
                "importance",
                sa.String(),
                nullable=False,
                server_default="souhaitee",
            )
        )

    op.create_index(
        "ix_job_skill_matches_importance",
        "job_skill_matches",
        ["importance"],
    )


def downgrade() -> None:

    op.drop_index(
        "ix_job_skill_matches_importance",
        table_name="job_skill_matches",
    )

    with op.batch_alter_table("job_skill_matches") as batch:

        batch.drop_column("importance")
