"""Llamadas síncronas a otros sistemas (CRM y ERP) por su API."""
import os
import httpx
from . import auth

CRM_URL = os.getenv("CRM_URL", "")
ERP_URL = os.getenv("ERP_URL", "")
_catalog_cache: list = []


def upsert_customer(payload: dict) -> str:
    """Registra o reconoce al cliente en el CRM y devuelve su ID único."""
    if not CRM_URL:
        raise RuntimeError("CRM_URL no configurado")
    try:
        r = httpx.post(f"{CRM_URL}/customers", json=payload, headers=auth.service_headers(), timeout=5)
    except httpx.HTTPError:
        raise RuntimeError("CRM o Keycloak no disponible")
    if r.status_code in (401, 403, 503):
        raise RuntimeError(f"El CRM rechazó la credencial del e-commerce ({r.status_code})")
    if r.status_code in (200, 201):
        return r.json()["customer_id"]
    raise ValueError(str(r.json().get("detail", "Datos de cliente inválidos")))


def catalog() -> dict:
    """Catálogo publicado por el ERP. Si el ERP no responde, se usa la última copia."""
    global _catalog_cache
    try:
        r = httpx.get(f"{ERP_URL}/products", timeout=3)
        r.raise_for_status()
        _catalog_cache = r.json()
        return {"online": True, "products": _catalog_cache}
    except Exception:
        return {"online": False, "products": _catalog_cache}
