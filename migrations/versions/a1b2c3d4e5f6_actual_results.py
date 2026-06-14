"""actual results

Revision ID: a1b2c3d4e5f6
Revises: 677311f11ba0
Create Date: 2026-06-13 21:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '677311f11ba0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'actual_results',
        sa.Column('match_number', sa.Integer(), nullable=False),
        sa.Column('home_score', sa.SmallInteger(), nullable=False),
        sa.Column('away_score', sa.SmallInteger(), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('match_number'),
    )


def downgrade() -> None:
    op.drop_table('actual_results')
