"""le referentiel dit quelles competences peuvent etre deduites

Le moteur portait cette connaissance dans deux listes ecrites a la
main : SEMANTIC_INFERENCE_SKILLS (douze competences produit, seules
autorisees a l'inference) et SEMANTIC_INFERENCE_EXCLUDED (onze
technologies interdites). Avec un referentiel de 13 476 entrees, la
premiere condamnait 13 464 competences a ne jamais etre deduites : un
profil d'infirmiere ou de developpeur ne pouvait produire que
« prouve », « declare » ou « manquant ».

La distinction reelle n'a rien de propre a un metier : un savoir-faire
se devine d'un recit d'experience, un outil ou un corpus de
connaissances non. Elle appartient donc au referentiel.

Valeurs initiales :

- entrees ESCO : la taxonomie porte deja la distinction dans son
  champ skillType, range par l'importateur dans `subcategory`.
  « knowledge » (Python, logistique, droit du travail) devient non
  deductible ; « skill/competence » reste deductible ;
- entrees maison : non deductibles pour les categories Technology,
  Tools et AI, plus SQL et Data Science, nommes parce que leur
  categorie « Data » ne les distingue pas d'une competence d'analyse ;
- Product Management est non deductible par ressemblance, comme il
  l'etait deja : il reste deduit par composition, a partir des
  competences que le referentiel lui associe.

Revision ID: c8b3f1a27d54
Revises: a41c7be0d9f2
Create Date: 2026-09-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c8b3f1a27d54"
down_revision: Union[str, None] = "a41c7be0d9f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Entrees maison dont la categorie ne suffit pas a trancher.
NON_DEDUCTIBLES_NOMMEES = (
    "SQL",
    "Data Science",
    "Product Management",
)

# Categories maison qui designent un outil ou une technologie.
CATEGORIES_NON_DEDUCTIBLES = ("Technology", "Tools", "AI")


def upgrade() -> None:

    with op.batch_alter_table("skill_catalog") as batch:

        batch.add_column(
            sa.Column(
                "is_inferable",
                sa.Boolean(),
                nullable=False,
                server_default="1",
            )
        )

    noms = ", ".join(f"'{nom}'" for nom in NON_DEDUCTIBLES_NOMMEES)
    categories = ", ".join(
        f"'{categorie}'" for categorie in CATEGORIES_NON_DEDUCTIBLES
    )

    # ESCO : la taxonomie tranche elle-meme.
    op.execute(
        """
        UPDATE skill_catalog
           SET is_inferable = 0
         WHERE id LIKE 'esco-%'
           AND subcategory = 'knowledge'
        """
    )

    # Entrees maison : categorie d'outil, ou nommees.
    op.execute(
        f"""
        UPDATE skill_catalog
           SET is_inferable = 0
         WHERE id NOT LIKE 'esco-%'
           AND (category IN ({categories})
                OR canonical_name IN ({noms}))
        """
    )


def downgrade() -> None:

    with op.batch_alter_table("skill_catalog") as batch:

        batch.drop_column("is_inferable")
