"""Cliente síncrono hacia la API del CRM (patrón: API síncrona entre sistemas)."""
import os
import httpx
from . import auth

CRM_URL = os.getenv("CRM_URL", "")  # vacío = no validar (útil en pruebas locales)


def customer_exists(customer_id: str) -> bool:
    if not CRM_URL:
        return True
    try:
        r = httpx.get(f"{CRM_URL}/customers/{customer_id}", headers=auth.service_headers(), timeout=3.0)
    except httpx.HTTPError:
        raise RuntimeError("CRM o Keycloak no disponible")
    if r.status_code in (401, 403, 503):
        raise RuntimeError(f"CRM rechazó la credencial del ERP ({r.status_code})")
    return r.status_code == 200
