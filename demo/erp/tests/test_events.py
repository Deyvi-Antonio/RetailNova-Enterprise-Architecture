import os, tempfile
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/erp_ev.db")
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import bus, events, crm_client

client = TestClient(app)


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(bus, "publish", lambda rk, ev: out.append((rk, ev)))
    return out


def stock(sku):
    return [p for p in client.get("/products").json() if p["sku"] == sku][0]["stock"]


def setup_module():
    client.post("/products", json={"sku": "EV-1", "name": "Mochila", "price": "50.00", "stock": 10})


def order(eid, qty=2, cid="cli-1", ref="ped-1"):
    return bus.make_event("order.created", "ecommerce",
                          {"order_ref": ref, "customer_id": cid, "items": [{"sku": "EV-1", "qty": qty}]}, event_id=eid)


def test_web_order_creates_invoice_and_notifies(sent):
    before = stock("EV-1")
    events.handle("order.created", order("e-1"))
    assert stock("EV-1") == before - 2
    rk, ev = sent[0]
    assert rk == "invoice.created.ecommerce" and ev["data"]["order_ref"] == "ped-1" and ev["data"]["total"] == "118.00"


def test_duplicate_event_is_ignored(sent):
    before = stock("EV-1")
    events.handle("order.created", order("e-1"))  # mismo event_id que el test anterior
    assert stock("EV-1") == before and sent == []


def test_insufficient_stock_rejected_without_change(sent):
    before = stock("EV-1")
    ev = bus.make_event("sale.created", "pos", {"order_ref": "v-9", "customer_id": "CONSUMIDOR_FINAL",
                                                 "items": [{"sku": "EV-1", "qty": 999}]})
    events.handle("sale.created", ev)
    assert stock("EV-1") == before
    assert sent[0][0] == "order.rejected.pos" and "Stock insuficiente" in sent[0][1]["data"]["reason"]


def test_pos_consumidor_final_skips_crm(sent, monkeypatch):
    monkeypatch.setattr(crm_client, "customer_exists", lambda cid: False)
    ev = bus.make_event("sale.created", "pos", {"order_ref": "v-1", "customer_id": "CONSUMIDOR_FINAL",
                                                 "items": [{"sku": "EV-1", "qty": 1}]})
    events.handle("sale.created", ev)
    assert sent[0][0] == "invoice.created.pos"


def test_crm_down_is_transient_and_not_marked(sent, monkeypatch):
    def boom(cid):
        raise RuntimeError("down")
    monkeypatch.setattr(crm_client, "customer_exists", boom)
    with pytest.raises(bus.TransientError):
        events.handle("order.created", order("e-crm"))
    monkeypatch.setattr(crm_client, "customer_exists", lambda cid: True)
    events.handle("order.created", order("e-crm", ref="ped-crm"))  # al reintentar sí se procesa
    assert sent[-1][0] == "invoice.created.ecommerce"


def test_invoices_list_shows_origin(sent):
    origins = {i["origin"] for i in client.get("/invoices").json()}
    assert "ecommerce" in origins and "pos" in origins
