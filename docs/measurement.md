# Medición

`python -m app metrics` y la consola muestran solicitudes únicas completadas,
eventos y percentiles p50/p95 del proceso local. La muestra excluye errores,
reintentos reutilizados, red y proveedor externo fuera de la transacción.
Una muestra vacía devuelve percentiles nulos. No mide disponibilidad ni ahorro.

Para evaluar valor de negocio registra el conjunto de evaluación, volumen,
ventana temporal y una referencia manual con el mismo criterio. Mide errores
por caso y revisión humana además de tiempo. Conserva numerador y denominador.
Los ejemplos y las pruebas son sintéticos; no representan resultados de clientes.
