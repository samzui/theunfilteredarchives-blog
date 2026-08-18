from alembic import op
import sqlalchemy as sa


revision = "3a723c2f31a4"
down_revision = "05b2c8b8d881"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "visitor_key",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "writing_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "event_type",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["writing_id"],
            ["writings.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_analytics_events_created_at",
        "analytics_events",
        ["created_at"],
        unique=False,
    )

    op.create_index(
        "ix_analytics_events_event_type",
        "analytics_events",
        ["event_type"],
        unique=False,
    )

    op.create_index(
        "ix_analytics_events_user_id",
        "analytics_events",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        "ix_analytics_events_visitor_key",
        "analytics_events",
        ["visitor_key"],
        unique=False,
    )

    op.create_index(
        "ix_analytics_events_writing_id",
        "analytics_events",
        ["writing_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_analytics_events_writing_id",
        table_name="analytics_events",
    )

    op.drop_index(
        "ix_analytics_events_visitor_key",
        table_name="analytics_events",
    )

    op.drop_index(
        "ix_analytics_events_user_id",
        table_name="analytics_events",
    )

    op.drop_index(
        "ix_analytics_events_event_type",
        table_name="analytics_events",
    )

    op.drop_index(
        "ix_analytics_events_created_at",
        table_name="analytics_events",
    )

    op.drop_table("analytics_events")