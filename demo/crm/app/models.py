import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def _now():
    return datetime.now(timezone.utc)


class Customer(Base):
    """Cliente maestro. El CRM es el sistema oficial del ID único de cliente."""
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("doc_type", "doc_number", name="uq_customer_doc"),)

    customer_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_type: Mapped[str] = mapped_column(String(10))       # DNI, RUC, CE
    doc_number: Mapped[str] = mapped_column(String(20))
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    """Registro de accesos a datos personales (Ley N.º 29733 y su reglamento, art. 46):
    quién, cuándo, qué acción, sobre qué dato y con qué resultado."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    username: Mapped[str] = mapped_column(String(100))
    roles: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(40))
    resource: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result: Mapped[str] = mapped_column(String(20))  # PERMITIDO | DENEGADO
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
