"""tenant_settings.reports_feed_room_id for org-wide report announcements chat

Revision ID: 003
Revises: 002
Create Date: 2026-03-23

"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenant_settings",
        sa.Column("reports_feed_room_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tenant_settings_reports_feed_room",
        "tenant_settings",
        "chat_rooms",
        ["reports_feed_room_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tenant_settings_reports_feed_room", "tenant_settings", type_="foreignkey")
    op.drop_column("tenant_settings", "reports_feed_room_id")
