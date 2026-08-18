from alembic import op
import sqlalchemy as sa


revision = "f4d2d0c46326"
down_revision = "3a723c2f31a4"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "writings",
        "cover_image_url",
        existing_type=sa.VARCHAR(length=1000),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade():
    op.alter_column(
        "writings",
        "cover_image_url",
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=1000),
        existing_nullable=True,
    )