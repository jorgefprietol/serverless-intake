# Contrato HTTP

`GET /health` responde 200 si el proceso atiende solicitudes. No verifica proveedores.
`GET /` abre la consola; `GET /api/config` devuelve el ejemplo público.
`GET /api/metrics` requiere `Authorization: Bearer <SERVICE_TOKEN>`.

`POST /api/run` requiere el mismo token, `Content-Type: application/json` y
`Idempotency-Key` (1–128 caracteres: letras, números, `.`, `_`, `:`, `-`).
El cuerpo específico se describe en README y en el ejemplo de la consola.
Límite: 256 KiB. Respuesta: `{"request_id":"...","result":{...}}`.

Una misma clave y cuerpo devuelven el resultado persistido sin repetir efectos.
Otra carga con esa clave devuelve 409. Los errores de negocio devuelven 422 y
revierten la transacción completa. Una operación fallida puede reintentarse.
401: autenticación; 413: tamaño; 415: tipo; 500: fallo interno sin detalles.
La cabecera `Idempotency-Replayed` informa si se reutilizó la respuesta.

SQLite serializa escrituras; una llamada al modelo mantiene bloqueada la transacción.
Es un límite de esta implementación local. Para carga sostenida, separar workers
y usar almacenamiento e identidad adecuados al despliegue.

El token habilita todas las operaciones. Tenant, rol, aprobador y otros atributos
del cuerpo se confían a la integración autenticada; no prueban identidad humana.
