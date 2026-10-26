# Decisiones

1. **Trabajo asíncrono.** La entrada no espera a la inferencia. Evita acoplar el tiempo de API al proveedor; añade estados y recuperación de colas.
2. **DynamoDB antes de SQS.** Conserva un trabajo aunque falle el envío. La reparación requiere reintento del cliente con la misma clave; no se implementa un outbox por streams.
3. **Lease y salida estable.** Reducen duplicados, sin prometer una sola inferencia. Si se pierde una confirmación después de invocar Bedrock, puede repetirse el coste.
4. **Modelo explícito.** `ModelId` y `ModelArn` deben referirse al mismo modelo disponible en la región. El ejemplo no concede permisos amplios para perfiles entre regiones.
5. **Una organización operadora.** IAM autentica integraciones. El ejemplo comparte un espacio de trabajos entre identidades autorizadas. Para clientes aislados, introducir tenant derivado de identidad y políticas por tenant antes de publicar.
6. **Datos limitados.** Documentos de hasta 20 000 caracteres, resultado de hasta 20 000, sin ejecución de herramientas y sin texto documental en logs.
