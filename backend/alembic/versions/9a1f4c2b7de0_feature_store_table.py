"""feature store table

Revision ID: 9a1f4c2b7de0
Revises: 48cb4f53e354
Create Date: 2026-07-20 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a1f4c2b7de0'
down_revision: Union[str, Sequence[str], None] = '48cb4f53e354'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'feature_vectors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False),
        sa.Column('feature_set_version', sa.String(), nullable=False),
        sa.Column('generated_time', sa.String(), nullable=True),
        sa.Column('period_label', sa.String(), nullable=True),
        sa.Column('period_type', sa.String(), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=True),
        sa.Column('feature_count', sa.Integer(), nullable=False),
        sa.Column('populated_count', sa.Integer(), nullable=False),
        sa.Column('low_confidence_count', sa.Integer(), nullable=False),
        sa.Column('coverage', sa.Float(), nullable=False),
        sa.Column('features', sa.JSON(), nullable=False),
        sa.Column('features_by_category', sa.JSON(), nullable=False),
        sa.Column('category_summary', sa.JSON(), nullable=False),
        sa.Column('registry_metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['enterprise_assessments.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_feature_vectors_id'), 'feature_vectors', ['id'], unique=False)
    op.create_index(op.f('ix_feature_vectors_user_id'), 'feature_vectors', ['user_id'], unique=False)
    op.create_index(op.f('ix_feature_vectors_assessment_id'), 'feature_vectors', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_feature_vectors_fiscal_year'), 'feature_vectors', ['fiscal_year'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_feature_vectors_fiscal_year'), table_name='feature_vectors')
    op.drop_index(op.f('ix_feature_vectors_assessment_id'), table_name='feature_vectors')
    op.drop_index(op.f('ix_feature_vectors_user_id'), table_name='feature_vectors')
    op.drop_index(op.f('ix_feature_vectors_id'), table_name='feature_vectors')
    op.drop_table('feature_vectors')
