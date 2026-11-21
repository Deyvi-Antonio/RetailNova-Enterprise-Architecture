import logging
from contextlib import asynccontextmanager
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import bus, events
from .db import Base, engine, get_db
from .models import Product, Invoice
from .service import create_invoice as create_invoice_core, DomainError

logging.basicConfig(level=logging.INFO)
Base.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app):
    if bus.URL:
        bus.start_consumer("erp.ventas", ["order.created", "sale.created"], events.handle)
    yield

app = FastAPI(title="RetailNova ERP", version="0.2.0", lifespan=lifespan)


class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    name: str
    price: Decimal = Field(gt=0)
    stock: int = Field(ge=0, default=0)


class ProductOut(ProductIn):
    model_config = {"from_attributes": True}


class ItemIn(BaseModel):
    sku: str
    qty: int = Field(gt=0)


class InvoiceIn(BaseModel):
    customer_id: str
    items: list[ItemIn] = Field(min_length=1)


class InvoiceOut(BaseModel):
    id: int
    customer_id: str
    subtotal: Decimal
    igv: Decimal
    total: Decimal
    origin: str
    order_ref: str | None
    model_config = {"from_attributes": True}


@app.get("/health")
def health():
    return {"status": "ok", "service": "erp"}


@app.post("/products", response_model=ProductOut, status_code=201)
def create_product(p: ProductIn, db: Session = Depends(get_db)):
    if db.get(Product, p.sku):
        raise HTTPException(409, "SKU ya existe")
    obj = Product(**p.model_dump())
    db.add(obj)
    db.commit()
    return obj


@app.get("/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.scalars(select(Product).order_by(Product.sku)).all()


@app.post("/invoices", response_model=InvoiceOut, status_code=201)
def create_invoice(data: InvoiceIn, db: Session = Depends(get_db)):
    """Factura directa por API (síncrona)."""
    try:
        inv = create_invoice_core(db, data.customer_id, [i.model_dump() for i in data.items])
    except DomainError as e:
        db.rollback()
        raise HTTPException(e.status, e.msg)
    db.commit()
    db.refresh(inv)
    return inv


@app.get("/invoices", response_model=list[InvoiceOut])
def list_invoices(limit: int = 50, db: Session = Depends(get_db)):
    return db.scalars(select(Invoice).order_by(Invoice.id.desc()).limit(min(limit, 200))).all()


@app.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.get(Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "Factura no encontrada")
    return inv
