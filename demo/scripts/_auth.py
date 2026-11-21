"""Inicio de sesión de los scripts de demo con los usuarios de prueba de Keycloak."""
import os
import pathlib
import time
import httpx

ENV_FILE = pathlib.Path(__file__).resolve().parents[1] / ".env"
TOKEN_URL = "http://localhost:8080/realms/retailnova/protocol/openid-connect/token"


def env(key: str) -> str:
    if os.getenv(key):
        return os.environ[key]
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            if line.strip().startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    raise SystemExit(f"Falta {key} en demo/.env")


def headers(user: str = "ana.admin") -> dict:
    data = {"grant_type": "password", "client_id": "retailnova-web", "username": user,
            "password": env("DEMO_USERS_PASSWORD"), "scope": "openid"}
    for i in range(40):  # Keycloak tarda ~1 min en arrancar la primera vez
        try:
            r = httpx.post(TOKEN_URL, data=data, timeout=5)
            if r.status_code == 200:
                return {"Authorization": "Bearer " + r.json()["access_token"]}
            if r.status_code == 401:
                raise SystemExit(f"Keycloak rechazó a {user}: revisa DEMO_USERS_PASSWORD en .env ({r.text[:120]})")
        except httpx.HTTPError:
            pass
        if i == 0:
            print("Esperando a que Keycloak esté listo...")
        time.sleep(3)
    raise SystemExit("Keycloak no respondió en http://localhost:8080")
