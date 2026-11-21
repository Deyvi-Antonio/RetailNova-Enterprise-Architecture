import os, tempfile
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/erp_test.db"
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app import crm_client

client = TestClient(app)


def seed():
    client.post("/products", json={"sku": "ZAP-1", "name": "Zapatilla", "price": "100.00", "stock": 5})


def test_health():
    assert client.get("/health").json()["service"] == "erp"


def test_invoice_discounts_stock_and_igv():
    seed()
    r = client.post("/invoices", json={"customer_id": "c-1", "items": [{"sku": "ZAP-1", "qty": 2}]})
    assert r.status_code == 201
    body = r.json()
    assert Decimal(body["subtotal"]) == Decimal("200.00")
    assert Decimal(body["igv"]) == Decimal("36.00")
    assert Decimal(body["total"]) == Decimal("236.00")
    stock = [p for p in client.get("/products").json() if p["sku"] == "ZAP-1"][0]["stock"]
    assert stock == 3


def test_insufficient_stock_409_and_no_change():
    seed()
    before = [p for p in client.get("/products").json() if p["sku"] == "ZAP-1"][0]["stock"]
    r = client.post("/invoices", json={"customer_id": "c-1", "items": [{"sku": "ZAP-1", "qty": 999}]})
    assert r.status_code == 409
    after = [p for p in client.get("/products").json() if p["sku"] == "ZAP-1"][0]["stock"]
    assert before == after


def test_unknown_sku_404():
    r = client.post("/invoices", json={"customer_id": "c-1", "items": [{"sku": "NOPE", "qty": 1}]})
    assert r.status_code == 404


def test_unknown_customer_rejected(monkeypatch):
    monkeypatch.setattr(crm_client, "customer_exists", lambda cid: False)
    r = client.post("/invoices", json={"customer_id": "fantasma", "items": [{"sku": "ZAP-1", "qty": 1}]})
    assert r.status_code == 404


def test_crm_down_503(monkeypatch):
    def boom(cid):
        raise RuntimeError("down")
    monkeypatch.setattr(crm_client, "customer_exists", boom)
    r = client.post("/invoices", json={"customer_id": "c-1", "items": [{"sku": "ZAP-1", "qty": 1}]})
    assert r.status_code == 503


def test_duplicate_sku_409():
    seed()
    assert client.post("/products", json={"sku": "ZAP-1", "name": "x", "price": "1", "stock": 1}).status_code == 409
