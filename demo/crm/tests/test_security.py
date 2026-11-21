import os, tempfile
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/crm_sec.db")
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import auth
from tokens import h, enable, OTHER

client = TestClient(app)
NEW = {"doc_type": "DNI", "doc_number": "70000001", "full_name": "Rosa Díaz", "email": "rosa@example.com"}


@pytest.fixture(autouse=True)
def secured(monkeypatch):
    enable(monkeypatch, auth)


def test_no_token_401():
    assert client.get("/customers").status_code == 401


def test_service_account_can_register_customer():
    assert client.post("/customers", json=NEW, headers=h("service-account-retailnova-servicios", ["integracion"])).status_code in (200, 201)


def test_cashier_cannot_see_personal_data_and_is_audited():
    r = client.get("/customers", headers=h("carla.cajera", ["cajero"]))
    assert r.status_code == 403 and "cajero" in r.json()["detail"]
    log = client.get("/audit", headers=h("ana.admin", ["admin"])).json()
    assert log[0]["usuario"] == "carla.cajera" and log[0]["resultado"] == "DENEGADO"


def test_customer_service_can_list_and_is_audited():
    r = client.get("/customers", headers=h("sofia.atencion", ["atencion_cliente"]))
    assert r.status_code == 200 and any(c["email"] == "rosa@example.com" for c in r.json())
    log = client.get("/audit", headers=h("ana.admin", ["admin"])).json()
    assert log[0]["usuario"] == "sofia.atencion" and log[0]["accion"] == "LISTAR_CLIENTES" and log[0]["resultado"] == "PERMITIDO"


def test_only_admin_sees_audit():
    assert client.get("/audit", headers=h("sofia.atencion", ["atencion_cliente"])).status_code == 403


def test_expired_wrong_key_wrong_issuer_rejected():
    assert client.get("/customers", headers=h("x", ["admin"], exp_in=-10)).status_code == 401
    assert client.get("/customers", headers=h("x", ["admin"], key=OTHER)).status_code == 401
    assert client.get("/customers", headers=h("x", ["admin"], iss="http://evil/realms/retailnova")).status_code == 401


def test_me_and_console_page():
    assert client.get("/me", headers=h("gabriel.gerente", ["gerente"])).json()["roles"] == ["gerente"]
    assert "Registro de auditoría" in client.get("/").text and "Auth" in client.get("/static/auth.js").text
