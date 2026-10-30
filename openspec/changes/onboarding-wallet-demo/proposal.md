# Proposal

## Why

La historia de registro y activación necesita un recorrido guiado que pueda
probarse antes de aprobar KYC, integraciones financieras y requisitos de
producción. El alcance acordado es una simulación sin operaciones reales.

## What Changes

- Agregar un recorrido de demostración con nombre visible, revisión y activación
  simulada, mostrando el paso actual y bloqueando datos inválidos.
- Indicar que el estado es local y temporal, no representa una wallet real y
  no permite pagos. El home de pagos queda fuera de esta entrega.
- No registrar eventos ni implementar mediciones de adquisición, MAU, CAC o
  tiempo; los criterios 4, 5 y 6 de la HU quedan pendientes por decisión del
  solicitante y no se consideran cumplidos.
- No implementar KYC, identidad real, correo, credenciales ni backend de
  activación. La regulación y los requisitos de cumplimiento siguen pendientes.
- Preservar el login, los contratos y los datos heredados.

El cambio previo `onboarding-wallet` es un borrador separado para una cuenta con
correo y no está aprobado para esta simulación. Se conserva sin modificar.

## Capabilities

### New Capabilities

- `wallet-onboarding-demo`: recorrido guiado y activación simulada local.

### Modified Capabilities

Ninguna; no hay especificaciones principales registradas.

## Impact

- `web/`: ruta, interfaz, estado temporal y pruebas del recorrido.
- No modifica `auth/`, `api/`, datos persistentes, contratos HTTP ni dependencias.
- Un onboarding y una wallet reales requieren decisiones y revisión adicionales.
