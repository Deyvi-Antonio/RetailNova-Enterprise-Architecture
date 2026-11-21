"""Carga los datos de RetailNova: catálogo, clientes (con duplicados de los sistemas antiguos)
y 60 días de ventas históricas en el ERP. Luego actualiza el Data Warehouse.
Uso (con los contenedores arriba): python scripts/cargar_datos.py"""
import random
from datetime import datetime, timedelta, timezone
import httpx
from _auth import headers
from catalogo import PRODUCTOS, TIENDAS, CLIENTES, email, asegurar_productos

CRM, ERP, ETL = "http://localhost:8001", "http://localhost:8002", "http://localhost:8005"
PERU = timezone(timedelta(hours=-5))
rnd = random.Random(2026)  # semilla fija: los mismos números en cada exposición
ADMIN = headers("ana.admin")

print("1) Catálogo de productos en el ERP...")
print(f"   {asegurar_productos(ERP, ADMIN)} productos nuevos ({len(PRODUCTOS)} en total)")

print("2) Clientes en el CRM (simulando registros que venían de tienda, web y CRM antiguo)...")
ids, duplicados = [], 0
for nombre, dni, cel in CLIENTES:
    r = httpx.post(f"{CRM}/customers", headers=ADMIN,
                   json={"doc_type": "DNI", "doc_number": dni, "full_name": nombre, "email": email(nombre), "phone": cel})
    ids.append(r.json()["customer_id"])
for nombre, dni, cel in rnd.sample(CLIENTES, 6):  # el mismo cliente llega de otro canal con datos escritos distinto
    r = httpx.post(f"{CRM}/customers", headers=ADMIN,
                   json={"doc_type": "DNI", "doc_number": dni, "full_name": nombre.upper(), "email": email(nombre).upper()})
    duplicados += r.status_code == 200
print(f"   {len(ids)} clientes únicos · {duplicados} duplicados detectados y unificados por el CRM")

print("3) Ventas históricas de los últimos 60 días...")
pesos = [p[5] for p in PRODUCTOS]
tiendas, tpesos = list(TIENDAS), [v[1] for v in TIENDAS.values()]
hoy = datetime.now(PERU).replace(hour=0, minute=0, second=0, microsecond=0)
filas = []
for dias in range(60, 0, -1):
    dia = hoy - timedelta(days=dias)
    n = 4 + (4 if dia.weekday() >= 5 else 0) + rnd.randint(0, 3)
    for _ in range(n):
        online = rnd.random() < 0.4
        lineas = {}
        for p in rnd.choices(PRODUCTOS, weights=pesos, k=rnd.choice([1, 1, 1, 2, 2, 3])):
            lineas[p[0]] = lineas.get(p[0], 0) + (rnd.choice([1, 1, 2]) if p[2] == "Accesorios" else 1)
        filas.append({
            "customer_id": rnd.choice(ids) if online or rnd.random() < 0.35 else "CONSUMIDOR_FINAL",
            "origin": "ecommerce" if online else "pos",
            "store_id": None if online else rnd.choices(tiendas, weights=tpesos)[0],
            "created_at": (dia + timedelta(hours=rnd.randint(10, 21), minutes=rnd.randint(0, 59))).isoformat(),
            "items": [{"sku": s, "qty": q} for s, q in lineas.items()]})
r = httpx.post(f"{ERP}/admin/migracion", headers=ADMIN, json=filas, timeout=60)
print("   " + (f"{r.json()['facturas_cargadas']} facturas históricas cargadas" if r.status_code == 201 else
              "ya estaban cargadas (para repetir: docker compose down -v)" if r.status_code == 409 else r.text))

print("4) Actualizando el Data Warehouse...")
r = httpx.post(f"{ETL}/api/run", headers=headers("gabriel.gerente"), timeout=60).json()
print(f"   ETL {r['status']}: {r['rows'].get('fact_sales', 0)} líneas de venta, {r['rows'].get('dim_customer', 0)} clientes")
print("\nListo. Abre http://localhost:8005 (gabriel.gerente) para ver el panel.")
