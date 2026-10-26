# Arquitectura

```mermaid
flowchart LR
    Client[Cliente IAM] --> API[API Gateway]
    API --> Intake[Lambda de entrada]
    Intake --> State[(DynamoDB)]
    Intake --> Queue[SQS]
    Queue --> Worker[Lambda worker]
    Worker --> State
    Worker --> Model[Bedrock Converse]
    Worker --> Results[(S3 privado)]
    Queue --> DLQ[Cola de fallos]
```

El API almacena primero el documento y su hash bajo una clave derivada del identificador de idempotencia. Sólo después publica el identificador en la cola. El cliente reintenta con la misma clave si falla la publicación. El worker reclama un lease de 100 segundos, invoca el modelo, escribe el resultado bajo una clave estable y marca el trabajo como completado.

El lease supera el timeout del worker (60 segundos); la visibilidad de la cola es 360 segundos. Un trabajo completado no vuelve a invocar el modelo. Una ejecución fallida devuelve `batchItemFailures` y deja el estado reintentable. Tras cinco entregas fallidas SQS dirige el mensaje a la DLQ.

La alternativa local persiste trabajos en SQLite y ejecuta el worker por acción explícita. No emula la infraestructura ni requiere boto3. La cola real sólo existe en AWS.
