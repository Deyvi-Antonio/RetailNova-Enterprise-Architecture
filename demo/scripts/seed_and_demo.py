"""Escena 1 y 2 (parcial): cliente en CRM (con duplicado) -> factura en ERP.
Uso: python scripts/seed_and_demo.py [CRM_URL] [ERP_URL]"""
import sys
import httpx
from _auth import headers

CRM = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
ERP = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8002"
ADMIN = headers("ana.admin")

# Datos sintéticos
for p in [("ZAP-1", "Zapatilla urbana", "129.90", 20), ("POL-1", "Polo básico", "39.90", 50)]:
    r = httpx.post(f"{ERP}/products", json={"sku": p[0], "name": p[1], "price": p[2], "stock": p[3]}, headers=ADMIN)
    print("producto", p[0], r.status_code)

c1 = httpx.post(f"{CRM}/customers", json={"doc_type": "DNI", "doc_number": "45678912",
      "full_name": "María Quispe", "email": "maria@example.com"}, headers=ADMIN)
c2 = httpx.post(f"{CRM}/customers", json={"doc_type": "DNI", "doc_number": "45678912",
      "full_name": "Maria Quispe R.", "email": "MARIA@example.com"}, headers=ADMIN)  # duplicado a propósito
print("cliente 1:", c1.status_code, c1.json()["customer_id"])
print("cliente 2 (duplicado):", c2.status_code, c2.json()["customer_id"], "-> mismo ID:", c1.json()["customer_id"] == c2.json()["customer_id"])

inv = httpx.post(f"{ERP}/invoices", json={"customer_id": c1.json()["customer_id"],
      "items": [{"sku": "ZAP-1", "qty": 2}, {"sku": "POL-1", "qty": 3}]}, headers=ADMIN)
print("factura:", inv.status_code, inv.json())
