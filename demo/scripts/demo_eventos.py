"""Escenas 2 y 3: pedido web por eventos y venta en tienda sin red.
Uso (con los contenedores arriba): python scripts/demo_eventos.py"""
import sys
import time
import httpx
from _auth import headers

ERP, ECOM, POS = "http://localhost:8002", "http://localhost:8003", "http://localhost:8004"
ADMIN, CAJERA = headers("ana.admin"), headers("carla.cajera")


def wait(url, ok_states, timeout=20, h=None):
    for _ in range(timeout * 2):
        d = httpx.get(url, headers=h or {}).json()
        if d["status"] in ok_states:
            return d
        time.sleep(0.5)
    return d


def stock():
    return {p["sku"]: p["stock"] for p in httpx.get(f"{ERP}/products").json()}


for p in [("ZAP-1", "Zapatilla urbana", "129.90", 20), ("POL-1", "Polo básico", "39.90", 50)]:
    httpx.post(f"{ERP}/products", json={"sku": p[0], "name": p[1], "price": p[2], "stock": p[3]}, headers=ADMIN)
print("Stock inicial en el ERP:", stock())

print("\n== Escena 2: compra en la tienda online -> evento -> ERP ==")
o = httpx.post(f"{ECOM}/orders", json={"customer": {"doc_number": "45678912", "full_name": "María Quispe",
               "email": "maria@example.com"}, "items": [{"sku": "ZAP-1", "qty": 1}]}).json()
print("Pedido creado:", o["id"][:8], "estado:", o["status"], "cliente CRM:", o["customer_id"][:8])
o = wait(f"{ECOM}/orders/{o['id']}", {"CONFIRMADO", "RECHAZADO"})
print("Respuesta del ERP:", o["status"], "factura", o["invoice_id"], "total S/", o["total"])

bad = httpx.post(f"{ECOM}/orders", json={"customer": {"doc_number": "45678912", "full_name": "María Quispe",
                 "email": "maria@example.com"}, "items": [{"sku": "ZAP-1", "qty": 9999}]}).json()
bad = wait(f"{ECOM}/orders/{bad['id']}", {"CONFIRMADO", "RECHAZADO"})
print("Pedido sin stock:", bad["status"], "-", bad["reason"])

print("\n== Escena 3: tienda sin red -> cola local -> sincroniza al volver ==")
httpx.post(f"{POS}/network", json={"online": False}, headers=CAJERA)
s = httpx.post(f"{POS}/sales", json={"items": [{"sku": "POL-1", "qty": 2}]}, headers=CAJERA).json()
print("Venta registrada sin red:", s["id"][:8], "estado:", s["status"])
time.sleep(4)
print("4 s después, sigue:", httpx.get(f"{POS}/sales/{s['id']}", headers=CAJERA).json()["status"], "(no se perdió, espera la red)")
r = httpx.post(f"{POS}/network", json={"online": True}, headers=CAJERA).json()
print("Red restablecida. Ventas sincronizadas:", r["sincronizadas"])
s = wait(f"{POS}/sales/{s['id']}", {"FACTURADO", "RECHAZADO"}, h=CAJERA)
print("Venta de tienda:", s["status"], "factura", s["invoice_id"], "total S/", s["total"])

print("\nStock final en el ERP:", stock())
ok = o["status"] == "CONFIRMADO" and bad["status"] == "RECHAZADO" and s["status"] == "FACTURADO"
print("\nRESULTADO:", "OK" if ok else "REVISAR")
sys.exit(0 if ok else 1)
