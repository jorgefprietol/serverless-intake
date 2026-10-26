# Integraciones

## Modelo local

Instala Ollama y un modelo compatible con salidas estructuradas. Configura
`MODEL_BACKEND=ollama`, `OLLAMA_MODEL=<modelo instalado>` y, si es necesario,
`OLLAMA_URL`. Las operaciones que usan modelos están descritas en README.
El adaptador usa `/api/generate`, timeout de 45 segundos, salida acotada y sin
redirecciones. Un fallo revierte la operación. Las reglas de negocio validan
la salida; el esquema enviado al proveedor no sustituye esa validación.

La demo usa `MODEL_BACKEND=local`: reglas o recuperación determinista. No descarga
modelos ni simula llamadas. El adaptador se verifica con dobles HTTP; la calidad
del modelo elegido debe evaluarse con el corpus y los criterios del dominio.

## n8n

`docker compose --profile orchestration up --build` inicia servicio y n8n local.
Importa `workflows/intake.json`. Configura dos credenciales Header Auth:
una en el Webhook para la entrada y otra en HTTP Request con `Authorization`
igual a `Bearer <SERVICE_TOKEN>`. Activa el workflow y usa su URL de producción.
El HTTP Request usa `http://service:8080/api/run` dentro de Compose. Si n8n se
ejecuta fuera, cambia esa URL. El webhook reenvía el JSON de dominio y conserva
`Idempotency-Key` del cliente; si falta, usa el identificador de ejecución.

Los JSON se validan estructuralmente en CI. No sustituyen una prueba en la
versión concreta de n8n. Usa credenciales guardadas en n8n, nunca en el JSON.
El contenedor n8n usa almacenamiento persistente y puerto local; configura su
cuenta al primer inicio. `N8N_SECURE_COOKIE=false` es sólo para HTTP en loopback.
Fija `N8N_VERSION` a la versión que valides antes de un despliegue reproducible.

ERP, CRM, mensajería y otros sistemas se incorporan mediante sus contratos
autenticados. Cuando una salida se describe como propuesta, outbox o simulación,
no se ha enviado a un sistema real.
