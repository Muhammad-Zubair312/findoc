"""widen_document_nodes_title_to_text

Revision ID: 636533c22e44
Revises: c2ec0811a633
Create Date: 2026-07-11 12:13:45.468474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '636533c22e44'
down_revision: Union[str, Sequence[str], None] = 'c2ec0811a633'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # document_nodes.title was VARCHAR(500); some SEC filing section titles
    # (e.g. long Item headings with embedded sub-clauses) exceed that and
    # raised a StringDataRightTruncation error during ingestion.
    op.alter_column(
        "document_nodes",
        "title",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "document_nodes",
        "title",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
    )
