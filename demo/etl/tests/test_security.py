from fastapi.testclient import TestClient
from app.main import app
from app import auth
from tokens import h, enable

client = TestClient(app)


def test_only_management_sees_kpis(monkeypatch):
    enable(monkeypatch, auth)
    assert client.get("/api/kpis").status_code == 401
    assert client.get("/api/kpis", headers=h("carla.cajera", ["cajero"])).status_code == 403
    assert client.get("/api/kpis", headers=h("gabriel.gerente", ["gerente"])).status_code == 200
