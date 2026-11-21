"""Indicadores del panel gerencial. Se calculan SOLO desde el Data Warehouse."""
import json
from sqlalchemy import text
from .etl import engines


def _q(c, sql):
    return [dict(r._mapping) for r in c.execute(text(sql))]


def _f(v):
    return float(v or 0)


def compute() -> dict:
    with engines()["dw"].connect() as c:
        tot = _q(c, "SELECT COALESCE(SUM(amount_total),0) AS total, COUNT(DISTINCT invoice_id) AS facturas, "
                    "COUNT(DISTINCT CASE WHEN customer_id <> 'CONSUMIDOR_FINAL' THEN customer_id END) AS clientes, COALESCE(SUM(qty),0) AS unidades FROM fact_sales")[0]
        by_channel = _q(c, "SELECT d.description AS canal, COALESCE(SUM(f.amount_total),0) AS total, "
                           "COUNT(DISTINCT f.invoice_id) AS facturas FROM dim_channel d "
                           "LEFT JOIN fact_sales f ON f.channel = d.channel GROUP BY d.description ORDER BY total DESC")
        top = _q(c, "SELECT p.name AS producto, SUM(f.qty) AS unidades, SUM(f.amount_total) AS total "
                    "FROM fact_sales f JOIN dim_product p ON p.sku = f.sku GROUP BY p.name ORDER BY unidades DESC")
        by_day = _q(c, "SELECT d.date AS fecha, SUM(f.amount_total) AS total FROM fact_sales f "
                       "JOIN dim_date d ON d.date_key = f.date_key GROUP BY d.date ORDER BY d.date")
        stock = _q(c, "SELECT sku, name AS producto, current_stock AS stock FROM dim_product ORDER BY current_stock")
        orders = _q(c, "SELECT source, status, COUNT(*) AS n FROM fact_orders GROUP BY source, status")
        last = _q(c, "SELECT started_at, finished_at, status, rows_json, error FROM etl_runs ORDER BY id DESC LIMIT 1")
    facturas = int(tot["facturas"] or 0)
    web = {o["status"]: int(o["n"]) for o in orders if o["source"] == "ecommerce"}
    web_total = sum(web.values())
    run = last[0] if last else None
    return {
        "ventas_total": _f(tot["total"]), "facturas": facturas, "clientes": int(tot["clientes"] or 0),
        "unidades": int(tot["unidades"] or 0),
        "ticket_promedio": round(_f(tot["total"]) / facturas, 2) if facturas else 0,
        "por_canal": [{"canal": r["canal"], "total": _f(r["total"]), "facturas": int(r["facturas"])} for r in by_channel],
        "top_productos": [{"producto": r["producto"], "unidades": int(r["unidades"]), "total": _f(r["total"])} for r in top],
        "por_dia": [{"fecha": str(r["fecha"]), "total": _f(r["total"])} for r in by_day],
        "stock": [{"sku": r["sku"], "producto": r["producto"], "stock": int(r["stock"]), "bajo": int(r["stock"]) < 5}
                  for r in stock],
        "pedidos_web": {"total": web_total, "por_estado": web,
                        "tasa_rechazo": round(100 * web.get("RECHAZADO", 0) / web_total, 1) if web_total else 0},
        "pos_en_cola": sum(int(o["n"]) for o in orders if o["source"] == "pos" and o["status"] == "EN_COLA"),
        "ultima_carga": None if not run else {
            "fecha": str(run["finished_at"]), "estado": run["status"],
            "filas": json.loads(run["rows_json"] or "{}"), "error": run["error"]},
    }
