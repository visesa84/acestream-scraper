"""create epg_programs table

Revision ID: epg_programs_table
Revises: 20250412_add_epg_channels_update_tv_channels
Create Date: 2026-10-19 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'epg_programs_table'
down_revision = '20250412_add_epg_channels_update_tv_channels'
branch_labels = None
depends_on = None

def has_table(table_name):
    conn = op.get_bind()
    insp = inspect(conn)
    return table_name in insp.get_table_names()

def upgrade():
    if not has_table('epg_programs'):
        op.create_table(
            'epg_programs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('epg_channel_id', sa.Integer(), nullable=False),
            sa.Column('program_xml_id', sa.String(length=255), nullable=True),
            sa.Column('start_time', sa.DateTime(), nullable=False),
            sa.Column('end_time', sa.DateTime(), nullable=False),
            sa.Column('title', sa.String(length=500), nullable=False),
            sa.Column('subtitle', sa.String(length=500), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('category', sa.String(length=100), nullable=True),
            sa.Column('language', sa.String(length=50), nullable=True),
            sa.Column('episode_number', sa.String(length=100), nullable=True),
            sa.Column('rating', sa.String(length=20), nullable=True),
            sa.Column('icon_url', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['epg_channel_id'], ['epg_channels.id'], ),
            sa.PrimaryKeyConstraint('id')
        )

def downgrade():
    if has_table('epg_programs'):
        op.drop_table('epg_programs')