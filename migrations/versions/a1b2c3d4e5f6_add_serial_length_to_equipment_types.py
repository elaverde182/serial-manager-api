"""add serial_length to equipment_types and widen random_code

Revision ID: a1b2c3d4e5f6
Revises: c83e10180e90
Create Date: 2026-07-24 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'c83e10180e90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Longitud del serial de fábrica por modelo (NULL = usar formato por país).
    with op.batch_alter_table('equipment_types') as batch_op:
        batch_op.add_column(sa.Column('serial_length', sa.Integer(), nullable=True))

    # El serial plano por modelo puede llegar a 16 caracteres: la columna del
    # código aleatorio guarda el serial completo en ese modo.
    with op.batch_alter_table('equipment_tags') as batch_op:
        batch_op.alter_column(
            'random_code',
            existing_type=sa.String(length=12),
            type_=sa.String(length=20),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('equipment_tags') as batch_op:
        batch_op.alter_column(
            'random_code',
            existing_type=sa.String(length=20),
            type_=sa.String(length=12),
            existing_nullable=False,
        )
    with op.batch_alter_table('equipment_types') as batch_op:
        batch_op.drop_column('serial_length')
