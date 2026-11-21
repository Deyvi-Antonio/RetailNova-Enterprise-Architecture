"""Mensajería por eventos con RabbitMQ (exchange tipo topic).

Formato de evento: {event_id, type, source, occurred_at, data}.
"""
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone

import pika

EXCHANGE = "retailnova.events"
DLX = "retailnova.dlx"          # mensajes que no se pudieron procesar
URL = os.getenv("RABBITMQ_URL", "")
log = logging.getLogger("bus")
logging.getLogger("pika").setLevel(logging.WARNING)  # menos ruido en los logs


class TransientError(Exception):
    """Error temporal (p. ej., otro sistema caído): el mensaje se reintenta."""


def make_event(type_: str, source: str, data: dict, event_id: str | None = None) -> dict:
    return {"event_id": event_id or str(uuid.uuid4()), "type": type_, "source": source,
            "occurred_at": datetime.now(timezone.utc).isoformat(), "data": data}


def _declare(ch):
    ch.exchange_declare(EXCHANGE, "topic", durable=True)
    ch.exchange_declare(DLX, "fanout", durable=True)
    ch.queue_declare("retailnova.dead-letters", durable=True)
    ch.queue_bind("retailnova.dead-letters", DLX)


def publish(routing_key: str, event: dict) -> None:
    if not URL:
        raise RuntimeError("RABBITMQ_URL no configurado")
    conn = pika.BlockingConnection(pika.URLParameters(URL))
    try:
        ch = conn.channel()
        _declare(ch)
        ch.confirm_delivery()  # el broker confirma que recibió el mensaje
        ch.basic_publish(EXCHANGE, routing_key, json.dumps(event).encode(),
                         properties=pika.BasicProperties(delivery_mode=2, content_type="application/json",
                                                         message_id=event["event_id"]))
    finally:
        conn.close()


def start_consumer(queue: str, bindings: list[str], handler) -> threading.Thread:
    """Consume en un hilo aparte y se reconecta solo si RabbitMQ se cae."""
    def run():
        while True:
            try:
                conn = pika.BlockingConnection(pika.URLParameters(URL))
                ch = conn.channel()
                _declare(ch)
                ch.queue_declare(queue, durable=True, arguments={"x-dead-letter-exchange": DLX})
                for b in bindings:
                    ch.queue_bind(queue, EXCHANGE, b)
                ch.basic_qos(prefetch_count=1)

                def cb(ch_, method, props, body):
                    try:
                        handler(method.routing_key, json.loads(body))
                        ch_.basic_ack(method.delivery_tag)
                    except TransientError as e:
                        log.warning("Error temporal, se reintenta: %s", e)
                        time.sleep(3)
                        ch_.basic_nack(method.delivery_tag, requeue=True)
                    except Exception:
                        log.exception("Evento inválido: va a dead-letters")
                        ch_.basic_nack(method.delivery_tag, requeue=False)

                ch.basic_consume(queue, cb)
                log.info("Escuchando cola %s %s", queue, bindings)
                ch.start_consuming()
            except Exception as e:  # broker no disponible: reintentar
                log.warning("RabbitMQ no disponible (%s); reintento en 5 s", e)
                time.sleep(5)

    t = threading.Thread(target=run, daemon=True, name=f"consumer-{queue}")
    t.start()
    return t


def start_loop(fn, every: float, name: str) -> threading.Thread:
    """Ejecuta fn() periódicamente (usado para vaciar la bandeja de salida)."""
    def run():
        while True:
            try:
                fn()
            except Exception:
                log.exception("Error en %s", name)
            time.sleep(every)
    t = threading.Thread(target=run, daemon=True, name=name)
    t.start()
    return t
