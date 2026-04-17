"""Add PAP table and ioc_pap_id

Revision ID: b4e01e674f36
Revises: afcff5ebcf7c
Create Date: 2026-04-17 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import _table_has_column

revision = 'b4e01e674f36'
down_revision = 'afcff5ebcf7c'
branch_labels = None
depends_on = None


def upgrade():
    if not _has_table('pap'):
        op.create_table(
            'pap',
            sa.Column('pap_id', sa.Integer, primary_key=True),
            sa.Column('pap_name', sa.Text),
            sa.Column('pap_bscolor', sa.Text),
        )

    if not _table_has_column('ioc', 'ioc_pap_id'):
        op.add_column(
            'ioc',
            sa.Column('ioc_pap_id', sa.Integer, sa.ForeignKey('pap.pap_id'), nullable=True),
        )


def downgrade():
    if _table_has_column('ioc', 'ioc_pap_id'):
        op.drop_column('ioc', 'ioc_pap_id')

    if _has_table('pap'):
        op.drop_table('pap')
