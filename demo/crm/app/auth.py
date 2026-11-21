"""Seguridad de aplicación: valida tokens JWT emitidos por Keycloak y aplica roles.

- Usuarios: inician sesión en Keycloak (pantalla oficial) y envían "Authorization: Bearer <token>".
- Servicios: se autentican entre sí con su propia cuenta de servicio (client credentials).
Con AUTH_ENABLED=false (pruebas locales) todo se permite como usuario "dev"."""
import os
import time
import logging
from dataclasses import dataclass, field

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer

log = logging.getLogger("auth")
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
KC_INTERNAL = os.getenv("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080")
REALM = os.getenv("KEYCLOAK_REALM", "retailnova")
ISSUERS = [s.strip() for s in os.getenv(
    "KEYCLOAK_ISSUERS", "http://localhost:8080/realms/retailnova,http://keycloak:8080/realms/retailnova").split(",") if s.strip()]
CLIENT_ID = os.getenv("SERVICE_CLIENT_ID", "retailnova-servicios")
CLIENT_SECRET = os.getenv("SERVICE_CLIENT_SECRET", "")

bearer = HTTPBearer(auto_error=False, description="Token de Keycloak")  # habilita el botón Authorize en /docs
_jwks = jwt.PyJWKClient(f"{KC_INTERNAL}/realms/{REALM}/protocol/openid-connect/certs", cache_keys=True, lifespan=300)
on_denied = None  # gancho opcional para auditar accesos denegados


@dataclass
class User:
    sub: str
    username: str
    roles: set = field(default_factory=set)


def _decode(token: str) -> dict:
    key = _jwks.get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["RS256"], issuer=ISSUERS,
                      options={"verify_aud": False, "require": ["exp", "iss", "sub"]})


def current_user(request: Request) -> User:
    if not AUTH_ENABLED:
        return User("dev", "dev", {"admin"})
    h = request.headers.get("authorization", "")
    if not h.lower().startswith("bearer "):
        raise HTTPException(401, "Inicia sesión para continuar", headers={"WWW-Authenticate": "Bearer"})
    try:
        c = _decode(h[7:])
    except jwt.PyJWKClientError:
        raise HTTPException(503, "Keycloak no disponible")
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "La sesión expiró, vuelve a iniciar sesión", headers={"WWW-Authenticate": "Bearer"})
    except jwt.InvalidTokenError as e:
        log.info("Token rechazado: %s", e)
        raise HTTPException(401, "Token inválido o manipulado", headers={"WWW-Authenticate": "Bearer"})
    roles = set(c.get("realm_access", {}).get("roles", []))
    return User(c["sub"], c.get("preferred_username") or c.get("azp", "?"), roles)


def require(*roles: str):
    """Dependencia de FastAPI: exige al menos uno de los roles (admin siempre pasa)."""
    allowed = set(roles) | {"admin"}

    def dep(request: Request, _creds=Depends(bearer)) -> User:
        user = current_user(request)
        if not (user.roles & allowed):
            if on_denied:
                on_denied(user, request)
            shown = sorted(r for r in user.roles if r in KNOWN_ROLES) or ["sin rol"]
            raise HTTPException(403, f"Tu rol ({', '.join(shown)}) no tiene permiso. Se requiere: {', '.join(sorted(roles))}")
        request.state.user = user
        return user
    return dep


KNOWN_ROLES = {"admin", "gerente", "cajero", "atencion_cliente", "integracion"}

_tok = {"value": None, "exp": 0.0}


def service_headers() -> dict:
    """Token de la cuenta de servicio para llamar a otros sistemas (se reutiliza hasta que vence)."""
    if not AUTH_ENABLED:
        return {}
    if _tok["value"] and time.time() < _tok["exp"] - 30:
        return {"Authorization": f"Bearer {_tok['value']}"}
    r = httpx.post(f"{KC_INTERNAL}/realms/{REALM}/protocol/openid-connect/token",
                   data={"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
                   timeout=5)
    r.raise_for_status()
    j = r.json()
    _tok.update(value=j["access_token"], exp=time.time() + j["expires_in"])
    return {"Authorization": f"Bearer {_tok['value']}"}
