from datetime import datetime
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    lang: Mapped[str] = mapped_column(String(2), default="ru", server_default="ru", nullable=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    premium_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    role: Mapped[str] = mapped_column(String(50), default="user", server_default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tg_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # private, group, supergroup, channel

    monitored_servers: Mapped[List["MonitoredServer"]] = relationship(
        "MonitoredServer", back_populates="chat", cascade="all, delete-orphan"
    )


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=25565, nullable=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("ip_domain", "port", name="uix_server_ip_port"),
    )

    monitors: Mapped[List["MonitoredServer"]] = relationship(
        "MonitoredServer", back_populates="server", cascade="all, delete-orphan"
    )


class MonitoredServer(Base):
    __tablename__ = "monitored_servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    server_id: Mapped[int] = mapped_column(ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    custom_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Настройки отображения
    show_tps: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    show_motd: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    show_players: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    
    # Интеграция с темами в Telegram
    gamechat_thread_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    
    # Управление мониторингом
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=60, server_default="60", nullable=False)

    # Связи
    chat: Mapped["Chat"] = relationship("Chat", back_populates="monitored_servers")
    server: Mapped["Server"] = relationship("Server", back_populates="monitors")
