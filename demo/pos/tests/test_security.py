import os, tempfile
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/pos_sec.db")
from fastapi.testclient import TestClient
from app.main import app
from app import auth
from tokens import h, enable

client = TestClient(app)


def test_only_cashier_can_sell(monkeypatch):
    enable(monkeypatch, auth)
    sale = {"items": [{"sku": "POL-1", "qty": 1}]}
    assert client.post("/sales", json=sale).status_code == 401
    assert client.post("/sales", json=sale, headers=h("gabriel.gerente", ["gerente"])).status_code == 403
    assert client.post("/sales", json=sale, headers=h("carla.cajera", ["cajero"])).status_code == 201
    assert client.post("/network", json={"online": True}, headers=h("sofia.atencion", ["atencion_cliente"])).status_code == 403
