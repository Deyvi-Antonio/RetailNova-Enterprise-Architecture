"""Simulación de la conexión de la tienda con la sede central (para la demo)."""
import os
import httpx

ERP_URL = os.getenv("ERP_URL", "")
online = True
_catalog_cache: list = []


def catalog() -> dict:
    global _catalog_cache
    if online:
        try:
            r = httpx.get(f"{ERP_URL}/products", timeout=3)
            r.raise_for_status()
            _catalog_cache = r.json()
            return {"online": True, "products": _catalog_cache}
        except Exception:
            pass
    return {"online": False, "products": _catalog_cache}  # copia local del catálogo
