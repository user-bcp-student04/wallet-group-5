# Design

## Context

Ver la motivación en `proposal.md`. `auth` usa SQLite con credenciales de
demostración en texto plano y genera tokens Base64 propios; `api` exige JWT
RS256 con `sub`, `iss`, `aud` y `exp`. El login web actual guarda ese token
heredado y navega al dashboard de tareas. No existe un flujo de registro ni
prueba de integración real entre ambos servicios.

Los contratos actuales de `POST /auth/login` y `/api/tasks` se conservan. Se
necesita caracterización antes de tocar persistencia o tokens existentes y no
se puede reutilizar la autenticación heredada como mecanismo seguro de la nueva
cuenta.

## Goals / Non-Goals

**Goals:**

- Separar el ciclo de cuenta nueva del almacenamiento y sesión de demostración.
- Activar e iniciar sesión solo al validar un desafío de correo, con pruebas
  reproducibles y datos aislados.
- Emitir una credencial verificable por el perfil JWT existente de la API.

**Non-Goals:**

- Migrar cuentas de demostración, eliminar sus contratos o habilitar una wallet
  y operaciones de dinero.
- Elegir un proveedor de correo o alterar la política de autorización de tareas.

## Decisions

1. **Onboarding en `auth`, UI en `web`.** Crear endpoints nuevos con contratos
   explícitos y capas HTTP, servicio, repositorio y seguridad. Angular consumirá
   esos endpoints mediante un servicio y presentará registro, verificación,
   errores y estado de cuenta activa. Alternativa: extender el login heredado;
   se descarta para evitar mezclar credenciales inseguras y romper su contrato.
   Las rutas y esquemas exactos se acordarán antes de implementarlos.
2. **Registro pendiente separado de cuenta activa.** Guardar una credencial
   protegida con hash de contraseña resistente y salt, más desafío asociado a
   una solicitud; activar y consumir el desafío de forma atómica. Una nueva
   solicitud para un correo pendiente reemplaza el desafío y la credencial
   pendiente e invalida el desafío anterior, evitando que el propietario active
   accidentalmente una contraseña de un registro anterior. Una cuenta activa
   nunca se sobrescribe. La verificación se vincula tanto al desafío como a la
   solicitud que lo inició, para impedir que otra solicitud use el código.
   Alternativa: insertar directamente en `legacy_users`; se descarta por su
   almacenamiento de contraseñas en texto claro y consulta insegura.
3. **Código de un solo uso y controles.** Generar el código con aleatoriedad
   criptográfica y almacenar un verificador protegido con clave externa, no el
   código en texto plano. Exigir vencimiento, límites de intentos y solicitudes,
   comparación segura y consumo atómico. La duración, tamaño, límites, conducta
   de reintento y gestión de clave requieren aprobación antes de programar.
   Alternativa: almacenar el código como texto; se descarta por exposición.
4. **Entrega desacoplada.** Definir un puerto de envío con adaptador real
   seleccionado y un adaptador de prueba aislado; no registrar códigos ni
   respuestas del proveedor con datos sensibles. El tratamiento de errores
   debe ser uniforme para cuentas existentes y nuevas, sin dar éxito falso si
   el servicio de envío está indisponible. No se autoriza usar un servicio
   externo real hasta elegir proveedor, configuración y condiciones de uso.
5. **Sesión nueva y segura.** Al confirmar la cuenta, emitir un JWT firmado
   con el perfil RS256 y claims requeridos por `api`; custodiar la clave
   privada en configuración externa. El mecanismo de transporte y persistencia
   de la sesión web debe acordarse con seguridad antes de implementarse.
   Alternativa: `LegacyTokenUtil`; se descarta porque no firma un JWT y es
   incompatible con el verificador de `api`.
6. **Respuesta genérica y trazabilidad.** Igualar códigos y forma de respuesta
   pública para registros válidos de cuentas nuevas y existentes; reducir
   diferencias observables de tiempo y efectos secundarios y probarlas. Los
   errores operativos se registran sin direcciones completas, contraseñas ni
   códigos. Contraseñas, códigos y valores reales no se incluyen en pruebas.

## Risks / Trade-offs

- **Registro anticipado o sustitución de desafío** → invalidar desafíos previos,
  vincular solicitud y código y nunca modificar cuentas activas; validar
  concurrencia, abuso y posibilidad de denegación de servicio.
- **Enumeración de cuentas por mensajes, tiempos o envío** → respuestas
  equivalentes, límites de uso y evaluación de canales laterales, incluidos
  errores del proveedor; documentar cualquier riesgo residual.
- **Indisponibilidad de correo o clave** → fallar explícitamente sin crear una
  sesión ni exponer datos; probar el adaptador de fallos y recuperación.
- **Sesión o datos heredados inseguros** → aislar las cuentas nuevas y no
  promover la solución a producción sin revisión humana de seguridad.
- **Uso compartido de SQLite y concurrencia** → decisiones de transacción,
  unicidad y manejo de errores verificadas con pruebas de concurrencia; revisar
  si SQLite satisface los requisitos operativos antes del despliegue.

## Migration Plan

1. Acordar políticas pendientes y caracterizar login, persistencia y tokens
   existentes antes de tocar sus rutas.
2. Agregar almacenamiento separado con migración versionada y reversible que no
   modifique ni elimine datos heredados; habilitar el onboarding tras configurar
   correo y claves de prueba o del entorno correspondiente.
3. Probar registro, verificación, interoperabilidad JWT y regresión de contratos;
   desplegar solo tras revisión humana. Si falla, deshabilitar el flujo nuevo y
   conservar el login anterior y los datos. No borrar cuentas o bases como parte
   automática del rollback; acordar cualquier recuperación de datos por separado.

## Decisiones bloqueantes antes de implementar

- Proveedor de correo y modo de entrega; alcance y protección de la información
  compartida con él.
- Política de contraseña, formato y duración del código, límites de intentos y
  envío, reenvío y manejo de desafíos caducados.
- Contratos HTTP, destino posterior a la sesión y transporte seguro de sesión.
- Algoritmos y parámetros concretos para proteger contraseñas y verificadores,
  gestión y rotación de claves, almacenamiento y despliegue.
- Compatibilidad y alcance de los accesos de la sesión nueva: el endpoint
  heredado `/api/tasks` no debe interpretarse como una función de wallet.
