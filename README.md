# RetailNova Enterprise Architecture

Trabajo integrador de Arquitectura Empresarial (TOGAF, ciclo 2026-2) y demo local.

## Estructura
- `docs/` – documentos de arquitectura (Fases A–H).
- `demo/` – demo local: ERP, CRM, e-commerce, POS, ETL/DW, dashboard.
- `demo/agent-gateway/` – reservado para el MVP (agentes de IA). Vacío por ahora.

## Principio de diseño
Cada sistema tiene su **propia base de datos**. "Una sola fuente de verdad" significa
un sistema oficial por dato (p. ej., el CRM genera el ID único de cliente), no una base compartida.

## Requisitos
- Docker Desktop (WSL2 en Windows). Todo es gratuito; no se usan APIs de pago.

## Levantar (Sprint 0)
```bash
cd demo
cp .env.example .env      # cambia las contraseñas
docker compose up -d
docker compose ps         # las bases deben quedar "healthy"
```
- RabbitMQ: http://localhost:15672
- Keycloak: http://localhost:8080

Detener: `docker compose down` (conserva datos) · `docker compose down -v` (borra datos).

## Seguridad
`.env` nunca se sube a Git. Solo datos sintéticos. Ver `docs/` para Ley N.º 29733.

## Plan
Sprint 0 base · 1 ERP+CRM+ID único · 2 e-commerce+POS+eventos · 3 DW+dashboard · 4 seguridad+pruebas+guion.
