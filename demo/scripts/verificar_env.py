"""Revisa el archivo demo/.env y lo compara con lo que tienen los contenedores.
Uso: python scripts/verificar_env.py"""
import pathlib
import subprocess

DEMO = pathlib.Path(__file__).resolve().parents[1]
ENV = DEMO / ".env"
REQUIRED = ["ERP_DB_PASSWORD", "CRM_DB_PASSWORD", "ECOM_DB_PASSWORD", "POS_DB_PASSWORD", "DW_DB_PASSWORD",
            "RABBITMQ_USER", "RABBITMQ_PASSWORD", "KEYCLOAK_DB_PASSWORD", "KEYCLOAK_ADMIN", "KEYCLOAK_ADMIN_PASSWORD",
            "SERVICE_CLIENT_SECRET", "DEMO_USERS_PASSWORD", "ETL_READER_PASSWORD"]

for extra in [".env.txt", ".env.env"]:
    if (DEMO / extra).exists():
        print(f"⚠ Existe {extra}: el Bloc de notas pudo guardar con otro nombre. Docker solo lee '.env'.")
if not ENV.exists():
    raise SystemExit("✘ No existe demo/.env. Ejecuta: copy .env.example .env")

raw = ENV.read_bytes()
if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
    print("✘ .env está guardado en UTF-16. Ábrelo en el Bloc de notas y guárdalo como UTF-8.")
text = raw.decode("utf-8-sig", errors="replace")
vals = {}
for line in text.splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip()

print("Archivo leído:", ENV)
for k in REQUIRED:
    v = vals.get(k)
    if v is None:
        print(f"✘ {k}: falta (cópialo de .env.example)")
    elif v.startswith("cambiar_"):
        print(f"• {k}: usa el valor de ejemplo")
    elif any(c in v for c in " @:/#\"'"):
        print(f"✘ {k}: tiene espacios o símbolos; usa solo letras, números y _")
    else:
        print(f"✔ {k}: personalizado")


def container_value(service, var):
    try:
        out = subprocess.run(["docker", "compose", "exec", "-T", service, "printenv", var], cwd=DEMO,
                             capture_output=True, text=True, timeout=20)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


print("\nComparación con los contenedores en ejecución:")
for service, var, key in [("rabbitmq", "RABBITMQ_DEFAULT_PASS", "RABBITMQ_PASSWORD"),
                          ("keycloak", "KC_BOOTSTRAP_ADMIN_PASSWORD", "KEYCLOAK_ADMIN_PASSWORD")]:
    cv = container_value(service, var)
    if cv is None:
        print(f"  {service}: no está corriendo")
    elif cv == vals.get(key):
        print(f"  ✔ {service} usa el mismo valor que .env")
    else:
        print(f"  ✘ {service} usa OTRO valor que .env → ejecuta: docker compose down -v ; docker compose up -d --build")
