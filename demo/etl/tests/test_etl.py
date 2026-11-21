"""Prueba el ETL con bases de origen de prueba (SQLite) que imitan las tablas reales."""
import os, tempfile
from decimal import Decimal
d = tempfile.mkdtemp()
URLS = {k: f"sqlite:///{d}/{k}.db" for k in ["erp", "crm", "ecom", "pos", "dw"]}
for k, var in [("erp", "ERP_DB_URL"), ("crm", "CRM_DB_URL"), ("ecom", "ECOM_DB_URL"), ("pos", "POS_DB_URL"), ("dw", "DW_DB_URL")]:
    os.environ[var] = URLS[k]
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient
from app.main import app
from app import etl

client = TestClient(app)


def sql(db, *stmts):
    with create_engine(URLS[db]).begin() as c:
        for s in stmts:
            c.execute(text(s))


def setup_module():
    sql("erp", "CREATE TABLE products (sku TEXT, name TEXT, price NUMERIC, stock INT)",
        "CREATE TABLE invoices (id INT, customer_id TEXT, subtotal NUMERIC, igv NUMERIC, total NUMERIC, origin TEXT, order_ref TEXT, created_at TIMESTAMP)",
        "CREATE TABLE invoice_items (id INT, invoice_id INT, sku TEXT, qty INT, unit_price NUMERIC)",
        "INSERT INTO products VALUES ('ZAP-1','Zapatilla',100.00,3),('POL-1','Polo',40.00,50)",
        # factura web 1 (03:00 UTC = 22:00 del día anterior en Lima) y factura de tienda 2
        "INSERT INTO invoices VALUES (1,'cli-1',200,36,236,'ecommerce','ped-1','2026-11-21 03:00:00'),"
        "(2,'CONSUMIDOR_FINAL',80,14.4,94.4,'pos','ven-1','2026-11-21 15:00:00')",
        "INSERT INTO invoice_items VALUES (1,1,'ZAP-1',2,100.00),(2,2,'POL-1',2,40.00)")
    sql("crm", "CREATE TABLE customers (customer_id TEXT, doc_type TEXT, doc_number TEXT, full_name TEXT, email TEXT, created_at TIMESTAMP)",
        "INSERT INTO customers VALUES ('cli-1','DNI','45678912','María Quispe','maria@example.com','2026-11-20 10:00:00')")
    sql("ecom", "CREATE TABLE orders (id TEXT, customer_id TEXT, status TEXT, invoice_id INT, created_at TIMESTAMP)",
        "INSERT INTO orders VALUES ('ped-1','cli-1','CONFIRMADO',1,'2026-11-21 03:00:00'),('ped-2','cli-1','RECHAZADO',NULL,'2026-11-21 03:05:00')")
    sql("pos", "CREATE TABLE sales (id TEXT, store_id TEXT, status TEXT, invoice_id INT, created_at TIMESTAMP)",
        "INSERT INTO sales VALUES ('ven-1','TIENDA-01','FACTURADO',2,'2026-11-21 15:00:00'),('ven-2','TIENDA-01','EN_COLA',NULL,'2026-11-21 16:00:00')")


def test_run_ok_and_counts():
    r = client.post("/api/run").json()
    assert r["status"] == "OK", r
    assert r["rows"]["fact_sales"] == 2 and r["rows"]["fact_orders"] == 4 and r["rows"]["dim_customer"] == 1


def test_kpis_values():
    k = client.get("/api/kpis").json()
    assert k["ventas_total"] == 330.4 and k["facturas"] == 2 and k["clientes"] == 1 and k["ticket_promedio"] == 165.2
    canales = {c["canal"]: c["total"] for c in k["por_canal"]}
    assert canales["Tienda online"] == 236.0 and canales["Tienda física (POS)"] == 94.4
    assert k["pedidos_web"]["tasa_rechazo"] == 50.0 and k["pos_en_cola"] == 1
    assert [s for s in k["stock"] if s["sku"] == "ZAP-1"][0]["bajo"] is True
    assert k["ultima_carga"]["estado"] == "OK"


def test_peru_timezone_date_key():
    k = client.get("/api/kpis").json()
    assert {d["fecha"] for d in k["por_dia"]} == {"2026-11-20", "2026-11-21"}  # 03:00 UTC cae el 20 en Lima


def test_no_personal_data_in_dw():
    with create_engine(URLS["dw"]).connect() as c:
        cols = [r[1] for r in c.execute(text("PRAGMA table_info(dim_customer)"))]
        dump = str([tuple(r) for r in c.execute(text("SELECT * FROM dim_customer"))])
    assert "email" not in cols and "full_name" not in cols and "doc_number" not in cols
    assert "María" not in dump and "45678912" not in dump


def test_rerun_is_idempotent():
    client.post("/api/run")
    assert client.get("/api/kpis").json()["facturas"] == 2


def test_failure_is_logged_not_crash():
    sql("pos", "DROP TABLE sales")
    r = client.post("/api/run").json()
    assert r["status"] == "ERROR"
    k = client.get("/api/kpis").json()
    assert k["facturas"] == 2 and k["ultima_carga"]["estado"] == "ERROR"  # los datos anteriores se conservan


def test_dashboard_page():
    assert "Panel gerencial" in client.get("/").text
