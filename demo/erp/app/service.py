"""Lógica de facturación, usada tanto por la API como por los eventos."""
from decimal import Decimal
from sqlalchemy.orm import Session
from . import crm_client
from .models import Product, Invoice, InvoiceItem

IGV = Decimal("0.18")  # IGV Perú
CONSUMIDOR_FINAL = "CONSUMIDOR_FINAL"  # venta en tienda sin cliente identificado


def amounts(gross: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """Como en una boleta peruana: el total parte del precio con IGV y de ahí se separa el IGV."""
    total = (gross * (1 + IGV)).quantize(Decimal("0.01"))
    subtotal = (total / (1 + IGV)).quantize(Decimal("0.01"))
    return subtotal, total - subtotal, total


class DomainError(Exception):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status, self.msg = status, msg


def create_invoice(db: Session, customer_id: str, items: list[dict],
                   origin: str = "api", order_ref: str | None = None, store_id: str | None = None) -> Invoice:
    """Valida el cliente en el CRM, descuenta stock y calcula IGV.
    No hace commit: el llamador confirma o revierte la transacción."""
    if customer_id != CONSUMIDOR_FINAL:
        try:
            if not crm_client.customer_exists(customer_id):
                raise DomainError(404, "customer_id no existe en el CRM")
        except RuntimeError:
            raise DomainError(503, "CRM no disponible")
    if not items:
        raise DomainError(422, "El pedido no tiene ítems")

    subtotal = Decimal("0")
    lines = []
    for it in items:
        sku, qty = it["sku"], int(it["qty"])
        if qty <= 0:
            raise DomainError(422, f"Cantidad inválida para {sku}")
        prod = db.get(Product, sku, with_for_update=True)
        if not prod:
            raise DomainError(404, f"SKU no existe: {sku}")
        if prod.stock < qty:
            raise DomainError(409, f"Stock insuficiente para {sku} (disponible {prod.stock})")
        prod.stock -= qty
        subtotal += prod.price * qty
        lines.append(InvoiceItem(sku=sku, qty=qty, unit_price=prod.price))

    subtotal, igv, total = amounts(subtotal)
    inv = Invoice(customer_id=customer_id, subtotal=subtotal, igv=igv, total=total,
                  items=lines, origin=origin, order_ref=order_ref, store_id=store_id)
    db.add(inv)
    db.flush()
    return inv
