"""Utilidades de prueba: firma tokens como lo haría Keycloak (RS256)."""
import time
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER = rsa.generate_private_key(public_exponent=65537, key_size=2048)
ISS = "http://localhost:8080/realms/retailnova"


class FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        return type("K", (), {"key": KEY.public_key()})()


def token(user, roles, exp_in=300, iss=ISS, key=KEY):
    now = int(time.time())
    return jwt.encode({"sub": user, "preferred_username": user, "iss": iss, "iat": now, "exp": now + exp_in,
                       "realm_access": {"roles": roles + ["default-roles-retailnova"]}}, key, algorithm="RS256")


def h(user, roles, **kw):
    return {"Authorization": "Bearer " + token(user, roles, **kw)}


def enable(monkeypatch, auth):
    monkeypatch.setattr(auth, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth, "_jwks", FakeJWKS())
