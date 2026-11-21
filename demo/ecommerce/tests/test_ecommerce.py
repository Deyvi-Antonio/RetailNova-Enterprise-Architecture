import os, tempfile
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/ecom_test.db"
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import bus, clients, outbox

client = TestClient(app)
ORDER = {"customer": {"doc_number": "45678912", "full_name": "María Quispe", "email": "maria@example.com"},
         "items": [{"sku": "ZAP-1", "qty": 2}]}


@pytest.fixture(autouse=True)
def crm(monkeypatch):
    monkeypatch.setattr(clients, "upsert_customer", lambda p: "cli-123")


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(bus, "publish", lambda rk, ev: out.append((rk, ev)))
    return out


def test_order_saved_pending_with_crm_id():
    r = client.post("/orders", json=ORDER)
    assert r.status_code == 201
    assert r.json()["status"] == "PENDIENTE" and r.json()["customer_id"] == "cli-123"


def test_flush_publishes_with_stable_event_id(sent):
    oid = client.post("/orders", json=ORDER).json()["id"]
    assert outbox.flush() >= 1
    ev = [e for rk, e in sent if e["data"]["order_ref"] == oid][0]
    assert ev["event_id"] == oid and ev["type"] == "order.created"
    assert client.get(f"/orders/{oid}").json()["status"] == "ENVIADO"
    assert outbox.flush() == 0  # ya no queda nada pendiente


def test_broker_down_keeps_order_pending(monkeypatch):
    def boom(rk, ev):
        raise ConnectionError("rabbitmq caído")
    monkeypatch.setattr(bus, "publish", boom)
    oid = client.post("/orders", json=ORDER).json()["id"]
    assert outbox.flush() == 0
    assert client.get(f"/orders/{oid}").json()["status"] == "PENDIENTE"


def test_erp_confirms_and_rejects():
    a = client.post("/orders", json=ORDER).json()["id"]
    b = client.post("/orders", json=ORDER).json()["id"]
    outbox.handle_update("invoice.created.ecommerce", bus.make_event("invoice.created", "erp",
                         {"order_ref": a, "invoice_id": 7, "total": "236.00"}))
    outbox.handle_update("order.rejected.ecommerce", bus.make_event("order.rejected", "erp",
                         {"order_ref": b, "reason": "Stock insuficiente"}))
    ra, rb = client.get(f"/orders/{a}").json(), client.get(f"/orders/{b}").json()
    assert ra["status"] == "CONFIRMADO" and ra["invoice_id"] == 7 and ra["total"] == "236.00"
    assert rb["status"] == "RECHAZADO" and "Stock" in rb["reason"]


def test_confirmed_not_overwritten_by_late_flush(sent):
    oid = client.post("/orders", json=ORDER).json()["id"]
    outbox.handle_update("invoice.created.ecommerce", bus.make_event("invoice.created", "erp",
                         {"order_ref": oid, "invoice_id": 9, "total": "1.00"}))
    outbox.flush()
    assert client.get(f"/orders/{oid}").json()["status"] == "CONFIRMADO"


def test_crm_down_503(monkeypatch):
    def boom(p):
        raise RuntimeError("CRM no disponible")
    monkeypatch.setattr(clients, "upsert_customer", boom)
    assert client.post("/orders", json=ORDER).status_code == 503


def test_store_page_and_validation():
    assert "Tienda online" in client.get("/").text
    assert client.post("/orders", json={**ORDER, "items": []}).status_code == 422
