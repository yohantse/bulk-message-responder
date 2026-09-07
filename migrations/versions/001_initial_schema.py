"""Initial schema for users, conversations, and messages

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-07 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Use postgresql.UUID if postgresql, or fallback to CHAR(36)
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    uuid_type = postgresql.UUID(as_uuid=True) if is_pg else sa.CHAR(36)

    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("external_user_id", sa.String(100), nullable=False),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "channel", "external_user_id", name="uq_users_channel_external_user_id"
        ),
    )
    op.create_index("ix_users_channel", "users", ["channel"])
    op.create_index("ix_users_external_user_id", "users", ["external_user_id"])

    # 2. conversations table
    op.create_table(
        "conversations",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("external_chat_id", sa.String(100), nullable=False),
        sa.Column(
            "user_id", uuid_type, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "channel", "external_chat_id", name="uq_conversations_channel_external_chat_id"
        ),
    )
    op.create_index("ix_conversations_channel", "conversations", ["channel"])
    op.create_index("ix_conversations_external_chat_id", "conversations", ["external_chat_id"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_index("ix_conversations_status", "conversations", ["status"])

    # 3. messages table
    op.create_table(
        "messages",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "conversation_id",
            uuid_type,
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("external_chat_id", sa.String(100), nullable=False),
        sa.Column("external_message_id", sa.String(100), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("message_type", sa.String(20), server_default="text", nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "channel",
            "external_chat_id",
            "external_message_id",
            "direction",
            name="uq_messages_channel_chat_msg_direction",
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_channel", "messages", ["channel"])
    op.create_index("ix_messages_external_chat_id", "messages", ["external_chat_id"])
    op.create_index("ix_messages_external_message_id", "messages", ["external_message_id"])
    op.create_index("ix_messages_direction", "messages", ["direction"])
    op.create_index("ix_messages_status", "messages", ["status"])


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("users")
