"""Added notification is active

Revision ID: d0f1ea7d2b3b
Revises: 514174e44a8d
Create Date: 2024-09-07 11:12:07.798435

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0f1ea7d2b3b'
down_revision: Union[str, None] = '514174e44a8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('notifications', sa.Column('is_active', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('notifications', 'is_active')
    # ### end Alembic commands ###