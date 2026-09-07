import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import GUID, Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.message import Message
    from app.database.models.user import User


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "channel", "external_chat_id", name="uq_conversations_channel_external_chat_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_chat_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        index=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
