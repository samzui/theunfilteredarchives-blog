from alembic import op
import sqlalchemy as sa


revision = '292306a393ae'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'community_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=220), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('consent', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(
        op.f('ix_community_submissions_created_at'),
        'community_submissions',
        ['created_at'],
        unique=False
    )

    op.create_index(
        op.f('ix_community_submissions_email'),
        'community_submissions',
        ['email'],
        unique=False
    )

    op.create_index(
        op.f('ix_community_submissions_status'),
        'community_submissions',
        ['status'],
        unique=False
    )


def downgrade():
    op.drop_index(
        op.f('ix_community_submissions_status'),
        table_name='community_submissions'
    )

    op.drop_index(
        op.f('ix_community_submissions_email'),
        table_name='community_submissions'
    )

    op.drop_index(
        op.f('ix_community_submissions_created_at'),
        table_name='community_submissions'
    )

    op.drop_table('community_submissions')