# Serverless Intake

Servicio de entrada de documentos con trabajos persistentes, procesamiento desacoplado y resultados trazables. Incluye una implementación local y adaptadores para API Gateway, Lambda, SQS, DynamoDB, Bedrock y S3.

## Diseño y tecnologías

Python 3.10+ y SQLite para la demo; adaptadores Python 3.12 para Lambda, API Gateway, SQS, DynamoDB, Bedrock y S3 definidos mediante AWS SAM.

[Diagrama de arquitectura](docs/architecture.md) · [Diagrama del flujo](docs/flow.md) · [Tecnologías y alcance](docs/technologies.md)

## Ejecución local

Python 3.10 o posterior; no requiere instalar paquetes para la demo.

```powershell
./run.ps1 demo
./run.ps1 test
./run.ps1 serve -Port 8088
```

En Linux/macOS: `python -m app demo`; para la consola define `SERVICE_TOKEN` con al menos 24 caracteres y ejecuta `python -m app serve`. Abre la dirección del servicio e introduce el token en la consola.

```json
{"action":"submit","operation":"summarize","text":"Documento de ejemplo","run_inline":false}
```

Usa `POST /api/run`, Bearer token y `Idempotency-Key`. La respuesta devuelve un `job_id`. Procesa con `{"action":"process","job_id":"..."}` y consulta con `{"action":"status","job_id":"..."}`. `run_inline:true` completa el trabajo en una llamada para facilitar la demo. Operaciones: `summarize`, `classify`, `extract`. En modo local usan extracción, reglas y patrones; `MODEL_BACKEND=ollama` habilita el adaptador de generación.

## Implementación AWS

`template.yaml` define entrada autenticada con IAM, cola cifrada y DLQ, workers con concurrencia limitada, estado con TTL, resultados privados y permisos sobre recursos concretos. El worker usa Bedrock Converse y conserva el uso de tokens que devuelve el proveedor. La API devuelve 202; el resultado se obtiene desde S3 con una identidad autorizada.

La misma clave y documento conservan el trabajo. Una clave con otro documento devuelve 409. Una respuesta 503 tras persistir el trabajo puede recuperarse reintentando la misma petición. La entrega de SQS es al menos una vez: un lease evita trabajo simultáneo; un fallo entre inferencia y persistencia puede repetir inferencia y generar coste adicional.

Los adaptadores se prueban con dobles de SDK, sin llamadas a AWS. La plantilla no se ha desplegado ni se han medido disponibilidad, coste o calidad del modelo en una cuenta real. [Despliegue y recuperación](docs/operations.md) describe el procedimiento y los límites.

## Verificación y decisiones

- `python -m unittest discover -s tests -v`: ciclo local, claves, colas, leases, reintentos, cifrado solicitado y fallos del proveedor.
- `python -m app demo`: ejecución con datos sintéticos.
- [Arquitectura](docs/architecture.md), [decisiones](docs/decisions.md), [contrato local](docs/api.md), [referencias](docs/references.md).

Métricas locales: transacciones únicas, eventos y p50/p95; en AWS: profundidad de cola, edad del mensaje, DLQ, errores, latencia y tokens. Un resultado del modelo es un documento de salida, nunca una instrucción ejecutable.
