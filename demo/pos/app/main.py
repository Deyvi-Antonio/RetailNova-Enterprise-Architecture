import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import auth, bus, network, outbox
from .auth import require, User
from .db import Base, engine, get_db
from .models import Sale

logging.basicConfig(level=logging.INFO)
Base.metadata.create_all(engine)


@asynccontextmanager
async def lifespan(app):
    if bus.URL:
        bus.start_consumer("pos.respuestas", ["invoice.created.pos", "order.rejected.pos"], outbox.handle_update)
        bus.start_loop(outbox.flush, 3, "pos-outbox")
    yield

app = FastAPI(title="RetailNova POS (tienda)", version="0.4.0", lifespan=lifespan)


class ItemIn(BaseModel):
    sku: str
    qty: int = Field(gt=0)


class SaleIn(BaseModel):
    items: list[ItemIn] = Field(min_length=1)
    customer_id: str = "CONSUMIDOR_FINAL"
    store_id: str = "TIENDA-01"


class NetworkIn(BaseModel):
    online: bool


def out(s: Sale) -> dict:
    return {"id": s.id, "store_id": s.store_id, "customer_id": s.customer_id, "items": json.loads(s.items_json),
            "status": s.status, "invoice_id": s.invoice_id, "total": s.total, "reason": s.reason,
            "created_at": s.created_at.isoformat()}


@app.get("/", response_class=HTMLResponse)
def pos_page():
    return (Path(__file__).parent / "pos.html").read_text(encoding="utf-8")


@app.get("/static/auth.js")
def auth_js():
    return Response((Path(__file__).parent / "web_auth.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/health")
def health():
    return {"status": "ok", "service": "pos", "online": network.online}


@app.get("/catalog")
def catalog():
    return network.catalog()


@app.get("/network")
def get_network():
    return {"online": network.online}


@app.post("/network")
def set_network(data: NetworkIn, _u=Depends(require("cajero"))):
    """Simula la caída o el regreso de la red de la tienda."""
    network.online = data.online
    sent = outbox.flush() if (data.online and bus.URL) else 0
    return {"online": network.online, "sincronizadas": sent}


@app.post("/sales", status_code=201)
def create_sale(data: SaleIn, db: Session = Depends(get_db), user: User = Depends(require("cajero"))):
    s = Sale(items_json=json.dumps([i.model_dump() for i in data.items]),
             customer_id=data.customer_id, store_id=data.store_id)
    db.add(s)
    db.commit()  # la venta queda registrada en la tienda pase lo que pase
    sale_id = s.id
    if bus.URL:
        outbox.flush()
    db.expire_all()
    return out(db.get(Sale, sale_id))


@app.get("/sales")
def list_sales(limit: int = 20, db: Session = Depends(get_db), _u=Depends(require("cajero", "gerente"))):
    return [out(s) for s in db.scalars(select(Sale).order_by(Sale.created_at.desc()).limit(min(limit, 100)))]


@app.get("/sales/{sale_id}")
def get_sale(sale_id: str, db: Session = Depends(get_db), _u=Depends(require("cajero", "gerente"))):
    s = db.get(Sale, sale_id)
    if not s:
        raise HTTPException(404, "Venta no encontrada")
    return out(s)
