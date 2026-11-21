"""Cola local de la tienda: las ventas sin enviar se sincronizan cuando vuelve la red."""
import json
import logging
from sqlalchemy import select, update
from . import bus, network
from .db import SessionLocal
from .models import Sale

log = logging.getLogger("pos.outbox")


def flush() -> int:
    if not network.online:
        return 0
    sent = 0
    with SessionLocal() as db:
        pending = db.scalars(select(Sale).where(Sale.published.is_(False)).order_by(Sale.created_at)).all()
        for s in pending:
            ev = bus.make_event("sale.created", "pos",
                                {"order_ref": s.id, "store_id": s.store_id, "customer_id": s.customer_id,
                                 "items": json.loads(s.items_json)}, event_id=s.id)
            try:
                bus.publish("sale.created", ev)
            except Exception as e:
                log.warning("Sin conexión con la sede (se reintentará): %s", e)
                break
            db.execute(update(Sale).where(Sale.id == s.id).values(published=True))
            db.execute(update(Sale).where(Sale.id == s.id, Sale.status == "EN_COLA").values(status="ENVIADO"))
            db.commit()
            sent += 1
    return sent


def handle_update(routing_key: str, event: dict) -> None:
    d = event["data"]
    with SessionLocal() as db:
        if routing_key.startswith("invoice.created"):
            values = {"status": "FACTURADO", "invoice_id": d["invoice_id"], "total": d["total"], "published": True}
        else:
            values = {"status": "RECHAZADO", "reason": d["reason"], "published": True}
        db.execute(update(Sale).where(Sale.id == d["order_ref"]).values(**values))
        db.commit()
