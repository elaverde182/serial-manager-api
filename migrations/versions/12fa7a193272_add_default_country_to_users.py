"""add default_country_code to users

Revision ID: 12fa7a193272
Revises: ee1143141713
Create Date: 2026-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '12fa7a193272'
down_revision: Union[str, None] = 'ee1143141713'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('default_country_code', sa.String(length=3), nullable=True))
        batch_op.create_foreign_key(
            'fk_users_default_country_code', 'countries', ['default_country_code'], ['code']
        )


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('fk_users_default_country_code', type_='foreignkey')
        batch_op.drop_column('default_country_code')
