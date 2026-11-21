import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import auth, bus, events
from .auth import require
from .db import Base, engine, get_db
from .models import Product, Invoice, InvoiceItem
from .service import create_invoice as create_invoice_core, DomainError, amounts

logging.basicConfig(level=logging.INFO)
Base.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app):
    if bus.URL:
        bus.start_consumer("erp.ventas", ["order.created", "sale.created"], events.handle)
    yield

# Nombre comercial del ERP: se cambia en un solo lugar (variable ERP_BRAND)
BRAND = os.getenv("ERP_BRAND", "SAP 2")
TAGLINE = os.getenv("ERP_TAGLINE", "Sistema de Administración de Productos")

app = FastAPI(title=f"{BRAND} · ERP de RetailNova", version="0.5.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.add_middleware(CORSMiddleware, allow_origins=[f"http://localhost:{p}" for p in range(8001, 8006)],
                   allow_methods=["GET"], allow_headers=["*"])


class ProductIn(BaseModel):
    sku: str = Field(min_length=1, max_length=40)
    name: str
    category: str = "General"
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
    store_id: str | None = None
    created_at: datetime | None = None
    model_config = {"from_attributes": True}


class HistItem(BaseModel):
    sku: str
    qty: int = Field(gt=0)


class HistInvoice(BaseModel):
    customer_id: str
    origin: str = Field(pattern="^(ecommerce|pos|api)$")
    store_id: str | None = None
    created_at: datetime
    items: list[HistItem] = Field(min_length=1)


@app.get("/", response_class=HTMLResponse)
def erp_page():
    return (Path(__file__).parent / "erp.html").read_text(encoding="utf-8")


@app.get("/brand")
def brand():
    return {"name": BRAND, "tagline": TAGLINE}


@app.get("/health")
def health():
    return {"status": "ok", "service": "erp"}


@app.post("/products", response_model=ProductOut, status_code=201)
def create_product(p: ProductIn, db: Session = Depends(get_db), _u=Depends(require("gerente"))):
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
def create_invoice(data: InvoiceIn, db: Session = Depends(get_db), _u=Depends(require("integracion"))):
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
def list_invoices(limit: int = 50, db: Session = Depends(get_db), _u=Depends(require("gerente"))):
    return db.scalars(select(Invoice).order_by(Invoice.id.desc()).limit(min(limit, 200))).all()


@app.post("/admin/migracion", status_code=201)
def load_history(rows: list[HistInvoice], force: bool = False, db: Session = Depends(get_db), _u=Depends(require("admin"))):
    """Carga inicial de ventas históricas (migración desde los sistemas anteriores).
    No descuenta stock: el stock actual ya refleja esas ventas."""
    if not force and db.scalar(select(Invoice.id).where(Invoice.migrated.is_(True)).limit(1)):
        raise HTTPException(409, "La carga histórica ya se realizó")
    prices = {p.sku: p.price for p in db.scalars(select(Product))}
    n = 0
    for r in rows:
        lines, subtotal = [], Decimal("0")
        for it in r.items:
            if it.sku not in prices:
                raise HTTPException(404, f"SKU no existe: {it.sku}")
            subtotal += prices[it.sku] * it.qty
            lines.append(InvoiceItem(sku=it.sku, qty=it.qty, unit_price=prices[it.sku]))
        subtotal, igv, total = amounts(subtotal)
        db.add(Invoice(customer_id=r.customer_id, subtotal=subtotal, igv=igv, total=total, items=lines,
                       origin=r.origin, store_id=r.store_id, created_at=r.created_at, migrated=True))
        n += 1
    db.commit()
    return {"facturas_cargadas": n}


@app.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db), _u=Depends(require("gerente"))):
    inv = db.get(Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "Factura no encontrada")
    return inv
