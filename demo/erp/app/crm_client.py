"""Cliente síncrono hacia la API del CRM (patrón: API síncrona entre sistemas)."""
import os
import httpx

CRM_URL = os.getenv("CRM_URL", "")  # vacío = no validar (útil en pruebas locales)


def customer_exists(customer_id: str) -> bool:
    if not CRM_URL:
        return True
    try:
        r = httpx.get(f"{CRM_URL}/customers/{customer_id}", timeout=3.0)
    except httpx.HTTPError:
        raise RuntimeError("CRM no disponible")
    return r.status_code == 200
