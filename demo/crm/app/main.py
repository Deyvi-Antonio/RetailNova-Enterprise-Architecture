import re
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import auth
from .auth import require, User
from .db import Base, engine, get_db, SessionLocal
from .models import Customer, AuditLog

app = FastAPI(title="RetailNova CRM", version="0.4.0")
Base.metadata.create_all(engine)


def audit(user: User, request: Request, action: str, resource: str | None, result: str = "PERMITIDO"):
    with SessionLocal() as db:
        db.add(AuditLog(username=user.username, roles=",".join(sorted(user.roles & auth.KNOWN_ROLES)),
                        action=action, resource=resource, result=result,
                        ip=request.client.host if request.client else None))
        db.commit()


auth.on_denied = lambda user, request: audit(user, request, f"{request.method} {request.url.path}", None, "DENEGADO")

DOC_RULES = {"DNI": r"^\d{8}$", "RUC": r"^\d{11}$", "CE": r"^[A-Za-z0-9]{9,12}$"}


class CustomerIn(BaseModel):
    doc_type: str = Field(examples=["DNI"])
    doc_number: str = Field(examples=["12345678"])
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    phone: str | None = None


class CustomerOut(BaseModel):
    customer_id: str
    doc_type: str
    doc_number: str
    full_name: str
    email: str
    phone: str | None
    created_at: datetime | None = None
    model_config = {"from_attributes": True}


@app.get("/", response_class=HTMLResponse)
def console_page():
    return (Path(__file__).parent / "console.html").read_text(encoding="utf-8")


@app.get("/static/auth.js")
def auth_js():
    return Response((Path(__file__).parent / "web_auth.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/health")
def health():
    return {"status": "ok", "service": "crm"}


@app.post("/customers", response_model=CustomerOut, status_code=201)
def upsert_customer(data: CustomerIn, response: Response, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(require("integracion", "atencion_cliente"))):
    """Crea el cliente o devuelve el existente (sin duplicar).
    Duplicado = mismo documento O mismo correo (normalizado)."""
    doc_type = data.doc_type.strip().upper()
    doc_number = data.doc_number.strip().upper()
    email = data.email.strip().lower()
    rule = DOC_RULES.get(doc_type)
    if not rule:
        raise HTTPException(422, f"doc_type no soportado: {doc_type}")
    if not re.match(rule, doc_number):
        raise HTTPException(422, f"doc_number inválido para {doc_type}")

    existing = db.scalar(select(Customer).where(
        (Customer.email == email) | ((Customer.doc_type == doc_type) & (Customer.doc_number == doc_number))
    ))
    if existing:
        response.status_code = 200  # ya existía: mismo ID, sin duplicar
        audit(user, request, "RECONOCER_CLIENTE", existing.customer_id)
        return existing

    c = Customer(doc_type=doc_type, doc_number=doc_number, full_name=data.full_name.strip(),
                 email=email, phone=data.phone)
    db.add(c)
    db.commit()
    db.refresh(c)
    audit(user, request, "CREAR_CLIENTE", c.customer_id)
    return c


@app.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: str, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(require("integracion", "atencion_cliente"))):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    audit(user, request, "VER_CLIENTE", customer_id)
    return c


@app.get("/customers", response_model=list[CustomerOut])
def list_customers(request: Request, limit: int = 50, db: Session = Depends(get_db),
                   user: User = Depends(require("atencion_cliente"))):
    """Datos personales: solo Atención al cliente (y admin). Cada consulta queda auditada."""
    rows = db.scalars(select(Customer).order_by(Customer.created_at.desc()).limit(min(limit, 200))).all()
    audit(user, request, "LISTAR_CLIENTES", f"{len(rows)} registros")
    return rows


@app.get("/audit")
def list_audit(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(require("admin"))):
    """Registro de auditoría (solo administrador)."""
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500))).all()
    return [{"at": a.at.isoformat(), "usuario": a.username, "roles": a.roles, "accion": a.action,
             "recurso": a.resource, "resultado": a.result, "ip": a.ip} for a in rows]


@app.get("/me")
def me(user: User = Depends(require(*auth.KNOWN_ROLES))):
    return {"usuario": user.username, "roles": sorted(user.roles & auth.KNOWN_ROLES)}
