"""Durable local job lifecycle, matching the queue/worker cloud contract."""
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

TITLE = "Serverless Intake"
DESCRIPTION = "Entrada asíncrona de documentos, estados de ejecución y resultados trazables en AWS."
DEMO = {"action": "submit", "operation": "summarize", "text": "El equipo de operaciones recibió tres solicitudes de actualización. Dos fueron aprobadas y una requiere revisión de seguridad.", "run_inline": True}
OPERATIONS = {"summarize", "classify", "extract"}


def validate(payload):
    if not isinstance(payload, dict):
        raise ValueError("El documento debe ser un objeto JSON")
    operation = payload.get("operation", "summarize")
    text = payload.get("text")
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValueError("operation debe ser summarize, classify o extract")
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 20000:
        raise ValueError("text debe tener entre 1 y 20000 caracteres")
    return {"operation": operation, "text": text.strip()}


def local_result(document):
    text = document["text"]
    operation = document["operation"]
    if operation == "summarize":
        return {"text": " ".join(re.split(r"(?<=[.!?])\s+", text)[:2]), "method": "extractive_local"}
    if operation == "classify":
        category = "security" if re.search(r"seguridad|security|vulnerab", text, re.I) else "operations"
        return {"category": category, "method": "rules_local"}
    return {"references": re.findall(r"\b[A-Z]{2,6}-\d{2,12}\b", text), "method": "patterns_local"}


def process(payload, store):
    db = store.connection
    db.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, document TEXT NOT NULL, status TEXT NOT NULL, result TEXT, created_at TEXT NOT NULL)")
    action = payload.get("action", "submit")
    if action == "submit":
        document = validate(payload)
        job_id = str(uuid.uuid4())
        db.execute("INSERT INTO jobs VALUES(?,?,?,?,?)", (job_id, json.dumps(document), "queued", None, datetime.now(timezone.utc).isoformat()))
        store.event("job.queued", {"job_id": job_id, "operation": document["operation"]})
        if payload.get("run_inline") is not True:
            return {"job_id": job_id, "status": "queued", "execution": "local"}
        action = "process"
    else:
        job_id = payload.get("job_id")
        if not isinstance(job_id, str):
            raise ValueError("job_id requerido")
    row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise ValueError("Trabajo desconocido")
    if action == "status":
        return {"job_id": job_id, "status": row["status"], "result": json.loads(row["result"]) if row["result"] else None}
    if action != "process":
        raise ValueError("Acción desconocida")
    if row["status"] == "completed":
        return {"job_id": job_id, "status": "completed", "result": json.loads(row["result"]), "reused": True}
    document = json.loads(row["document"])
    backend = os.getenv("MODEL_BACKEND", "local")
    if backend == "local":
        result = local_result(document)
    elif backend == "ollama":
        from .providers import generate
        result = {"text": generate(json.dumps(document)), "method": "ollama"}
    else:
        raise ValueError("Backend local soporta local u ollama; Bedrock se ejecuta en el worker AWS")
    db.execute("UPDATE jobs SET status='completed', result=? WHERE id=?", (json.dumps(result), job_id))
    store.event("job.completed", {"job_id": job_id, "method": result["method"]})
    return {"job_id": job_id, "status": "completed", "result": result, "execution": "local"}
