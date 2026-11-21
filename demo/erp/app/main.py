from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import crm_client
from .db import Base, engine, get_db
from .models import Product, Invoice, InvoiceItem

app = FastAPI(title="RetailNova ERP", version="0.1.0")
Base.metadata.create_all(engine)
IGV = Decimal("0.18")  # IGV Perú


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
    return db.scalars(select(Product)).all()


@app.post("/invoices", response_model=InvoiceOut, status_code=201)
def create_invoice(data: InvoiceIn, db: Session = Depends(get_db)):
    """Factura: valida cliente en el CRM, descuenta stock y calcula IGV (todo en una transacción)."""
    try:
        if not crm_client.customer_exists(data.customer_id):
            raise HTTPException(404, "customer_id no existe en el CRM")
    except RuntimeError:
        raise HTTPException(503, "CRM no disponible")

    subtotal = Decimal("0")
    lines = []
    for it in data.items:
        prod = db.get(Product, it.sku, with_for_update=True)
        if not prod:
            raise HTTPException(404, f"SKU no existe: {it.sku}")
        if prod.stock < it.qty:
            raise HTTPException(409, f"Stock insuficiente para {it.sku} (disponible {prod.stock})")
        prod.stock -= it.qty
        subtotal += prod.price * it.qty
        lines.append(InvoiceItem(sku=it.sku, qty=it.qty, unit_price=prod.price))

    igv = (subtotal * IGV).quantize(Decimal("0.01"))
    inv = Invoice(customer_id=data.customer_id, subtotal=subtotal, igv=igv, total=subtotal + igv, items=lines)
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@app.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.get(Invoice, invoice_id)
    if not inv:
        raise HTTPException(404, "Factura no encontrada")
    return inv
