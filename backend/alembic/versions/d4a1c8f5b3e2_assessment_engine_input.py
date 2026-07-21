"""assessment engine_input column

Revision ID: d4a1c8f5b3e2
Revises: c3f8a6b2d9e1
Create Date: 2026-07-21 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a1c8f5b3e2'
down_revision: Union[str, Sequence[str], None] = 'c3f8a6b2d9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('enterprise_assessments', sa.Column('engine_input', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('enterprise_assessments', 'engine_input')
