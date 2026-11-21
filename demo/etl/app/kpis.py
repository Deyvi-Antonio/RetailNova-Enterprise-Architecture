"""Indicadores del panel gerencial. Se calculan SOLO desde el Data Warehouse."""
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from .etl import engines

PERU = timezone(timedelta(hours=-5))


def _q(c, sql, **p):
    return [dict(r._mapping) for r in c.execute(text(sql), p)]


def _f(v):
    return float(v or 0)


def compute() -> dict:
    today = datetime.now(PERU).date()
    dk_today = today.year * 10000 + today.month * 100 + today.day
    d30 = today - timedelta(days=29)
    dk_30 = d30.year * 10000 + d30.month * 100 + d30.day
    with engines()["dw"].connect() as c:
        tot = _q(c, "SELECT COALESCE(SUM(amount_total),0) AS total, COUNT(DISTINCT invoice_id) AS facturas, "
                    "COUNT(DISTINCT CASE WHEN customer_id <> 'CONSUMIDOR_FINAL' THEN customer_id END) AS clientes, "
                    "COALESCE(SUM(qty),0) AS unidades FROM fact_sales")[0]
        hoy = _q(c, "SELECT COALESCE(SUM(amount_total),0) AS total, COUNT(DISTINCT invoice_id) AS facturas "
                    "FROM fact_sales WHERE date_key = :k", k=dk_today)[0]
        by_channel = _q(c, "SELECT d.description AS canal, d.channel AS code, COALESCE(SUM(f.amount_total),0) AS total "
                           "FROM dim_channel d LEFT JOIN fact_sales f ON f.channel = d.channel "
                           "GROUP BY d.description, d.channel ORDER BY total DESC")
        by_store = _q(c, "SELECT s.name AS tienda, COALESCE(SUM(f.amount_total),0) AS total, "
                         "COUNT(DISTINCT f.invoice_id) AS facturas FROM dim_store s "
                         "LEFT JOIN fact_sales f ON f.store_id = s.store_id GROUP BY s.name ORDER BY total DESC")
        by_cat = _q(c, "SELECT p.category AS categoria, SUM(f.amount_total) AS total, SUM(f.qty) AS unidades "
                       "FROM fact_sales f JOIN dim_product p ON p.sku = f.sku GROUP BY p.category ORDER BY total DESC")
        top = _q(c, "SELECT p.name AS producto, p.category AS categoria, SUM(f.qty) AS unidades, SUM(f.amount_total) AS total "
                    "FROM fact_sales f JOIN dim_product p ON p.sku = f.sku GROUP BY p.name, p.category "
                    "ORDER BY total DESC LIMIT 5")
        by_day = _q(c, "SELECT d.date AS fecha, d.weekday_name AS dia, SUM(f.amount_total) AS total FROM fact_sales f "
                       "JOIN dim_date d ON d.date_key = f.date_key WHERE f.date_key >= :k GROUP BY d.date, d.weekday_name "
                       "ORDER BY d.date", k=dk_30)
        stock = _q(c, "SELECT sku, name AS producto, category AS categoria, current_stock AS stock FROM dim_product "
                      "ORDER BY current_stock")
        orders = _q(c, "SELECT source, status, COUNT(*) AS n FROM fact_orders GROUP BY source, status")
        last = _q(c, "SELECT finished_at, status, rows_json, error FROM etl_runs ORDER BY id DESC LIMIT 1")
    facturas = int(tot["facturas"] or 0)
    web = {o["status"]: int(o["n"]) for o in orders if o["source"] == "ecommerce"}
    web_total = sum(web.values())
    days = {str(r["fecha"]): _f(r["total"]) for r in by_day}
    serie = []
    for i in range(30):
        d = d30 + timedelta(days=i)
        serie.append({"fecha": d.isoformat(), "fin_de_semana": d.weekday() >= 5, "total": days.get(d.isoformat(), 0.0)})
    run = last[0] if last else None
    return {
        "ventas_total": _f(tot["total"]), "facturas": facturas, "clientes": int(tot["clientes"] or 0),
        "unidades": int(tot["unidades"] or 0),
        "ticket_promedio": round(_f(tot["total"]) / facturas, 2) if facturas else 0,
        "ventas_hoy": _f(hoy["total"]), "facturas_hoy": int(hoy["facturas"] or 0),
        "por_canal": [{"canal": r["canal"], "code": r["code"], "total": _f(r["total"])} for r in by_channel],
        "por_tienda": [{"tienda": r["tienda"], "total": _f(r["total"]), "facturas": int(r["facturas"])} for r in by_store],
        "por_categoria": [{"categoria": r["categoria"], "total": _f(r["total"]), "unidades": int(r["unidades"])} for r in by_cat],
        "top_productos": [{"producto": r["producto"], "categoria": r["categoria"], "unidades": int(r["unidades"]),
                           "total": _f(r["total"])} for r in top],
        "por_dia": serie,
        "stock": [{"sku": r["sku"], "producto": r["producto"], "categoria": r["categoria"], "stock": int(r["stock"]),
                   "bajo": int(r["stock"]) <= 5} for r in stock],
        "pedidos_web": {"total": web_total, "por_estado": web,
                        "tasa_rechazo": round(100 * web.get("RECHAZADO", 0) / web_total, 1) if web_total else 0},
        "pos_en_cola": sum(int(o["n"]) for o in orders if o["source"] == "pos" and o["status"] == "EN_COLA"),
        "ultima_carga": None if not run else {"fecha": str(run["finished_at"]), "estado": run["status"],
                                              "filas": json.loads(run["rows_json"] or "{}"), "error": run["error"]},
    }
