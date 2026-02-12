import enum
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base

class ChannelStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"

class AuthStatus(str, enum.Enum):
    pending = "pending_verification"
    anonymous = "anonymous"
    authenticated = "authenticated"

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    domain = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    users = relationship("User", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )

    organization = relationship("Organization", back_populates="users")
    channel_sessions = relationship("ChannelSession", back_populates="user")

class ChannelSession(Base):
    __tablename__ = "channel_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", name="uq_user_platform"),
        UniqueConstraint("platform", "external_user_id", name="uq_platform_external_user"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform = Column(String, nullable=False, index=True)
    external_user_id = Column(String, nullable=False)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    status = Column(
        String,
        nullable=False,
        default=ChannelStatus.active.value,
    )
    auth_status = Column(
        String,
        nullable=False,
        default=AuthStatus.anonymous.value,
    )
    auth_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    last_active_at = Column(DateTime(timezone=True))
    last_read_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    draft_ticket = Column(JSONB, nullable=True)

    user = relationship("User", back_populates="channel_sessions")
    messages = relationship(
        "Message",
        back_populates="channel_session",
        cascade="all, delete-orphan",
    )

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "external_message_id",
            name="uq_session_external_message_id",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("channel_sessions.id"),
        nullable=False,
        index=True,
    )
    external_message_id = Column(String, nullable=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    channel_session = relationship("ChannelSession", back_populates="messages")


class TicketLink(Base):
    __tablename__ = "ticket_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_key = Column(String, nullable=False, unique=True, index=True)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("channel_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform = Column(String, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    channel_session = relationship("ChannelSession")
    organization = relationship("Organization")

class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("channel_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email = Column(String, nullable=False)
    token = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session = relationship("ChannelSession")
