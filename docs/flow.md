# Flujo de operación

![Flujo de operación](diagrams/flow.svg)

[Abrir SVG](diagrams/flow.svg) · [Fuente Mermaid](diagrams/flow.mmd)


<details>
<summary>Versión Mermaid</summary>

```mermaid
flowchart TD
    Start["Recibir documento por API Gateway"] --> IAM["Autenticar IAM y validar entrada"]
    IAM --> Identity["Derivar trabajo desde Idempotency-Key"]
    Identity --> Exists{"¿Trabajo existente?"}
    Exists -->|Sí| Digest{"¿Documento idéntico?"}
    Digest -->|No| Conflict["Responder conflicto"]
    Digest -->|Sí| Queue["Publicar identificador en SQS si sigue pendiente"]
    Exists -->|No| Persist["Persistir documento y estado queued"]
    Persist --> Queue
    Queue --> Accept["Responder 202 después del envío"]
    Queue --> Claim["Worker reclama lease"]
    Claim --> Complete{"¿Trabajo ya completado?"}
    Complete -->|Sí| Reuse["Confirmar mensaje sin nueva inferencia"]
    Complete -->|No| Model["Invocar Bedrock y guardar resultado en S3"]
    Model --> Done["Marcar completed en DynamoDB"]
    Model -->|Fallo| Retry["Reportar fallo parcial y reintentar"]
    Retry -->|Cinco entregas fallidas| DLQ["Conservar mensaje en DLQ"]
```

</details>

- El diagrama de flujo describe el adaptador AWS entregado, no un despliegue ya ejecutado. En local: `submit` crea el trabajo, `process` lo ejecuta y `status` consulta el estado.
- Si falla el envío después de persistir, la API devuelve 503; el cliente debe reintentar con la misma clave para reparar esa ventana.
- El lease evita procesamiento simultáneo bajo los timeouts definidos. Un fallo posterior a la inferencia puede repetir inferencia y coste.

Los estados locales usan una transacción SQLite; el adaptador AWS usa escrituras condicionales y entregas de cola. Son mecanismos distintos con garantías de recuperación documentadas.

[Arquitectura](architecture.md) · [Tecnologías y alcance](technologies.md)
