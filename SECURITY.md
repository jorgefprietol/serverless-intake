# Seguridad

No publiques datos de clientes, documentos reales ni credenciales en incidencias.
Para un reporte privado usa el contacto del perfil de GitHub del mantenedor.

El servicio exige un token compartido y escucha en loopback por defecto. El token
identifica una integración, no un usuario: los campos de tenant y de aprobación
deben venir de una pasarela confiable. No es un sistema de identidad multiusuario.
Antes de exponerlo: TLS, identidad de usuarios, autorización por operación,
límites de concurrencia, retención y cifrado de datos, copias y restauración.

Las entradas y las respuestas de los modelos son datos no confiables. La validación
de negocio sigue siendo obligatoria. Las demos no llaman servicios externos.
