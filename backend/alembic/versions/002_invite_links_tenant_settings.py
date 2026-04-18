"""invite links and tenant company settings

Revision ID: 002
Revises: 001
Create Date: 2026-03-21

"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(255), server_default="", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO tenant_settings (id, company_name) VALUES (1, '')")

    op.create_table(
        "invite_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("is_permanent", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_visits", sa.Integer(), nullable=True),
        sa.Column("visit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_invite_links_token"),
    )
    op.create_index("ix_invite_links_token", "invite_links", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_invite_links_token", table_name="invite_links")
    op.drop_table("invite_links")
    op.drop_table("tenant_settings")
