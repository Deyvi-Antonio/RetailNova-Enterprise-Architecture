"""ETL: Extrae de las bases de cada sistema, Transforma y Carga en el DW.
Carga completa e idempotente: cada corrida reconstruye las tablas en una sola transacción."""
import json
import logging
import os
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from sqlalchemy import create_engine, text, insert, delete
from .dw import md, dim_date, dim_product, dim_customer, dim_channel, fact_sales, fact_orders, etl_runs, DIMS_AND_FACTS

log = logging.getLogger("etl")
PERU = timezone(timedelta(hours=-5))  # Perú no tiene horario de verano
IGV = Decimal("0.18")
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
CHANNELS = {"ecommerce": "Tienda online", "pos": "Tienda física (POS)", "api": "Venta directa (API ERP)"}


def _engine(var, default=""):
    url = os.getenv(var, default)
    return create_engine(url, pool_pre_ping=True) if url else None


SOURCES = {"erp": "ERP_DB_URL", "crm": "CRM_DB_URL", "ecommerce": "ECOM_DB_URL", "pos": "POS_DB_URL"}
_engines: dict = {}


def engines():
    if not _engines:
        for k, var in SOURCES.items():
            _engines[k] = _engine(var)
        _engines["dw"] = _engine("DW_DB_URL", "sqlite:///./dw_dev.db")
    return _engines


def reset_engines():
    _engines.clear()


def _dt(v) -> datetime:
    if isinstance(v, str):
        v = datetime.fromisoformat(v)
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    return v.astimezone(PERU)


def _date_key(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day


def _dec(v) -> Decimal:
    return Decimal(str(v))


def _rows(eng, sql):
    with eng.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql))]


def extract() -> dict:
    e = engines()
    return {
        "invoices": _rows(e["erp"], "SELECT i.id, i.customer_id, i.origin, i.order_ref, i.created_at, "
                                    "it.sku, it.qty, it.unit_price FROM invoices i "
                                    "JOIN invoice_items it ON it.invoice_id = i.id"),
        "products": _rows(e["erp"], "SELECT sku, name, price, stock FROM products"),
        "customers": _rows(e["crm"], "SELECT customer_id, doc_type, created_at FROM customers"),
        "orders": _rows(e["ecommerce"], "SELECT id, status, invoice_id, created_at FROM orders"),
        "sales": _rows(e["pos"], "SELECT id, store_id, status, invoice_id, created_at FROM sales"),
    }


def transform(src: dict) -> dict:
    dates: dict[int, date] = {}

    def dk(v):
        d = _dt(v).date()
        k = _date_key(d)
        dates[k] = d
        return k

    store_by_sale = {s["id"]: s["store_id"] for s in src["sales"]}
    sales = []
    for r in src["invoices"]:
        net = _dec(r["unit_price"]) * int(r["qty"])
        igv = (net * IGV).quantize(Decimal("0.01"))
        sales.append({"invoice_id": r["id"], "date_key": dk(r["created_at"]), "customer_id": r["customer_id"],
                      "sku": r["sku"], "channel": r["origin"],
                      "store_id": store_by_sale.get(r["order_ref"]) if r["origin"] == "pos" else None,
                      "qty": int(r["qty"]), "unit_price": _dec(r["unit_price"]),
                      "amount_net": net, "amount_igv": igv, "amount_total": net + igv})
    orders = ([{"order_ref": o["id"], "source": "ecommerce", "status": o["status"], "date_key": dk(o["created_at"]),
                "invoice_id": o["invoice_id"]} for o in src["orders"]] +
              [{"order_ref": s["id"], "source": "pos", "status": s["status"], "date_key": dk(s["created_at"]),
                "invoice_id": s["invoice_id"]} for s in src["sales"]])
    customers = [{"customer_id": c["customer_id"], "doc_type": c["doc_type"],
                  "registered_date_key": dk(c["created_at"])} for c in src["customers"]]
    products = [{"sku": p["sku"], "name": p["name"], "list_price": _dec(p["price"]), "current_stock": int(p["stock"])}
                for p in src["products"]]
    channels = [{"channel": k, "description": v} for k, v in CHANNELS.items()]
    dims_date = [{"date_key": k, "date": d, "year": d.year, "month": d.month, "day": d.day,
                  "month_name": MESES[d.month], "weekday_name": DIAS[d.weekday()]} for k, d in dates.items()]
    return {"dim_date": dims_date, "dim_product": products, "dim_customer": customers, "dim_channel": channels,
            "fact_sales": sales, "fact_orders": orders}


def load(data: dict) -> None:
    dw = engines()["dw"]
    with dw.begin() as c:  # todo o nada
        for t in DIMS_AND_FACTS:
            c.execute(delete(t))
        for t in reversed(DIMS_AND_FACTS):
            if data[t.name]:
                c.execute(insert(t), data[t.name])


def run() -> dict:
    dw = engines()["dw"]
    md.create_all(dw)
    started = datetime.now(timezone.utc)
    try:
        data = transform(extract())
        load(data)
        rows = {k: len(v) for k, v in data.items()}
        status, error = "OK", None
    except Exception as ex:
        log.warning("ETL falló: %s", ex)
        rows, status, error = {}, "ERROR", str(ex)[:500]
    with dw.begin() as c:
        c.execute(insert(etl_runs).values(started_at=started, finished_at=datetime.now(timezone.utc),
                                          status=status, rows_json=json.dumps(rows), error=error))
    return {"status": status, "rows": rows, "error": error}
