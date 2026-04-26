import enum
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Enum, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.core.uuid7 import uuid7_str


class ScanStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    paused = "paused"
    finished = "finished"
    failed = "failed"


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid7_str)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.pending, nullable=False, index=True)
    max_depth: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)
    excluded_paths: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # crawler state — URL graph и очередь хранятся в таблице scan_queue (Sprint 3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped["User"] = relationship("User", back_populates="scans")
    vulnerabilities: Mapped[list["Vulnerability"]] = relationship("Vulnerability", back_populates="scan", cascade="all, delete-orphan")
