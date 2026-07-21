"""risk alerts table

Revision ID: c3f8a6b2d9e1
Revises: b2e7d9c4a1f3
Create Date: 2026-07-21 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f8a6b2d9e1'
down_revision: Union[str, Sequence[str], None] = 'b2e7d9c4a1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'risk_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=False),
        sa.Column('alert_type', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('business_impact', sa.String(), nullable=True),
        sa.Column('suggested_action', sa.String(), nullable=True),
        sa.Column('timeline', sa.String(), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['enterprise_assessments.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_risk_alerts_id'), 'risk_alerts', ['id'], unique=False)
    op.create_index(op.f('ix_risk_alerts_user_id'), 'risk_alerts', ['user_id'], unique=False)
    op.create_index(op.f('ix_risk_alerts_assessment_id'), 'risk_alerts', ['assessment_id'], unique=False)
    op.create_index(op.f('ix_risk_alerts_severity'), 'risk_alerts', ['severity'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_risk_alerts_severity'), table_name='risk_alerts')
    op.drop_index(op.f('ix_risk_alerts_assessment_id'), table_name='risk_alerts')
    op.drop_index(op.f('ix_risk_alerts_user_id'), table_name='risk_alerts')
    op.drop_index(op.f('ix_risk_alerts_id'), table_name='risk_alerts')
    op.drop_table('risk_alerts')
