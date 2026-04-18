"""Initial schema — all tables

Revision ID: 001
Revises: 
Create Date: 2026-02-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("username", sa.String(100), unique=True, nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("tz", sa.String(50), server_default="UTC", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # auth_credentials
    op.create_table(
        "auth_credentials",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("login", sa.String(100), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # user_roles
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("added_by", sa.BigInteger(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    # push_tokens
    op.create_table(
        "push_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token", sa.String(500), unique=True, nullable=False),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # activities
    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("grp", sa.String(50), nullable=False),
        sa.Column("pos", sa.Integer(), default=0, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # locations
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("grp", sa.String(50), nullable=False),
        sa.Column("pos", sa.Integer(), default=0, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # machine_kinds
    op.create_table(
        "machine_kinds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("mode", sa.String(20), default="list", nullable=False),
        sa.Column("pos", sa.Integer(), default=0, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # machine_items
    op.create_table(
        "machine_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("pos", sa.Integer(), default=0, nullable=False),
        sa.ForeignKeyConstraint(["kind_id"], ["machine_kinds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # crops
    op.create_table(
        "crops",
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("pos", sa.Integer(), default=0, nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )

    # reports
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("reg_name", sa.String(255), nullable=True),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("location_grp", sa.String(50), nullable=True),
        sa.Column("activity", sa.String(255), nullable=True),
        sa.Column("activity_grp", sa.String(50), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=True),
        sa.Column("hours", sa.Float(), nullable=True),
        sa.Column("machine_type", sa.String(50), nullable=True),
        sa.Column("machine_name", sa.String(255), nullable=True),
        sa.Column("crop", sa.String(100), nullable=True),
        sa.Column("trips", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # brigadier_reports
    op.create_table(
        "brigadier_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("work_type", sa.String(255), nullable=True),
        sa.Column("field", sa.String(255), nullable=True),
        sa.Column("shift", sa.String(50), nullable=True),
        sa.Column("rows", sa.Integer(), nullable=True),
        sa.Column("bags", sa.Integer(), nullable=True),
        sa.Column("workers", sa.Integer(), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # groups
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["groups.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # group_members
    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(50), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "group_id"),
    )

    # form_templates
    op.create_table(
        "form_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("schema", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # form_assignments
    op.create_table(
        "form_assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("form_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(50), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["form_id"], ["form_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # form_responses
    op.create_table(
        "form_responses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("form_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("data", JSONB(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["form_id"], ["form_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # chat_rooms
    op.create_table(
        "chat_rooms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("type", sa.String(20), default="group", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # chat_room_members
    op.create_table(
        "chat_room_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["chat_rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_id", "user_id"),
    )

    # chat_messages
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.BigInteger(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default="false", nullable=False),
        sa.ForeignKeyConstraint(["room_id"], ["chat_rooms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Indexes
    op.create_index("ix_reports_user_date", "reports", ["user_id", "work_date"])
    op.create_index("ix_reports_work_date", "reports", ["work_date"])
    op.create_index("ix_chat_messages_room", "chat_messages", ["room_id", "id"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_room_members")
    op.drop_table("chat_rooms")
    op.drop_table("form_responses")
    op.drop_table("form_assignments")
    op.drop_table("form_templates")
    op.drop_table("group_members")
    op.drop_table("groups")
    op.drop_table("brigadier_reports")
    op.drop_table("reports")
    op.drop_table("crops")
    op.drop_table("machine_items")
    op.drop_table("machine_kinds")
    op.drop_table("locations")
    op.drop_table("activities")
    op.drop_table("push_tokens")
    op.drop_table("user_roles")
    op.drop_table("auth_credentials")
    op.drop_table("users")
