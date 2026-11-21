"""Escena 5: seguridad por roles y auditoría (Ley N.º 29733).
Uso (con los contenedores arriba): python scripts/demo_seguridad.py"""
import sys
import httpx
from _auth import headers

CRM, ERP, PANEL = "http://localhost:8001", "http://localhost:8002", "http://localhost:8005"
ok = True


def check(desc, resp, expected):
    global ok
    good = resp.status_code == expected
    ok &= good
    detail = resp.json().get("detail", "") if resp.status_code >= 400 else ""
    print(f"{'✔' if good else '✘'} {desc}: {resp.status_code} {detail}")


u = {n: headers(n) for n in ["ana.admin", "gabriel.gerente", "carla.cajera", "sofia.atencion"]}
print("== Escena 5: acceso por rol ==")
check("Sin iniciar sesión, ver clientes del CRM", httpx.get(f"{CRM}/customers"), 401)
check("Cajera intenta ver datos personales de clientes", httpx.get(f"{CRM}/customers", headers=u["carla.cajera"]), 403)
r = httpx.get(f"{CRM}/customers", headers=u["sofia.atencion"])
check(f"Atención al cliente ve clientes ({len(r.json()) if r.status_code == 200 else 0} registros)", r, 200)
check("Cajera intenta ver el panel gerencial", httpx.get(f"{PANEL}/api/kpis", headers=u["carla.cajera"]), 403)
check("Gerente ve el panel gerencial", httpx.get(f"{PANEL}/api/kpis", headers=u["gabriel.gerente"]), 200)
check("Gerente intenta ver la auditoría", httpx.get(f"{CRM}/audit", headers=u["gabriel.gerente"]), 403)
check("Token falso", httpx.get(f"{CRM}/customers", headers={"Authorization": "Bearer abc.def.ghi"}), 401)

print("\n== Registro de auditoría del CRM (lo ve solo el administrador) ==")
a = httpx.get(f"{CRM}/audit?limit=6", headers=u["ana.admin"])
check("Administradora ve la auditoría", a, 200)
for e in a.json() if a.status_code == 200 else []:
    print(f"  {e['at'][11:19]}  {e['usuario']:<36} {e['accion']:<22} {e['resultado']}")

print("\nRESULTADO:", "OK" if ok else "REVISAR")
sys.exit(0 if ok else 1)
