"""Esquema del Data Warehouse (modelo estrella).

Minimización de datos (Ley N.º 29733): el DW NO guarda nombres, correos ni
números de documento. El cliente se identifica solo por su ID seudónimo del CRM."""
from sqlalchemy import (MetaData, Table, Column, Integer, String, Numeric, Date, DateTime, Text)

md = MetaData()

dim_date = Table("dim_date", md,
    Column("date_key", Integer, primary_key=True),          # AAAAMMDD
    Column("date", Date), Column("year", Integer), Column("month", Integer), Column("day", Integer),
    Column("month_name", String(12)), Column("weekday_name", String(12)))

dim_product = Table("dim_product", md,
    Column("sku", String(40), primary_key=True), Column("name", String(200)),
    Column("list_price", Numeric(12, 2)), Column("current_stock", Integer))

dim_customer = Table("dim_customer", md,
    Column("customer_id", String(40), primary_key=True), Column("doc_type", String(10)),
    Column("registered_date_key", Integer))

dim_channel = Table("dim_channel", md,
    Column("channel", String(20), primary_key=True), Column("description", String(80)))

fact_sales = Table("fact_sales", md,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("invoice_id", Integer, index=True), Column("date_key", Integer, index=True),
    Column("customer_id", String(40), index=True), Column("sku", String(40), index=True),
    Column("channel", String(20), index=True), Column("store_id", String(20), nullable=True),
    Column("qty", Integer), Column("unit_price", Numeric(12, 2)),
    Column("amount_net", Numeric(14, 2)), Column("amount_igv", Numeric(14, 2)), Column("amount_total", Numeric(14, 2)))

fact_orders = Table("fact_orders", md,
    Column("order_ref", String(40), primary_key=True), Column("source", String(20)),
    Column("status", String(20)), Column("date_key", Integer), Column("invoice_id", Integer, nullable=True))

etl_runs = Table("etl_runs", md,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("started_at", DateTime(timezone=True)), Column("finished_at", DateTime(timezone=True)),
    Column("status", String(10)), Column("rows_json", Text), Column("error", Text, nullable=True))

DIMS_AND_FACTS = [fact_sales, fact_orders, dim_product, dim_customer, dim_channel, dim_date]
