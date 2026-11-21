"""Escena 1 y 2 (parcial): cliente en CRM (con duplicado) -> factura en ERP.
Uso: python scripts/seed_and_demo.py [CRM_URL] [ERP_URL]"""
import sys
import httpx
from _auth import headers
from catalogo import asegurar_productos

CRM = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
ERP = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8002"
ADMIN = headers("ana.admin")

print("productos nuevos en el ERP:", asegurar_productos(ERP, ADMIN))

c1 = httpx.post(f"{CRM}/customers", json={"doc_type": "DNI", "doc_number": "45678912",
      "full_name": "María Quispe Huamán", "email": "maria.quispe@example.com"}, headers=ADMIN)
c2 = httpx.post(f"{CRM}/customers", json={"doc_type": "DNI", "doc_number": "45678912",
      "full_name": "MARIA QUISPE H.", "email": "MARIA.QUISPE@example.com"}, headers=ADMIN)  # duplicado a propósito
print("cliente 1:", c1.status_code, c1.json()["customer_id"])
print("cliente 2 (duplicado):", c2.status_code, c2.json()["customer_id"], "-> mismo ID:", c1.json()["customer_id"] == c2.json()["customer_id"])

inv = httpx.post(f"{ERP}/invoices", json={"customer_id": c1.json()["customer_id"],
      "items": [{"sku": "AUD-0401", "qty": 1}, {"sku": "ACC-0801", "qty": 2}]}, headers=ADMIN)
print("factura:", inv.status_code, inv.json())
