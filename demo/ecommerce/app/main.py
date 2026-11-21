import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import bus, clients, outbox
from .db import Base, engine, get_db
from .models import Order

logging.basicConfig(level=logging.INFO)
Base.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app):
    if bus.URL:
        bus.start_consumer("ecommerce.respuestas", ["invoice.created.ecommerce", "order.rejected.ecommerce"],
                           outbox.handle_update)
        bus.start_loop(outbox.flush, 3, "ecommerce-outbox")
    yield

app = FastAPI(title="RetailNova E-commerce", version="0.2.0", lifespan=lifespan)


class CustomerIn(BaseModel):
    doc_type: str = "DNI"
    doc_number: str
    full_name: str
    email: EmailStr
    phone: str | None = None


class ItemIn(BaseModel):
    sku: str
    qty: int = Field(gt=0)


class OrderIn(BaseModel):
    customer: CustomerIn
    items: list[ItemIn] = Field(min_length=1)


def out(o: Order) -> dict:
    return {"id": o.id, "customer_id": o.customer_id, "items": json.loads(o.items_json), "status": o.status,
            "invoice_id": o.invoice_id, "total": o.total, "reason": o.reason, "created_at": o.created_at.isoformat()}


@app.get("/", response_class=HTMLResponse)
def store_page():
    return (Path(__file__).parent / "store.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {"status": "ok", "service": "ecommerce"}


@app.get("/catalog")
def catalog():
    return clients.catalog()


@app.post("/orders", status_code=201)
def create_order(data: OrderIn, db: Session = Depends(get_db)):
    try:
        customer_id = clients.upsert_customer(data.customer.model_dump())
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    o = Order(customer_id=customer_id, items_json=json.dumps([i.model_dump() for i in data.items]))
    db.add(o)
    db.commit()
    order_id = o.id
    if bus.URL:
        outbox.flush()  # intento inmediato; si falla, el bucle lo reintenta
    db.expire_all()
    return out(db.get(Order, order_id))


@app.get("/orders")
def list_orders(limit: int = 20, db: Session = Depends(get_db)):
    return [out(o) for o in db.scalars(select(Order).order_by(Order.created_at.desc()).limit(min(limit, 100)))]


@app.get("/orders/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db)):
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Pedido no encontrado")
    return out(o)
