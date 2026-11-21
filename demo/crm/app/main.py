import re
from fastapi import FastAPI, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import Base, engine, get_db
from .models import Customer

app = FastAPI(title="RetailNova CRM", version="0.1.0")
Base.metadata.create_all(engine)

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
    model_config = {"from_attributes": True}


@app.get("/health")
def health():
    return {"status": "ok", "service": "crm"}


@app.post("/customers", response_model=CustomerOut, status_code=201)
def upsert_customer(data: CustomerIn, response: Response, db: Session = Depends(get_db)):
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
        return existing

    c = Customer(doc_type=doc_type, doc_number=doc_number, full_name=data.full_name.strip(),
                 email=email, phone=data.phone)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@app.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    c = db.get(Customer, customer_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    return c


@app.get("/customers", response_model=list[CustomerOut])
def list_customers(limit: int = 50, db: Session = Depends(get_db)):
    return db.scalars(select(Customer).limit(min(limit, 200))).all()
