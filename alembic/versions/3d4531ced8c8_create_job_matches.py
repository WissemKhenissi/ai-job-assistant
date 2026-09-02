"""create job matches

Revision ID: 3d4531ced8c8
Revises: 0838bcc0edfc
Create Date: 2026-08-21 18:21:13.404558
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3d4531ced8c8"
down_revision: Union[str, Sequence[str], None] = "0838bcc0edfc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_matches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("candidate_id", sa.String(), nullable=False),
        sa.Column("job_offer_id", sa.String(), nullable=False),
        sa.Column("score_global", sa.Float(), nullable=False),
        sa.Column("score_skills", sa.Float(), nullable=False),
        sa.Column("score_experience", sa.Float(), nullable=False),
        sa.Column("score_domain", sa.Float(), nullable=False),
        sa.Column("matched_skills", sa.JSON(), nullable=False),
        sa.Column("inferred_skills", sa.JSON(), nullable=False),
        sa.Column("missing_skills", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("weaknesses", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["job_offer_id"], ["job_offers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id",
            "job_offer_id",
            name="uq_job_matches_candidate_job_offer",
        ),
    )

    op.create_index(
        "ix_job_matches_candidate_id",
        "job_matches",
        ["candidate_id"],
    )

    op.create_index(
        "ix_job_matches_job_offer_id",
        "job_matches",
        ["job_offer_id"],
    )


def downgrade() -> None:
    pass