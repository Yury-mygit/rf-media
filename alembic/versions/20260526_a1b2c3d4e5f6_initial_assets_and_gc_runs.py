"""initial assets and gc_runs

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-05-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'assets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('mime', sa.String(length=80), nullable=False),
        sa.Column('bytes', sa.Integer(), nullable=False),
        sa.Column('has_thumb', sa.Boolean(), nullable=False),
        sa.Column('thumb_mime', sa.String(length=80), nullable=True),
        sa.Column('thumb_bytes', sa.Integer(), nullable=True),
        sa.Column('uploaded_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('deleted_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sha256'),
    )
    op.create_index('ix_assets_sha256', 'assets', ['sha256'], unique=True)
    op.create_index('ix_assets_created_at', 'assets', ['created_at'])

    op.create_table(
        'gc_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('started_at', sa.BigInteger(), nullable=False),
        sa.Column('finished_at', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('consumers_ok', sa.Integer(), nullable=False),
        sa.Column('consumers_failed', sa.Integer(), nullable=False),
        sa.Column('total_refs', sa.Integer(), nullable=False),
        sa.Column('deleted', sa.Integer(), nullable=False),
        sa.Column('error_text', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('gc_runs')
    op.drop_index('ix_assets_created_at', table_name='assets')
    op.drop_index('ix_assets_sha256', table_name='assets')
    op.drop_table('assets')
