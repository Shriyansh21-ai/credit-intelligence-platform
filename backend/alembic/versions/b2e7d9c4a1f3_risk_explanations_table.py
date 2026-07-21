"""risk explanations table

Revision ID: b2e7d9c4a1f3
Revises: 9a1f4c2b7de0
Create Date: 2026-07-20 00:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2e7d9c4a1f3'
down_revision: Union[str, Sequence[str], None] = '9a1f4c2b7de0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'risk_explanations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False),
        sa.Column('model_type', sa.String(), nullable=False),
        sa.Column('method', sa.String(), nullable=False),
        sa.Column('probability_of_default', sa.Float(), nullable=True),
        sa.Column('base_probability', sa.Float(), nullable=True),
        sa.Column('risk_score', sa.Integer(), nullable=True),
        sa.Column('risk_grade', sa.String(), nullable=True),
        sa.Column('summary', sa.String(), nullable=True),
        sa.Column('contributions', sa.JSON(), nullable=False),
        sa.Column('top_positive', sa.JSON(), nullable=False),
        sa.Column('top_negative', sa.JSON(), nullable=False),
        sa.Column('waterfall', sa.JSON(), nullable=False),
        sa.Column('global_importance', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['enterprise_assessments.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_risk_explanations_id'), 'risk_explanations', ['id'], unique=False)
    op.create_index(op.f('ix_risk_explanations_user_id'), 'risk_explanations', ['user_id'], unique=False)
    op.create_index(op.f('ix_risk_explanations_assessment_id'), 'risk_explanations', ['assessment_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_risk_explanations_assessment_id'), table_name='risk_explanations')
    op.drop_index(op.f('ix_risk_explanations_user_id'), table_name='risk_explanations')
    op.drop_index(op.f('ix_risk_explanations_id'), table_name='risk_explanations')
    op.drop_table('risk_explanations')
