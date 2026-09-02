"""create job offers

Revision ID: 51db98f33c15
Revises: 3d4531ced8c8
Create Date: 2026-08-21 19:57:49.050079
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "51db98f33c15"
down_revision: Union[str, Sequence[str], None] = "3d4531ced8c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_offers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=False),
        sa.Column("contract_type", sa.String(), nullable=False),
        sa.Column("remote_policy", sa.String(), nullable=False),
        sa.Column("salary", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("job_offers")