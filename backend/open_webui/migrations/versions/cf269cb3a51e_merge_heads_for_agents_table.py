"""Merge heads for agents table

Revision ID: cf269cb3a51e
Revises: 3781e22d8b01, d488d31a738e
Create Date: 2025-06-27 13:50:16.485276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = 'cf269cb3a51e'
down_revision: Union[str, None] = ('3781e22d8b01', 'd488d31a738e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
