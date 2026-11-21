from fastapi.testclient import TestClient
from app.main import app
from app import auth
from tokens import h, enable

client = TestClient(app)


def test_erp_roles(monkeypatch):
    enable(monkeypatch, auth)
    assert client.get("/products").status_code == 200  # catálogo público
    assert client.post("/products", json={"sku": "S-1", "name": "x", "price": "1", "stock": 1},
                       headers=h("carla.cajera", ["cajero"])).status_code == 403
    assert client.get("/invoices", headers=h("gabriel.gerente", ["gerente"])).status_code == 200
    assert client.post("/invoices", json={"customer_id": "c", "items": [{"sku": "S-1", "qty": 1}]},
                       headers=h("gabriel.gerente", ["gerente"])).status_code == 403
