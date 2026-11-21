"""Patrón outbox: el pedido se guarda primero en la base del e-commerce y luego
se publica. Si RabbitMQ no está, queda pendiente y se reintenta solo."""
import json
import logging
from sqlalchemy import select, update
from . import bus
from .db import SessionLocal
from .models import Order

log = logging.getLogger("ecommerce.outbox")


def flush() -> int:
    sent = 0
    with SessionLocal() as db:
        pending = db.scalars(select(Order).where(Order.published.is_(False)).order_by(Order.created_at)).all()
        for o in pending:
            ev = bus.make_event("order.created", "ecommerce",
                                {"order_ref": o.id, "customer_id": o.customer_id, "items": json.loads(o.items_json)},
                                event_id=o.id)  # ID estable: si se reenvía, el ERP lo detecta como duplicado
            try:
                bus.publish("order.created", ev)
            except Exception as e:
                log.warning("No se pudo publicar (se reintentará): %s", e)
                break
            db.execute(update(Order).where(Order.id == o.id).values(published=True))
            db.execute(update(Order).where(Order.id == o.id, Order.status == "PENDIENTE").values(status="ENVIADO"))
            db.commit()
            sent += 1
    return sent


def handle_update(routing_key: str, event: dict) -> None:
    """Respuesta del ERP: factura creada o pedido rechazado."""
    d = event["data"]
    with SessionLocal() as db:
        if routing_key.startswith("invoice.created"):
            values = {"status": "CONFIRMADO", "invoice_id": d["invoice_id"], "total": d["total"], "published": True}
        else:
            values = {"status": "RECHAZADO", "reason": d["reason"], "published": True}
        db.execute(update(Order).where(Order.id == d["order_ref"]).values(**values))
        db.commit()
