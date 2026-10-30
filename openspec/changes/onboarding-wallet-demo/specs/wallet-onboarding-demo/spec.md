# Wallet onboarding demo

## ADDED Requirements

### Requirement: Recorrido guiado de demostración
El sistema SHALL mostrar los pasos nombre visible, revisión y activación
simulada, identificando el paso actual durante todo el recorrido.

#### Scenario: Inicio del recorrido
- **WHEN** la persona accede al onboarding de demostración
- **THEN** ve la secuencia completa y el paso de nombre visible como actual

#### Scenario: Avance y retroceso
- **WHEN** la persona avanza o vuelve al paso anterior
- **THEN** el indicador refleja el paso mostrado y el nombre se conserva

### Requirement: Validación del nombre visible
El sistema SHALL bloquear el avance si el nombre, después de quitar espacios
al inicio y al final, contiene menos de 2 o más de 40 caracteres.

#### Scenario: Nombre inválido
- **WHEN** la persona intenta continuar con un nombre vacío, demasiado corto o largo
- **THEN** permanece en el paso de nombre y recibe un mensaje para corregirlo

#### Scenario: Nombre válido
- **WHEN** la persona continúa con un nombre válido
- **THEN** ve el nombre normalizado en la revisión

### Requirement: Activación exclusivamente simulada
El sistema SHALL permitir confirmar la revisión y mostrar el estado activo
simulado solo después de proporcionar un nombre válido.

#### Scenario: Confirmación de la revisión
- **WHEN** la persona confirma los datos revisados
- **THEN** ve el estado activo simulado y una aclaración de que no existe una
  wallet real ni se pueden realizar pagos

#### Scenario: Reinicio de la demostración
- **WHEN** la persona reinicia la demostración o recarga la página
- **THEN** vuelve al paso inicial y no se conserva el estado activo

### Requirement: Aislamiento de funcionalidades fuera de alcance
El sistema SHALL no enviar los datos del recorrido a un servidor ni registrar
eventos de analítica; no SHALL presentar la simulación como KYC, una wallet
operativa o un punto de entrada de pagos.

#### Scenario: Recorrido completo
- **WHEN** se completa la demostración
- **THEN** no se crea una cuenta ni una wallet real, no se realiza ninguna
  operación financiera y no se habilita el home de pagos
