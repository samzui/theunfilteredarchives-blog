from alembic import op
import sqlalchemy as sa


revision = '05b2c8b8d881'
down_revision = '292306a393ae'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'community_submissions',
        sa.Column(
            'reviewed_at',
            sa.DateTime(timezone=True),
            nullable=True
        )
    )


def downgrade():
    op.drop_column(
        'community_submissions',
        'reviewed_at'
    )