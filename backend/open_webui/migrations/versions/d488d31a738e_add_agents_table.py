"""Add agents table

Revision ID: d488d31a738e
Revises: ca81bd47c050
Create Date: 2025-06-26 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d488d31a738e"
down_revision: Union[str, None] = "ca81bd47c050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "agent",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("agent_type", sa.String(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=True),
        sa.Column("valves", sa.JSON(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("access_control", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True, onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("agent")
