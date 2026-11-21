import os, tempfile
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/crm_test.db"
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
BASE = {"doc_type": "DNI", "doc_number": "12345678", "full_name": "Ana Pérez", "email": "ana@example.com"}


def test_health():
    assert client.get("/health").json()["service"] == "crm"


def test_create_then_duplicate_same_id():
    r1 = client.post("/customers", json=BASE)
    assert r1.status_code == 201
    r2 = client.post("/customers", json=BASE)
    assert r2.status_code == 200
    assert r1.json()["customer_id"] == r2.json()["customer_id"]


def test_duplicate_by_email_case_insensitive():
    r = client.post("/customers", json={**BASE, "doc_number": "87654321", "email": "ANA@Example.com"})
    assert r.status_code == 200
    assert r.json()["doc_number"] == "12345678"  # devuelve el cliente original


def test_duplicate_by_document_other_email():
    r = client.post("/customers", json={**BASE, "email": "otro@example.com"})
    assert r.status_code == 200


def test_invalid_document():
    r = client.post("/customers", json={**BASE, "doc_number": "123", "email": "x@example.com"})
    assert r.status_code == 422


def test_get_and_404():
    cid = client.post("/customers", json=BASE).json()["customer_id"]
    assert client.get(f"/customers/{cid}").status_code == 200
    assert client.get("/customers/no-existe").status_code == 404
