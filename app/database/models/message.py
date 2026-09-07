import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import GUID, Base

if TYPE_CHECKING:
    from app.database.models.conversation import Conversation


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "channel",
            "external_chat_id",
            "external_message_id",
            "direction",
            name="uq_messages_channel_chat_msg_direction",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_chat_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    external_message_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # incoming / outgoing
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # received / sent / failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
