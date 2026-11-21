import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def _now():
    return datetime.now(timezone.utc)


class Sale(Base):
    """Venta en tienda. Estados: EN_COLA -> ENVIADO -> FACTURADO | RECHAZADO.
    Se guarda SIEMPRE primero en la base local: la tienda vende aunque no haya red."""
    __tablename__ = "sales"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    store_id: Mapped[str] = mapped_column(String(20), default="TIENDA-01")
    customer_id: Mapped[str] = mapped_column(String(36), default="CONSUMIDOR_FINAL")
    items_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="EN_COLA", index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    invoice_id: Mapped[int | None] = mapped_column(nullable=True)
    total: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
