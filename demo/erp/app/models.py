from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, DateTime, Integer, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def _now():
    return datetime.now(timezone.utc)


class Product(Base):
    __tablename__ = "products"
    sku: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))   # sin IGV
    stock: Mapped[int] = mapped_column(Integer, default=0)


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # customer_id viene del CRM. Es una REFERENCIA (sin FK): el ERP no comparte base con el CRM.
    customer_id: Mapped[str] = mapped_column(String(36), index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    igv: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    items: Mapped[list["InvoiceItem"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    sku: Mapped[str] = mapped_column(String(40))
    qty: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    invoice: Mapped[Invoice] = relationship(back_populates="items")
