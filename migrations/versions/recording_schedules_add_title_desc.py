"""add title and description to recording_schedules

Revision ID: recording_schedules_03
Revises: recording_schedules_02
Create Date: 2026-10-18 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'recording_schedules_03'
down_revision = 'recording_schedules_02'
branch_labels = None
depends_on = None

def has_column(table, column):
    """Verifica si una columna ya existe en la tabla para evitar errores."""
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [c['name'] for c in inspector.get_columns(table)]
    return column in columns

def upgrade():
    with op.batch_alter_table('recording_schedules', schema=None) as batch_op:
        if not has_column('recording_schedules', 'title'):
            batch_op.add_column(sa.Column('title', sa.String(500), nullable=True))
        if not has_column('recording_schedules', 'description'):
            batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))

def downgrade():
    with op.batch_alter_table('recording_schedules', schema=None) as batch_op:
        if has_column('recording_schedules', 'description'):
            batch_op.drop_column('description')
        if has_column('recording_schedules', 'title'):
            batch_op.drop_column('title')