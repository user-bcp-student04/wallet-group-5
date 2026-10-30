# Spec Delta

## Purpose

Permitir el registro inicial de una cuenta y verificar el control del correo
antes de conceder una sesión en Wallet Group 5.

## ADDED Requirements

### Requirement: Solicitud de registro
El sistema SHALL aceptar una solicitud de registro con correo y contraseña
válidos para iniciar el onboarding de una cuenta, sin crear una wallet operativa.

#### Scenario: Datos válidos para un correo no registrado
- **WHEN** una persona envía un correo no registrado y una contraseña válidos
- **THEN** el sistema inicia un proceso de verificación pendiente y no habilita operaciones financieras

#### Scenario: Datos inválidos
- **WHEN** falta el correo o la contraseña, o alguno incumple las reglas aprobadas
- **THEN** el sistema rechaza la solicitud, informa del error de validación y no crea una cuenta activa

### Requirement: Respuesta genérica para correos existentes
El sistema SHALL ofrecer una respuesta pública equivalente para un correo válido
ya registrado y uno no registrado, sin revelar la existencia de una cuenta ni
alterar las credenciales o la sesión de una cuenta existente.

#### Scenario: Comparación de respuestas de registro
- **WHEN** se envían solicitudes válidas comparables para un correo existente y otro no registrado
- **THEN** sus códigos de respuesta y mensajes públicos son equivalentes y no incluyen información de existencia de cuenta

#### Scenario: Solicitud para cuenta existente
- **WHEN** se solicita el registro de un correo asociado a una cuenta existente
- **THEN** sus credenciales y su sesión no se modifican por esa solicitud

### Requirement: Verificación por correo
El sistema SHALL entregar al correo indicado un código de un solo uso, vinculado
al proceso de registro, antes de activar la cuenta.

#### Scenario: Código válido
- **WHEN** la persona completa el proceso con el código correcto antes de su vencimiento y dentro del límite de intentos
- **THEN** el sistema verifica el correo y activa la cuenta correspondiente una sola vez

#### Scenario: Código inválido, vencido o utilizado
- **WHEN** se presenta un código incorrecto, vencido o ya utilizado
- **THEN** el sistema no activa la cuenta ni inicia sesión y presenta un error sin revelar información sensible

#### Scenario: Fallo del servicio de correo
- **WHEN** el sistema detecta que el servicio de envío no está disponible
- **THEN** comunica un error recuperable sin revelar la existencia de la cuenta y no afirma que el correo fue enviado

### Requirement: Sesión después de verificar
El sistema SHALL iniciar una sesión automáticamente después de la verificación
exitosa, y no SHALL conceder una sesión a través del registro antes de ella.

#### Scenario: Verificación exitosa
- **WHEN** se verifica correctamente el correo de una cuenta nueva
- **THEN** se establece una sesión para esa cuenta y se muestra el estado de cuenta activa

#### Scenario: Cuenta pendiente
- **WHEN** la cuenta aún no ha completado la verificación
- **THEN** el proceso de onboarding no entrega una sesión autenticada

### Requirement: Protección del proceso de registro
El sistema SHALL proteger contraseñas y códigos de verificación y limitar los
intentos, sin exponerlos en respuestas ni registros de aplicación.

#### Scenario: Datos almacenados y registros
- **WHEN** se registra o verifica una cuenta
- **THEN** la contraseña y el código no se almacenan en texto plano ni aparecen en respuestas o logs

#### Scenario: Límite de intentos alcanzado
- **WHEN** se alcanza el límite configurado para intentos de verificación
- **THEN** el sistema rechaza nuevos intentos conforme a la política aprobada y no inicia sesión

### Requirement: Compatibilidad de contratos existentes
El sistema SHALL conservar los contratos de `POST /auth/login` y `/api/tasks`
durante la incorporación del onboarding.

#### Scenario: Uso de contratos heredados
- **WHEN** los consumidores existentes usan los contratos caracterizados de login y tareas
- **THEN** se mantienen sus métodos, formatos y comportamientos acordados
