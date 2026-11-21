"""El ERP escucha pedidos web (order.created) y ventas de tienda (sale.created)
y responde con invoice.created.<origen> u order.rejected.<origen>."""
import logging
from . import bus
from .db import SessionLocal
from .models import ProcessedEvent
from .service import create_invoice, DomainError

log = logging.getLogger("erp.events")
ORIGIN = {"order.created": "ecommerce", "sale.created": "pos"}


def handle(routing_key: str, event: dict) -> None:
    origin = ORIGIN.get(routing_key)
    if origin is None:
        return
    data = event["data"]
    with SessionLocal() as db:
        if db.get(ProcessedEvent, event["event_id"]):
            log.info("Evento duplicado ignorado: %s", event["event_id"])
            return
        try:
            inv = create_invoice(db, data["customer_id"], data["items"], origin=origin, order_ref=data["order_ref"],
                                 store_id=data.get("store_id"))
            payload = {"order_ref": data["order_ref"], "invoice_id": inv.id, "total": str(inv.total)}
            db.add(ProcessedEvent(event_id=event["event_id"]))
            db.commit()
            out = (f"invoice.created.{origin}", bus.make_event("invoice.created", "erp", payload))
        except DomainError as e:
            db.rollback()
            if e.status == 503:
                raise bus.TransientError(e.msg)  # el CRM volverá: reintentar
            db.add(ProcessedEvent(event_id=event["event_id"]))
            db.commit()
            out = (f"order.rejected.{origin}",
                   bus.make_event("order.rejected", "erp", {"order_ref": data["order_ref"], "reason": e.msg}))
    bus.publish(*out)
    log.info("%s -> %s", event["event_id"], out[0])
