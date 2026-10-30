# Proposal

## Why

La historia de registro y activación del MVP de wallet y su procedimiento
(`docs/stories/onboarding-wallet-procedimiento.md`) piden un onboarding guiado de
siete pasos (inicio, documento, corrección, doble factor, persistencia y control de
duplicados, activación y salida) que termine con una wallet activa, habilite el punto
de entrada a pagos de bajo monto y quede instrumentado para medir una mediana de 3
minutos. Solo se piden tipo y número de documento. Esta entrega sigue siendo una
simulación sobre el simulador de wallet (`docs/contracts/bcp-wallet-mock-openapi.yaml`):
sin documentos ni dinero reales.

El procedimiento amplía el alcance acordado antes: el doble factor, el punto de
entrada a pagos, la instrumentación y la protección frente a enumeración de cuentas
pasan a estar **en alcance**. La implementación existente (tres pasos, `409
ACCOUNT_EXISTS`, sin doble factor ni eventos) cubre solo una parte; las tareas de
`tasks.md` separan lo ya hecho de lo nuevo.

## What Changes

- Web (`web/`): recorrido con la secuencia completa y el paso actual siempre visibles,
  validación que bloquea datos inválidos con un mensaje junto al campo y sin borrar los
  valores válidos, desafío de doble factor, confirmación de activación y salida con el
  punto de entrada a pagos de bajo monto (sin iniciar ningún pago).
- API (`api/`): endpoints públicos de onboarding que validan en el servidor, **verifican
  el doble factor antes de crear o activar la cuenta**, **persisten la cuenta** sin
  duplicados ante solicitudes repetidas o concurrentes y activan la wallet solo cuando
  los pasos requeridos terminaron. Los estados de registro, verificación y activación
  se guardan por separado y la API es la fuente única del paso y estado actuales.
- Una cuenta posiblemente duplicada recibe una respuesta neutra, que no confirma si
  existe una cuenta para el documento y la orienta al canal de acceso o asistencia.
- Reanudación tras una interrupción desde un paso seguro, validando el estado
  persistido, sin registrar finalizaciones ficticias.
- Analítica de onboarding: eventos de inicio, finalización de cada paso y cierre, con
  marcas de tiempo e identificadores técnicos no sensibles (nunca el documento), y una
  salida que permita revisar la duración, los nuevos usuarios activos por mes y, cuando
  exista una fuente de gasto acordada, la atribución para CAC.
- Seguridad: canales cifrados, datos persistidos protegidos con acceso restringido, sin
  documento, códigos ni secretos en logs, analítica o errores, y límites de frecuencia
  en el doble factor.
- Preservar el login, los contratos y los datos heredados.

**Decisiones pendientes de aprobación (la simulación usa valores provisionales; ver `design.md`):**

- **Mecanismo de doble factor aprobado para el MVP**, su canal y el dato de contacto. La
  simulación usa un código de prueba por entorno (`ONBOARDING_OTP_TEST_CODE`), que no autentica a nadie.
- **Frontera analítica oficial.** La simulación usa `onboarding.started` → `onboarding.closed`
  con la wallet activa; falta confirmarla con el Product Owner.
- **Origen y reglas de atribución del gasto de adquisición** (responsables por
  coordinar) para evaluar CAC de PEN 10; los umbrales de MAU (1,000–2,000) y CAC son
  objetivos del Product Owner, no decisiones de este cambio.
- **Canal de acceso o asistencia** para quien ya tiene una cuenta.
- **Límites de frecuencia** del doble factor y política de retención de la analítica.

**Fuera de alcance:** ejecución de pagos, cobros QR y su operación; el evento de
activación usado para MAU (lo emiten los pagos exitosos, historia de confirmación de
pagos); KYC y documentos reales; requisitos regulatorios; integraciones de proveedores
adicionales; un riel de pago único.

El cambio previo `onboarding-wallet` (cuenta con correo) tiene otro alcance y se
conserva sin modificar.

## Capabilities

### New Capabilities

- `wallet-onboarding-demo`: registro guiado con doble factor, cuenta única persistida,
  activación de la wallet contra el proveedor simulado, salida hacia pagos de bajo
  monto e instrumentación del onboarding.

### Modified Capabilities

Ninguna; no hay especificaciones principales registradas.

## Impact

- `api/`: tabla de cuentas y de estado de onboarding, desafío de doble factor, eventos
  de analítica, endpoints `/api/onboarding`, cliente del simulador, variable
  `WALLET_MOCK_URL` y pruebas. Estos endpoints no exigen JWT.
- `web/`: ruta `/onboarding`, pasos de doble factor y salida, cliente HTTP hacia la API y
  pruebas.
- `compose.yaml`: variable `WALLET_MOCK_URL` para la API y la configuración que fije el
  mecanismo de doble factor aprobado.
- No modifica `auth/` ni los contratos heredados de tareas.
