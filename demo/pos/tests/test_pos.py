import os, tempfile
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/pos_test.db"
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import bus, network, outbox

client = TestClient(app)
SALE = {"items": [{"sku": "POL-1", "qty": 1}]}


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(bus, "publish", lambda rk, ev: out.append((rk, ev)))
    network.online = True
    yield out
    network.online = True


def test_offline_sale_is_saved_and_queued(sent):
    client.post("/network", json={"online": False})
    r = client.post("/sales", json=SALE)
    assert r.status_code == 201 and r.json()["status"] == "EN_COLA"
    assert outbox.flush() == 0 and sent == []  # sin red no se envía nada


def test_back_online_syncs_queue(sent):
    client.post("/network", json={"online": False})
    ids = [client.post("/sales", json=SALE).json()["id"] for _ in range(2)]
    client.post("/network", json={"online": True})
    outbox.flush()
    published = {e["event_id"] for rk, e in sent if rk == "sale.created"}
    assert set(ids) <= published
    assert all(client.get(f"/sales/{i}").json()["status"] == "ENVIADO" for i in ids)


def test_erp_invoice_marks_facturado(sent):
    sid = client.post("/sales", json=SALE).json()["id"]
    outbox.handle_update("invoice.created.pos", bus.make_event("invoice.created", "erp",
                         {"order_ref": sid, "invoice_id": 3, "total": "47.08"}))
    s = client.get(f"/sales/{sid}").json()
    assert s["status"] == "FACTURADO" and s["invoice_id"] == 3


def test_default_customer_and_network_endpoint(sent):
    s = client.post("/sales", json=SALE).json()
    assert s["customer_id"] == "CONSUMIDOR_FINAL" and s["store_id"] == "TIENDA-01"
    assert client.get("/network").json() == {"online": True}
    assert "Caja de tienda" in client.get("/").text
