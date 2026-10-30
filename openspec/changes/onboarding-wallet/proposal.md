# Proposal

## Why

Wallet Group 5 necesita un proceso inicial para que una persona cree una cuenta
y confirme que controla su correo antes de acceder. El sistema heredado solo
implementa un login de demostración y no ofrece este proceso.

## What Changes

- Agregar registro web con correo y contraseña, creando una cuenta pendiente de
  verificación sin habilitar operaciones financieras.
- Enviar un código de un solo uso por correo y verificarlo antes de activar la
  cuenta y establecer automáticamente una sesión.
- Responder de forma genérica ante correos ya registrados y proteger los datos,
  los códigos y las credenciales durante el proceso.
- Mantener los contratos heredados de `POST /auth/login` y `/api/tasks`; este
  cambio no autoriza sustituirlos ni retirar el código existente.

Quedan fuera la creación de una wallet operativa, depósitos, retiros,
transferencias, tarjetas, pagos y verificación de identidad documental.
El proveedor de correo, la política de contraseña, los parámetros del código y
el destino tras la sesión están pendientes de aprobación antes de implementar.

## Capabilities

### New Capabilities

- `account-onboarding`: registro de cuenta, verificación del correo y
  establecimiento de sesión tras la verificación.

### Modified Capabilities

Ninguna: no hay especificaciones principales registradas actualmente.

## Impact

- `auth/`: nuevos contratos de registro y verificación, persistencia segura,
  envío de correo y emisión de sesión; conservar el contrato de login existente.
- `web/`: formularios y estados de registro y verificación; sin enviar al
  usuario al dashboard heredado como si fuera la wallet.
- `api/`: la sesión debe ser interoperable con su verificador JWT; validar la
  integración sin alterar `/api/tasks` ni su formato.
- Se requiere acordar proveedor de correo, gestión de claves, almacenamiento,
  límites de intentos y dependencias de seguridad antes de la implementación.
  Los valores reales se configurarán externamente; las pruebas usarán datos y
  claves aislados.
