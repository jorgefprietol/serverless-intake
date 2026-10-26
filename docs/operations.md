# Operación

## Local

`./run.ps1 serve -Port 8088` inicia la consola. La base está en `var/service.db`, excluida de Git. Detén con Ctrl+C. Para eliminar una demo persistente, respalda primero `var/`; la demo CLI usa una base temporal que se elimina al terminar.

## Cuenta AWS de pruebas

Requiere AWS CLI, AWS SAM CLI, permisos de despliegue y un modelo Bedrock habilitado. No hay credenciales en el repositorio. `boto3` está incluido en el runtime administrado de Lambda; para ejecutar los adaptadores directamente instala una versión del SDK que hayas validado.

```bash
sam validate --lint
sam build
sam deploy --guided
```

Especifica región, `ModelId` y el ARN exacto de ese mismo modelo. Revisa el changeset, las cuotas de concurrencia y el coste antes de ejecutarlo. Los comandos de despliegue no se ejecutan automáticamente. `sam validate --lint` requiere las herramientas de AWS, no necesarias para las pruebas unitarias.

Firma con SigV4 `POST /jobs`, usando `Idempotency-Key` y un cuerpo `{"operation":"summarize","text":"..."}`. Consulta `GET /jobs/{id}` para obtener estado y `result_key`. Lee el objeto desde el bucket de salida con permiso `s3:GetObject`. La API usa IAM, mientras el servicio local usa un token; son adaptadores con autenticación distinta.

Configura alarmas para mensajes visibles en DLQ, edad máxima en cola, errores y throttling de Lambda. Ante fallo de modelo: corrige permisos/cuota/modelo, inspecciona el estado y redirige mensajes desde la DLQ. No generes una clave nueva para reintentar el mismo documento.

Los trabajos caducan a los siete días (TTL eventual); los resultados a los treinta. S3 se conserva al eliminar el stack. Antes de `sam delete`, exporta la evidencia necesaria y decide qué datos conservar. El borrado del stack no elimina el bucket retenido ni sus costes.

## Límites de validación

Las pruebas no verifican IAM efectivo, entrega de SQS, políticas de cuenta, disponibilidad regional, cuotas, SAM transformado ni respuestas de un modelo real. Deben validarse mediante despliegue controlado. No existe un valor de ahorro o disponibilidad medido para esta implementación.
