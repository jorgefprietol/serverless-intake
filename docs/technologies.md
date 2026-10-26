# Tecnologías y alcance

Python 3.10+ y SQLite para la demo; adaptadores Python 3.12 para Lambda, API Gateway, SQS, DynamoDB, Bedrock y S3 definidos mediante AWS SAM.

| Tecnología | Estado | Uso en este proyecto |
| --- | --- | --- |
| Python 3.10+ / SQLite | Implementado localmente | CLI, consola y ciclo queued/completed con ejecución explícita. |
| Ollama / HTTP JSON | Opcional local | Generación sobre el documento; servidor y modelo por configurar. |
| AWS SAM / CloudFormation | Plantilla incluida | Recursos, cifrado, retención, concurrencia y permisos acotados; sin despliegue validado. |
| API Gateway HTTP API / IAM / Lambda Python 3.12 | Adaptadores incluidos | Entrada firmada con SigV4 y respuesta asíncrona 202; pruebas con dobles de SDK. |
| SQS / DLQ | Adaptadores y plantilla | Entrega al menos una vez, fallo parcial y redirección tras cinco entregas fallidas. |
| DynamoDB | Adaptador y plantilla | Hash de documento, estado, lease, TTL y escrituras condicionales. |
| Bedrock Converse / boto3 | Adaptador incluido | Inferencia y uso de tokens; requiere modelo disponible y permisos en la región. |
| S3 | Adaptador y plantilla | Resultado privado, cifrado solicitado y clave estable por trabajo. |
| n8n / Docker Compose | Archivos incluidos | Puente hacia la API local y empaquetado; no sustituyen el despliegue AWS. |
| unittest / GitHub Actions | Implementado | Ciclo local, reintentos, leases, fallo del proveedor y contrato HTTP. |

“Implementado” describe código disponible y comprobable en el repositorio. “Opcional” requiere un proveedor configurado; “incluido” identifica un archivo o adaptador entregado, sin afirmar una integración externa ejecutada.

[Arquitectura](architecture.md) · [Flujo de operación](flow.md) · [Integraciones](integrations.md)
